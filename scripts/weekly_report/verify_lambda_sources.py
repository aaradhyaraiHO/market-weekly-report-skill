#!/usr/bin/env python3
"""Read-only realtime-source contract checks; no reports, alerts or source writes.

Default: no-cost query/schema dry runs. --reconcile additionally reads
aggregates for a completed week and its twelve-week TY/LY comparison windows.
The production 80 GiB/query cap is never raised. No raw customer rows are saved.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd
from google.cloud import bigquery

import config
import fetch


def windows(week):
    start = date.fromisoformat(week)
    if start.weekday() != 6:
        raise ValueError('week must start on Sunday')
    end = start + timedelta(days=6)
    return start, end, start-timedelta(days=7), end-timedelta(days=7), start-timedelta(days=364), end-timedelta(days=364)


def queries(week):
    w = windows(week)
    result = []
    def capture(sql, label, params, **kwargs):
        result.append({'sql': sql, 'label': label, 'params': params})
        return pd.DataFrame()
    with patch.object(fetch, 'query_df', side_effect=capture):
        for market in [*config.MARKETS.values(), None]:
            for function in (fetch.ce_weekly_actual_revenue, fetch.ce_daily_orders_google):
                function(market, *w[:2])
            for function in (fetch.ce_tgids, fetch.ce_variants, fetch.ce_leadtime, fetch.ce_countries, fetch.ce_channels):
                function(market, *w)
            fetch.ce_tgid_leadtime(market, *w[:4])
            for function in (fetch.ce_leadtime_history, fetch.ce_country_history, fetch.ce_channel_history):
                function(market, w[0]-timedelta(weeks=11), w[1], w[4]-timedelta(weeks=11), w[5])
        fetch.availability_signal(['18 - Chicago'], w[2], *w[:2])
    return result


def job_config(params, dry_run=False):
    values = [bigquery.ArrayQueryParameter(k, 'STRING', list(v)) if isinstance(v, (list, tuple))
              else bigquery.ScalarQueryParameter(k, 'STRING', str(v)) for k, v in params.items()]
    return bigquery.QueryJobConfig(query_parameters=values, dry_run=dry_run,
        use_query_cache=False, maximum_bytes_billed=config.MAX_BYTES_BILLED,
        labels={'tool': 'weekly_report', 'step': 'lambda_source_verification'})


def check_queries(client, rows):
    def one(row):
        record = {k: row[k] for k in ('label', 'params')}
        record['sql_sha256'] = hashlib.sha256(row['sql'].encode()).hexdigest()
        try:
            job = client.query(row['sql'], job_config=job_config(row['params'], True), timeout=30)
            record.update(status='passed', estimated_bytes=job.total_bytes_processed or 0)
            if record['estimated_bytes'] > config.MAX_BYTES_BILLED:
                raise ValueError('Estimated scan exceeds the existing cap')
        except Exception as exc:
            record.update(status='failed', error=str(exc)[:1000])
        return record
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(one, rows))


def aggregate_check(left, right, keys, mapping, label):
    def indexed(frame, columns):
        grouped = frame.groupby(keys, dropna=False)[columns].sum(min_count=1)
        return {tuple(None if pd.isna(value) else str(value) for value in (key if isinstance(key, tuple) else (key,))): row
                for key, row in grouped.to_dict('index').items()}
    a, b = indexed(left, list(mapping)), indexed(right, list(mapping.values()))
    mismatches, unavailable = [], []
    for key in a.keys() | b.keys():
        if key not in a or key not in b:
            mismatches.append({'key': str(key), 'error': 'missing group', 'missing_side': 'left' if key not in a else 'right'})
            continue
        for field, other in mapping.items():
            av, bv = a[key][field], b[key][other]
            if pd.isna(av) and pd.isna(bv):
                unavailable.append({'key': str(key), 'field': field, 'reason': 'source fact is null on both independent paths'})
                continue
            if (pd.isna(av) and bv == 0) or (pd.isna(bv) and av == 0):
                unavailable.append({'key': str(key), 'field': field,
                    'reason': 'null source vs legacy period SUM/CASE zero: value parity unavailable, not a verified zero'})
                continue
            av = float('nan') if pd.isna(av) else float(av)
            bv = float('nan') if pd.isna(bv) else float(bv)
            if not math.isclose(av, bv, rel_tol=1e-9, abs_tol=0.00001):
                mismatches.append({'key': str(key), 'field': field,
                    'left': av if math.isfinite(av) else None, 'right': bv if math.isfinite(bv) else None})
    status = 'failed' if mismatches else 'passed_with_source_gaps' if unavailable else 'passed'
    return {'label': label, 'status': status, 'groups': len(a.keys() | b.keys()),
            'mismatch_count': len(mismatches), 'examples': mismatches[:5],
            'unavailable_count': len(unavailable), 'unavailable_examples': unavailable[:5]}


def reconcile(client, week):
    w = windows(week)
    if w[1] >= datetime.now(ZoneInfo('Asia/Kolkata')).date():
        raise ValueError('Live reconciliation requires a completed week; dry runs can check a planned week')
    history_start, history_ly_start = w[0]-timedelta(weeks=11), w[4]-timedelta(weeks=11)
    params = {'start': str(history_start), 'end': str(w[1]), 'ly_start': str(history_ly_start), 'ly_end': str(w[5])}
    evidence, costs = [], []
    def execute(sql, label='check', values=None, **kwargs):
        values = values or {}
        estimate = client.query(sql, job_config=job_config(values, True), timeout=30)
        if (estimate.total_bytes_processed or 0) > config.MAX_BYTES_BILLED:
            raise ValueError('Read-only verification exceeds the existing cap: ' + label)
        job = client.query(sql, job_config=job_config(values), timeout=30)
        frame = pd.DataFrame([dict(row) for row in job.result(timeout=180)])
        costs.append({'label': label, 'job_id': job.job_id, 'bytes_processed': job.total_bytes_processed})
        return frame
    period = '(DATE(created_at) BETWEEN @start AND @end OR DATE(created_at) BETWEEN @ly_start AND @ly_end)'
    grain = execute(f"""
        SELECT 'orders' AS source, COUNT(*) AS row_count, COUNT(DISTINCT order_id) AS distinct_ids,
               COUNTIF(order_id IS NULL) AS null_ids FROM {config.FCT_ORDERS} WHERE {period}
        UNION ALL
        SELECT 'bookings', COUNT(*), COUNT(DISTINCT booking_id), COUNTIF(booking_id IS NULL)
        FROM {config.FCT_BOOKINGS} WHERE {period}
    """, 'source_key_grain', params)
    for row in grain.to_dict('records'):
        evidence.append({'label': row['source']+'_unique_keys', **row,
            'status': 'passed' if row['row_count'] == row['distinct_ids'] and row['null_ids'] == 0 else 'failed'})
    if any(row['status'] != 'passed' for row in evidence):
        return {'checks': evidence, 'query_costs': costs, 'status': 'failed'}
    # Every ordinary fetch here is an existing, unchanged-math source consumer.
    with patch.object(fetch, 'query_df', side_effect=execute):
        calls = [
            (fetch.ce_weekly_actual_revenue, (None, history_start, w[1])),
            (fetch.ce_weekly_actual_revenue, (None, history_ly_start, w[5])),
            (fetch.ce_channel_history, (None, history_start, w[1], history_ly_start, w[5])),
            (fetch.ce_tgids, (None, *w)), (fetch.ce_variants, (None, *w)),
            (fetch.ce_leadtime, (None, *w)),
            (fetch.ce_leadtime_history, (None, history_start, w[1], history_ly_start, w[5])),
            (fetch.ce_countries, (None, *w)),
            (fetch.ce_country_history, (None, history_start, w[1], history_ly_start, w[5])),
            (fetch.ce_tgid_leadtime, (None, *w[:4])),
        ]
        with ThreadPoolExecutor(max_workers=4) as pool:
            (actual_ty, actual_ly, channel_history, tgids, variants, lead, lead_history,
             countries, country_history, tgid_lead) = list(pool.map(lambda call: call[0](*call[1]), calls))
    for frame in (actual_ty, actual_ly, channel_history, lead_history, country_history):
        frame['week'] = pd.to_datetime(frame['week']).dt.date
    for period_name, actual in (('ty', actual_ty), ('ly', actual_ly)):
        comparison = actual.copy()
        if period_name == 'ly':
            comparison['week'] += timedelta(days=364)
        evidence.append(aggregate_check(comparison, channel_history[channel_history.period == period_name],
            ['combined_entity_id', 'week'], {'actual_revenue': 'rev'}, 'channel_history_vs_actual_'+period_name))
    # Compare the existing period tables with their twelve-week histories.
    for frame, history, key, label in ((lead, lead_history, 'band', 'leadtime'),
                                        (countries, country_history, 'country', 'countries')):
        for suffix, point, period_name in (('', w[0], 'ty'), ('_wm1', w[2], 'ty'), ('_ly', w[0], 'ly')):
            selected = history[(history.week == point) & (history.period == period_name)]
            # Period tables contain union-of-period groups with explicit zero
            # activity in other periods; histories contain only actual groups.
            # Use real order/booking counts, never assume an absent fact is zero.
            count = ('bookings' if label == 'leadtime' else 'orders') + suffix
            active = frame[frame[count] > 0]
            evidence.append(aggregate_check(active, selected, ['combined_entity_id', key],
                {'rev'+suffix: 'rev'}, label+'_period_history'+suffix))
    # Variant economics must reconcile to their existing TGID parents without
    # multiplying revenue or counting an order once per component booking.
    keys = ['combined_entity_id', 'tgid']
    parent_keys = pd.MultiIndex.from_frame(tgids[keys])
    visible_variants = variants[pd.MultiIndex.from_frame(variants[keys]).isin(parent_keys)]
    evidence.append(aggregate_check(tgids, visible_variants, keys,
        {name+suffix: name+suffix for name in ('rev', 'orders', 'gbv', 'completed_gbv') for suffix in ('', '_wm1', '_ly')},
        'variant_children_vs_tgid_parents'))
    for column in ('pct', 'pct_wm1'):
        sums = tgid_lead.groupby(keys)[column].sum(min_count=1).dropna()
        bad = sums[abs(sums-1) > 1e-9]
        evidence.append({'label': 'tgid_leadtime_shares_'+column, 'status': 'passed' if bad.empty else 'failed',
                         'groups': len(sums), 'mismatch_count': len(bad)})
    status = ('failed' if any(r['status']=='failed' for r in evidence) else
              'passed_with_source_gaps' if any(r['status']=='passed_with_source_gaps' for r in evidence) else 'passed')
    return {'checks': evidence, 'query_costs': costs, 'status': status}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--week', required=True)
    parser.add_argument('--reconcile', action='store_true', help='Read aggregates for a completed week, not a full report run')
    parser.add_argument('--out', type=Path, help='Optional new verification receipt; never overwrite an existing file')
    args = parser.parse_args()
    windows(args.week)
    if args.out and args.out.exists():
        raise ValueError('Verification receipt already exists')
    client = bigquery.Client(project=config.BQ_PROJECT, location=config.BQ_LOCATION)
    result = {'schema': 'weekly-lambda-source-verification/v1', 'week': args.week,
        'started_at': datetime.now(timezone.utc).isoformat(), 'maximum_bytes_billed': config.MAX_BYTES_BILLED,
        'source_hashes': {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('fetch.py', 'config.py')},
        'reports_or_alerts_written': False}
    result['dry_runs'] = check_queries(client, queries(args.week))
    if all(r['status']=='passed' for r in result['dry_runs']) and args.reconcile:
        try:
            result['reconciliation'] = reconcile(client, args.week)
        except Exception as exc:
            result['reconciliation'] = {'status': 'failed', 'error': str(exc)[:2000]}
    result['status'] = result.get('reconciliation', {}).get('status', 'passed') if all(r['status']=='passed' for r in result['dry_runs']) else 'failed'
    result['finished_at'] = datetime.now(timezone.utc).isoformat()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x') as output:
            json.dump(result, output, indent=2, default=str, allow_nan=False)
    print(json.dumps({'status': result['status'], 'dry_runs': len(result['dry_runs']),
        'dry_run_failures': [r for r in result['dry_runs'] if r['status'] != 'passed'],
        'reconciliation': result.get('reconciliation'), 'receipt': str(args.out) if args.out else None}, default=str), flush=True)
    return 0 if result['status'] in ('passed', 'passed_with_source_gaps') else 1


if __name__ == '__main__':
    sys.exit(main())
