"""Prepare all approved market + Headout alerts and RCA before any Slack write.

The output is immutable for a week. Delivery retries use it without rerunning BQ.
This is delivery state, not a snapshot archive or a live report backfill.
"""
import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'scripts' / 'weekly_report'))
import config
from weekly_alert_v2 import load_headline, build_payload, LEDGER_SLUG
from safe_delivery import atomic_json, compile_market, digest, validate_bundle
from check_readiness import check


def query_rca(batch, week, end, path):
    result = subprocess.run([sys.executable, str(ROOT / 'alert' / 'weekly_rca_helper.py'),
                             '--ce-ids', ','.join(batch), '--week-start', week, '--week-end', end,
                             '--out', str(path)], capture_output=True, text=True, cwd=ROOT / 'alert')
    if result.returncode:
        error = result.stderr or ''
        cap_hit = any(term in error.lower() for term in ('maximum bytes billed', 'maximum_bytes_billed', 'bytes billed limit'))
        if cap_hit and len(batch) > 1:
            mid = len(batch) // 2
            return {**query_rca(batch[:mid], week, end, path.with_name(path.stem + '-a.json')),
                    **query_rca(batch[mid:], week, end, path.with_name(path.stem + '-b.json'))}
        raise RuntimeError(f'RCA failed for {batch}; no parent alerts will be sent. ' + error[-1500:])
    return json.loads(path.read_text())


def prepare(week, reports, okrs, out):
    from release_integrity import completed_week
    completed_week(week)
    if out.exists():
        bundle = json.loads(out.read_text())
        validate_bundle(bundle)
        if bundle['week'] != week:
            raise ValueError('Existing bundle week differs')
        raise ValueError('Frozen bundle already exists; resume delivery from it, do not regenerate')
    readiness = check(include_headout=True)
    if not readiness['ready']:
        raise ValueError(f'Alert routing not ready: {readiness["blockers"]}')
    bgms = json.loads((HERE / 'market_bgms.json').read_text())
    channels = json.loads((ROOT / 'alert' / 'market_channels.json').read_text())['markets']
    okr_data = json.loads(okrs.read_text())
    payloads = {}
    headlines = {}
    all_ids = set()
    for slug in [*config.MARKETS, 'headout']:
        headline = load_headline(reports / f'report_{slug}_{week}.html', slug, week_start=week)
        headlines[slug] = headline
        route = 'csee-nordics' if slug in ('csee', 'nordics') else LEDGER_SLUG[slug]
        url = f'https://market-notebook.vercel.app/weekly-report-{route}-{week}'
        if slug in ('csee', 'nordics'):
            url += f'?market={slug}'
        payloads[slug] = build_payload(headline, bgms, okr_data, url)
        all_ids.update(map(str, payloads[slug]['_rca']['ce_ids']))
    # Query the CE union once. Bounded batches avoid a giant ID query, retain
    # the existing byte ceiling/formulas, and never treats a query failure as RCA.
    evidence = {}
    work = out.parent / 'rca'
    work.mkdir(parents=True, exist_ok=True)
    end = (dt.date.fromisoformat(week) + dt.timedelta(days=6)).isoformat()
    ids = sorted(all_ids)
    for index in range(0, len(ids), 10):
        batch = ids[index:index + 10]
        path = work / f'batch-{index}.json'
        result = query_rca(batch, week, end, path)
        for ce in batch:
            if ce not in result:
                raise ValueError(f'Missing RCA source row: CE {ce}; no alerts are sendable')
            evidence[ce] = result[ce]
    markets = [compile_market(slug, week, channels[slug], payload, evidence)
               for slug, payload in payloads.items()]
    for market in markets:
        market['headline_sha256'] = digest(headlines[market['slug']])
    bundle = {'schema': 'weekly-v2-delivery/v1', 'week': week,
              'markets': markets, 'sha256': digest(markets)}
    validate_bundle(bundle)
    atomic_json(out, bundle)
    return bundle


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--week', required=True)
    parser.add_argument('--reports', type=Path, required=True)
    parser.add_argument('--okrs', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    bundle = prepare(args.week, args.reports, args.okrs, args.out)
    print(json.dumps({'week': args.week, 'markets': len(bundle['markets']), 'bundle': str(args.out)}))
