"""Apply an approved goal sidecar to one dated frozen report; no regeneration."""
from copy import deepcopy
import argparse
import json
from pathlib import Path

import headline_v2
from upgrade_frozen_release import DATA, digest

TARGET_FIELDS = ('target_mtd_gap', 'target_mtd_gap_pct', 'target_mtd_attainment_pct', 'monthly_target')


def repair(page, snapshot, goal):
    page, snapshot = Path(page), Path(snapshot)
    original = page.read_text()
    match = DATA.search(original)
    if not match:
        raise ValueError('not a V2 report')
    payload = json.loads(match.group(1))
    raw = json.loads(snapshot.read_text())
    meta = raw['meta']
    if not page.stem.endswith('-' + meta['week_start']):
        raise ValueError('only an explicit dated report can be repaired')
    view = next(v for v in payload['headlines'] if v['market_slug'] == meta['market_slug'])
    if (view['week_start'], view['week_end']) != (meta['week_start'], meta['week_end']):
        raise ValueError('snapshot/report date mismatch')
    if goal['month'] != view['week_end'][:7] or goal['monthly_goal'] <= 0:
        raise ValueError('wrong goal month or nonpositive goal')
    generated = headline_v2.build_headline_view(raw, goal)
    before = deepcopy(view)
    view['monthly'] = generated['monthly']
    for group, rows in view['movers'].items():
        targets = {str(r['ce_id']): r for r in generated['movers'][group]}
        for row in rows:
            replacement = targets.get(str(row['ce_id']))
            if replacement:
                for key in TARGET_FIELDS:
                    row[key] = replacement[key]
    # Check all parent facts, rankings, comments, OKRs and CE evidence unchanged.
    check = deepcopy(view)
    check['monthly'] = before['monthly']
    for group, rows in check['movers'].items():
        for row, old in zip(rows, before['movers'][group]):
            for key in TARGET_FIELDS:
                if key in old:
                    row[key] = old[key]
                else:
                    row.pop(key, None)
    if check != before:
        raise ValueError('non-goal payload changed')
    serialized = json.dumps(payload, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
    page.write_text(original[:match.start(1)] + serialized + original[match.end(1):])
    receipt = {'page': page.name, 'snapshot_sha256': digest(snapshot), 'page_sha256': digest(page),
               'month': goal['month'], 'monthly_goal': goal['monthly_goal'], 'as_of': goal['as_of'],
               'goal_row_count': goal.get('goal_row_count'), 'reference': goal.get('reference'),
               'non_goal_payload_preserved': True}
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--page', required=True)
    p.add_argument('--snapshot', required=True)
    p.add_argument('--goal-file', required=True)
    p.add_argument('--market', required=True)
    a = p.parse_args()
    goal = json.loads(Path(a.goal_file).read_text())['markets'][a.market]
    r = repair(a.page, a.snapshot, goal)
    output = Path(a.page).parent.parent / (Path(a.page).parent.name + '_goal_receipt.json')
    output.write_text(json.dumps(r, indent=2))
    print(json.dumps(r))
