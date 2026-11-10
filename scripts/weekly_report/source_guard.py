"""Read-only economic anomaly and source/report reconciliation release gate.

A gate rejects suspicious facts; it never clamps, replaces, or changes them.
Small negative/refund days are allowed. Material negative revenue larger than
both $1,000 and twice the day's absolute order value requires investigation.
"""
import argparse
import calendar
import datetime as dt
import json
import math
from pathlib import Path

import config
from bq import query_df
from build_v2_goals import FORECAST_AUTHORITY

AD_COSTS = ('sum_google_ads_spend', 'sum_google_split_ads_spend', 'sum_pmax_ads_spend',
    'sum_travel_ads_spend', 'sum_google_remarketing_ads_spend', 'sum_google_brand_ads_spend',
    'sum_microsoft_ads_spend', 'sum_microsoft_split_ads_spend',
    'sum_microsoft_brand_ads_spend', 'sum_microsoft_remarketing_ads_spend',
    'sum_facebook_ads_spend',
    'sum_facebook_split_ads_spend', 'sum_facebook_remarketing_ads_spend',
    'sum_apple_ads_spend', 'sum_criteo_remarketing_ads_spend')
OTHER_COSTS = ('sum_coupon_discount', 'sum_wallet_credits', 'sum_affiliate_commission',
    'sum_creator_collab_costs', 'sum_creator_collab_coupon_costs')


def read_daily(week):
    start = dt.date.fromisoformat(week)
    end = start + dt.timedelta(days=6)
    # Include W-1, W0 and the same weekday-aligned LY windows. Explicit timestamp
    # bounds prune monthly partitions. No new or increased query-byte allowance.
    ranges = [(start-dt.timedelta(days=7), end),
              (start-dt.timedelta(days=config.YOY_LAG_DAYS+7),
               end-dt.timedelta(days=config.YOY_LAG_DAYS))]
    params, conditions = {}, []
    for i, (a, b) in enumerate(ranges):
        params.update({f's{i}': a.isoformat(), f'e{i}': (b+dt.timedelta(days=1)).isoformat()})
        conditions.append(f'(report_timestamp >= TIMESTAMP(@s{i}) AND report_timestamp < TIMESTAMP(@e{i}))')
    costs = ' + '.join(f'SUM({c})' for c in OTHER_COSTS)
    # Verified Omni semantics: absent Bing brand/remarketing values contribute
    # zero, including historical comparisons. A missing source column still fails.
    ad_costs = ' + '.join(
        f'COALESCE({c}, 0)' if c in (
            'sum_microsoft_brand_ads_spend', 'sum_microsoft_remarketing_ads_spend'
        ) else c for c in AD_COSTS
    )
    sql = f"""
        SELECT report_date, business_market, CAST(combined_entity_id AS STRING) ce_id,
               SUM({config.REVENUE_COL}) revenue, SUM(sum_revenue) booked_revenue,
               SUM(sum_order_value) gbv, COUNT(*) source_rows,
               COUNTIF({config.REVENUE_COL} IS NULL AND count_orders > 0) missing_revenue,
               SUM({config.REVENUE_COL}) + SUM(sum_co_marketing_commission)
                 + SUM(sum_insider_commission) - SUM(sum_direct_costs) cm1_business,
               SUM({ad_costs}) + {costs} gross_marketing_cost
        FROM {config.CE_STATS}
        WHERE {' OR '.join(conditions)}
        GROUP BY 1, 2, 3
    """
    return query_df(sql, 'source_release_guard', params).to_dict('records')


def anomalies(rows):
    failures = []
    for row in rows:
        ident = f"{row['business_market']} CE {row['ce_id']} {row['report_date']}"
        if row.get('missing_revenue'):
            failures.append(f'{ident}: missing revenue for orders')
        for field in ('revenue', 'booked_revenue', 'gbv', 'cm1_business', 'gross_marketing_cost'):
            value = row.get(field)
            if value is None or not math.isfinite(float(value)):
                failures.append(f'{ident}: missing/non-finite {field}')
        if row.get('gbv') is not None:
            threshold = max(1000, 2*abs(float(row['gbv'])))
            for field in ('revenue', 'booked_revenue'):
                if row.get(field) is not None and float(row[field]) < -threshold:
                    failures.append(f'{ident}: extreme negative {field}={row[field]} vs order value={row["gbv"]}')
    return failures


def close(a, b, *, absolute=1):
    return (a is not None and b is not None and math.isfinite(float(a))
            and math.isfinite(float(b)) and math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=absolute))


def reconcile(snapshot, rows):
    meta = snapshot['meta']; start = dt.date.fromisoformat(meta['week_start'])
    source = [r for r in rows if meta['market_slug'] == 'headout' or r['business_market'] == meta['market']]
    failures, evidence = [], []
    for offset, label, key in [(0, 'W0', 'weekly'), (-7, 'W-1', 'weekly'),
                                (-config.YOY_LAG_DAYS, 'LY', 'weekly_ly')]:
        a = start + dt.timedelta(days=offset); b = a+dt.timedelta(days=6)
        actual_week = start if key == 'weekly_ly' else a
        found = [r for r in snapshot['market_summary'][key] if str(r['week'])[:10] == actual_week.isoformat()]
        subset = [r for r in source if a <= dt.date.fromisoformat(str(r['report_date'])[:10]) <= b]
        if len(found) != 1 or not subset:
            failures.append(f'{meta["market_slug"]} {label}: missing unique snapshot/source week'); continue
        expected = {field: sum(float(r[field]) for r in subset) for field in
                    ('revenue', 'cm1_business', 'gross_marketing_cost')}
        for field, value in expected.items():
            if not close(found[0].get(field), value):
                failures.append(f'{meta["market_slug"]} {label}: {field} snapshot={found[0].get(field)} source={value}')
        roi = 100*expected['cm1_business']/expected['gross_marketing_cost'] if expected['gross_marketing_cost'] else None
        if roi is not None and not close(found[0].get('roi1_pct'), roi, absolute=.011):
            failures.append(f'{meta["market_slug"]} {label}: ROI operands do not reconcile')
        evidence.append({'period': label, **expected, 'roi1_pct': roi})
    return failures, evidence


def validate_goal(goal):
    failures = []
    if goal.get('forecast_authority') != FORECAST_AUTHORITY:
        failures.append('unverified forecast authority (four-week extrapolation is not Goals forecast)')
    if not close(goal.get('forecast_revenue'), goal.get('forecast_source_revenue'), absolute=.01):
        failures.append('forecast differs from full-month warehouse source')
    month = dt.date.fromisoformat(goal['month']+'-01')
    if goal.get('forecast_source_days') != calendar.monthrange(month.year, month.month)[1]:
        failures.append('incomplete full-month forecast evidence')
    if not close(goal.get('forecast_revenue'),
                 (goal.get('mtd_revenue') or 0)+(goal.get('forecast_remaining_revenue') or 0), absolute=.01):
        failures.append('forecast operands do not reconcile')
    return failures


def read_month_forecasts(month):
    start = dt.date.fromisoformat(month+'-01')
    end = (start.replace(day=28)+dt.timedelta(days=4)).replace(day=1)
    return query_df(f"""
        SELECT business_market, SUM({config.REVENUE_COL}) revenue,
               COUNT(DISTINCT report_date) days,
               COUNTIF({config.REVENUE_COL} IS NULL) missing_revenue
        FROM {config.CE_STATS}
        WHERE report_timestamp >= TIMESTAMP(@start)
          AND report_timestamp < TIMESTAMP(@end)
        GROUP BY 1
    """, 'forecast_release_guard', {'start':start.isoformat(),'end':end.isoformat()}).to_dict('records')


def check(week, snapshots=(), goals=None):
    rows = read_daily(week)
    failures = anomalies(rows)
    if not rows:
        failures.append('Source query returned no rows')
    evidence = {}
    # Retain a usable failure receipt even if required source operands are NULL.
    # Do not try to sum them (or run more enrichment queries) after a source gate fails.
    for path in snapshots if not failures else ():
        snapshot = json.loads(Path(path).read_text())
        if snapshot['meta']['week_start'] != week:
            failures.append(f'{path}: wrong snapshot week'); continue
        issues, facts = reconcile(snapshot, rows)
        failures.extend(issues); evidence[snapshot['meta']['market_slug']] = facts
    unavailable_goals = []
    if goals is not None and not failures:
        month=(dt.date.fromisoformat(week)+dt.timedelta(days=6)).strftime('%Y-%m')
        forecasts=read_month_forecasts(month)
        for slug in (*config.MARKETS, 'headout'):
            goal = goals.get(slug)
            if goal is None:
                # Existing optional-enrichment contract: an absent goal is
                # displayed unavailable. Never turn it into an inferred value.
                unavailable_goals.append(slug)
            else:
                failures.extend(f'{slug}: {issue}' for issue in validate_goal(goal))
                source=[r for r in forecasts if slug=='headout' or r['business_market']==config.MARKETS[slug]]
                if (goal.get('month')!=month or not source
                        or any(r['missing_revenue'] for r in source)
                        or any(r['days']!=calendar.monthrange(int(month[:4]),int(month[5:]))[1] for r in source)
                        or not close(goal.get('forecast_revenue'),sum(r['revenue'] for r in source))):
                    failures.append(f'{slug}: monthly forecast differs from fresh Goals-authority source')
    return {'schema':'weekly-source-release-guard/v1', 'week':week,
            'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),
            'status':'failed' if failures else 'passed', 'failures':failures,
            'source_daily_rows':len(rows), 'reconciliation':evidence,
            'unavailable_goals':unavailable_goals}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--week',required=True); p.add_argument('--snapshots',nargs='*',default=[])
    p.add_argument('--goals',type=Path); p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    goals=json.loads(args.goals.read_text())['markets'] if args.goals else None
    result=check(args.week,args.snapshots,goals)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,default=str)+'\n')
    print(json.dumps(result))
    if result['status']!='passed':
        raise SystemExit('Source anomaly/reconciliation gate failed; do not publish')

if __name__=='__main__':
    main()
