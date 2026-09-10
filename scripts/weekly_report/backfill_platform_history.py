"""Guarded, additive platform backfill for frozen weekly report artifacts.

No queries or external writes. Source rows must reproduce every stored paid
operand/ratio before missing Google/Bing values can be filled. Existing values,
report totals, notes, and alert ledgers are never overwritten.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import datetime as dt
from functools import lru_cache
import json
from pathlib import Path

from build_snapshot import _weekly_metrics
import headline_v2
from upgrade_frozen_release import DATA, digest

PAID_KEYS = (
    'spend', 'coupon_wallet', 'cm1', 'paid_conversions', 'paid_impressions',
    'paid_clicks', 'paid_conv_value', 'paid_revenue', 'paid_cvr_pct',
    'paid_ctr_pct', 'paid_sis_pct', 'roi_pct', 'cpc', 'paid_rpc',
    'spend_g', 'cm1_g', 'paid_clicks_g', 'conversions_g', 'tr_g_pct',
)
EXTRA = ('coupon_wallet_g', 'offline_revenue_g', 'sis_impr', 'sis_elig')


def enriched_row(frozen, source):
    result = deepcopy(frozen)
    if not any(frozen.get(k) is not None for k in PAID_KEYS):
        return result, 'no_frozen_paid_evidence'
    # Complete frozen evidence is already authoritative, even if today's table
    # has subsequently changed. It is not an unresolved backfill item.
    if isinstance(frozen.get('paid_platforms'), dict):
        return result, 'already_stored'
    if source is None:
        return result, 'source_missing'
    candidate = _weekly_metrics(None, source)
    if any(frozen.get(k) != candidate.get(k) for k in PAID_KEYS if k in frozen):
        return result, 'source_drift'
    for key in EXTRA:
        if result.get(key) is None and source.get(key) is not None:
            result[key] = source[key]
    return result, 'reconciled'


def fill_missing(old, candidate):
    """Only null-to-value fills; list identities and existing values are fixed."""
    if isinstance(old, dict):
        result = deepcopy(old)
        for key in old:
            if key in candidate:
                result[key] = fill_missing(old[key], candidate[key])
        return result
    if isinstance(old, list):
        if len(old) != len(candidate):
            raise ValueError('platform list length changed')
        return [fill_missing(a, b) for a, b in zip(old, candidate)]
    if old is None and isinstance(candidate, (float, int)):
        return candidate
    return old


def attach_breakdowns(old, candidate):
    result = deepcopy(old)
    by_key = {r['key']: r for r in candidate.get('paid', [])}
    for row in result.get('paid', []):
        new = by_key.get(row['key'])
        if new is None:
            continue
        for key in ('w0', 'wm1', 'delta_abs', 'delta_pct', 'series'):
            if row.get(key) != new.get(key):
                raise ValueError(f'parent drift: {row["key"]}/{key}')
        if 'breakdown' not in row:
            continue  # Only already-released expandable platform rows are in scope.
        row['breakdown'] = fill_missing(row['breakdown'], new['breakdown'])
        for child in row['breakdown']:
            if child.get('w0') is not None and child.get('unavailable_reason') == 'Platform data unavailable':
                child['unavailable_reason'] = None
    return result


def run(artifact, cache, source_dir, weeks):
    artifact, cache, source_dir = map(Path, (artifact, cache, source_dir))
    sources = {}
    for label in ('ty', 'ly'):
        records = json.loads((source_dir / f'{label}.json').read_text())
        pairs = [(str(r['combined_entity_id']), r['week'][:10]) for r in records]
        if len(set(pairs)) != len(pairs):
            raise ValueError('ambiguous source CE/week keys')
        sources[label] = dict(zip(pairs, records))
    receipt = {'source_files': {p.name: digest(p) for p in source_dir.glob('*.json')},
               'pages': [], 'snapshots': {}, 'unresolved': [], 'counts': Counter()}

    @lru_cache(maxsize=3)
    def snapshot(slug, week):
        path = cache / f'snapshot_{slug}_{week}.json'
        if not path.exists():
            return None
        receipt['snapshots'][path.name] = digest(path)
        return {str(ce['ce_id']): ce for ce in json.loads(path.read_text()).get('ces', [])}

    for page in sorted(artifact.glob('weekly-report-*.html')):
        original = page.read_text()
        match = DATA.search(original)
        if not match:
            continue
        payload = json.loads(match.group(1))
        changed = 0
        for view in payload.get('headlines', []):
            if view['week_start'] not in weeks:
                continue
            ce_map = snapshot(view['market_slug'], view['week_start'])
            if ce_map is None:
                continue
            for ce in view.get('all_ces', []):
                raw = ce_map.get(str(ce['ce_id']))
                if raw is None:
                    continue
                enriched = {}
                states = Counter()
                for field, label, lag in (('weekly', 'ty', 0), ('weekly_ly', 'ly', 364)):
                    enriched[field] = []
                    for row in raw.get(field, []):
                        source_week = (dt.date.fromisoformat(row['week']) - dt.timedelta(days=lag)).isoformat()
                        new, state = enriched_row(row, sources[label].get((str(ce['ce_id']), source_week)))
                        enriched[field].append(new)
                        states[state] += 1
                candidate = headline_v2._ce_drawer_metrics(enriched['weekly'], enriched['weekly_ly'], raw.get('funnel'))
                old = ce.get('drawer_metrics', {})
                try:
                    updated = attach_breakdowns(old, candidate)
                except ValueError:
                    states['snapshot_parent_drift'] += 1
                    updated = old
                receipt['counts'].update(states)
                if updated != old:
                    ce['drawer_metrics'] = updated
                    changed += 1
                if states['source_drift'] or states['snapshot_parent_drift']:
                    receipt['unresolved'].append({'page': page.name, 'ce_id': ce['ce_id'], 'counts': dict(states)})
        if changed:
            serialized = json.dumps(payload, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
            page.write_text(original[:match.start(1)] + serialized + original[match.end(1):])
        receipt['pages'].append({'page': page.name, 'changed_ces': changed, 'sha256': digest(page)})
    receipt['counts'] = dict(receipt['counts'])
    path = artifact.parent / (artifact.name + '_platform_receipt.json')
    path.write_text(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--artifact', required=True)
    p.add_argument('--cache', default='.cache/weekly_report')
    p.add_argument('--source', required=True)
    p.add_argument('--weeks', nargs='+', required=True)
    a = p.parse_args()
    r = run(a.artifact, a.cache, a.source, set(a.weeks))
    print(json.dumps({'counts': r['counts'], 'changed_ces': sum(p['changed_ces'] for p in r['pages']),
                      'unresolved_ce_pages': len(r['unresolved'])}))
