"""Offline, status-only correction of one frozen weekly notebook edition.

No queries, rendering, API replacement, Slack writes or deployment. The original
artifact and sidecar remain immutable. Call stage inside the shared writer lock.
"""
from copy import deepcopy
import datetime as dt
import importlib.util
import json
from pathlib import Path
import re
import subprocess

import release_integrity as integrity
import report_storage as storage
from render_v2 import _json_safe
from upgrade_frozen_release import DATA

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "weekly_okr_status_builder", ROOT / "alert/v2/build_market_okr_results.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def corrected_rows(rows, slug, week, approved_targets=False, pro_plus_history=None):
    result = deepcopy(rows)
    if [r['id'] for r in rows] != list(builder.OKR_IDS):
        raise ValueError('Unexpected selected KR inventory')
    date = dt.date.fromisoformat(week)
    if pro_plus_history is not None:
        if approved_targets or slug != 'headout':
            raise ValueError('Pro+ correction is company-only and cannot change GEL targets')
        for row in result[:3]:
            for key in list(row):
                if key.startswith('status'):
                    del row[key]
            row.update(builder._pro_plus_status(slug=slug, week_start=date, row=row,
                                                history=pro_plus_history))
            if row['status'] == builder.STATUS_UNAVAILABLE:
                raise ValueError('Missing verified Pro+ evidence: '+row['status_reason'])
        return result
    for row in result:
        if approved_targets and row['id'] != builder.OKR_IDS[3]:
            continue
        for key in list(row):
            if key.startswith('status'):
                del row[key]
        row.update(status=builder.STATUS_UNAVAILABLE,
                   status_reason='projection_rule_not_verified')
        if row['id'] != builder.OKR_IDS[3]:
            continue
        allocation = None
        if approved_targets:
            if slug == 'headout':
                target = builder.COMPANY_TARGETS.get((date.month-1)//3+1, {}).get(row['id']) if date.year == 2026 else None
            else:
                allocations = json.loads((ROOT/'alert/v2/okr_market_targets.json').read_text())
                allocation = builder._market_gel_target(slug, integrity.config.MARKETS.get(slug), date, allocations)
                target = f"+{allocation['value']:g}% YoY" if allocation else None
            if target is None:
                raise ValueError('No verified exact-grain target for approved correction')
            row['target'] = target
            if allocation:
                row['target_provenance'] = allocation
        # The frozen display retains only rounded baseline dollars. Use its sign
        # solely to prove comparison availability, never to recompute YoY or
        # replace a monetary operand. Fail closed on unknown display formats.
        baseline = re.fullmatch(r'.+ vs \$([\d,.]+)([KM]?) QTD LY', row.get('detail', ''))
        positive_baseline = bool(baseline and float(baseline[1].replace(',', '')) > 0)
        row.update(builder._gel_status(
            slug=slug, year=date.year, week_start=date, value=row.get('value'),
            target=row.get('target'), revenue_ly=1 if positive_baseline else None,
            approved_target=allocation))
    return result


def without_status(value):
    if isinstance(value, dict):
        return {k: without_status(v) for k, v in value.items() if not k.startswith('status')}
    if isinstance(value, list):
        return [without_status(v) for v in value]
    return value


def patch_page(original, week, expected, replacements, approved_targets=False, pro_plus_history=None):
    match = DATA.search(original)
    if not match:
        raise ValueError('Missing report payload')
    payload = json.loads(match[1])
    before = deepcopy(payload)
    for view in payload['headlines']:
        slug = view['market_slug']
        if view['week_start'] != week or view.get('market_okrs') != expected[slug]:
            raise ValueError('Wrong week or frozen OKR evidence mismatch')
        view['market_okrs'] = corrected_rows(view['market_okrs'], slug, week, approved_targets, pro_plus_history)
    # Only status fields inside selected KR rows can change, not any other data.
    restored = deepcopy(payload)
    for old_view, new_view in zip(before['headlines'], restored['headlines']):
        comparison = deepcopy(new_view['market_okrs'])
        if pro_plus_history is not None and old_view['market_okrs'][3] != comparison[3]:
            raise ValueError('GEL changed during company Pro+ correction')
        if approved_targets:
            for old_row, new_row in zip(old_view['market_okrs'], comparison):
                if old_row['id'] != builder.OKR_IDS[3]:
                    if new_row != old_row:
                        raise ValueError('Unselected KR changed')
                    continue
                for key in ('target', 'target_provenance'):
                    if key in old_row:
                        new_row[key] = old_row[key]
                    else:
                        new_row.pop(key, None)
        if without_status(old_view['market_okrs']) != without_status(comparison):
            raise ValueError('OKR measurement changed')
        new_view['market_okrs'] = old_view['market_okrs']
    if restored != before:
        raise ValueError('Report payload changed outside OKR status')
    # Preserve every original data byte apart from the selected OKR arrays.
    # JSONDecoder spans avoid reserializing unrelated metrics/formatting.
    text = match[1]
    for old_view, new_view in zip(before['headlines'], payload['headlines']):
        needle = '"market_okrs":'
        # Find each array by matching its fully decoded original value.
        candidates = []
        offset = 0
        while (pos := text.find(needle, offset)) >= 0:
            start = pos + len(needle)
            while text[start].isspace():
                start += 1
            value, length = json.JSONDecoder().raw_decode(text[start:])
            if value == old_view['market_okrs']:
                candidates.append((start, start + length))
            offset = start + length
        if len(candidates) != 1:
            raise ValueError('Ambiguous OKR array replacement')
        start, end = candidates[0]
        encoded = json.dumps(new_view['market_okrs'], ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
        text = text[:start] + encoded + text[end:]
    updated = original[:match.start(1)] + text + original[match.end(1):]
    for old, new in replacements:
        if updated.count(old) != 1:
            raise ValueError('Unexpected badge renderer/CSS')
        updated = updated.replace(old, new, 1)
    return updated


def stage(base, target, week, sidecar, base_receipt, original_commit, approved_targets=False, pro_plus_history=None):
    base, target, sidecar = map(Path, (base, target, sidecar))
    evidence = json.loads(Path(base_receipt).read_text())
    if evidence['status'] != 'verified' or Path(evidence['notebook']) != base:
        raise ValueError('Unverified baseline')
    if integrity.files(base) != evidence['files']:
        raise ValueError('Baseline no longer matches its verification receipt')
    frozen = json.loads(sidecar.read_text())
    if frozen['week_start'] != week:
        raise ValueError('Sidecar week mismatch')
    template_path = 'scripts/weekly_report/template/report_v2_template.html'
    old_template = subprocess.check_output(
        ['git', 'show', f'{original_commit}:{template_path}'], text=True)
    new_template = (ROOT / template_path).read_text()
    replacements = []
    prefixes = () if pro_plus_history is not None else ('        grid.innerHTML=rows.map(row=>`<article class="okr-card"',) if approved_targets else (
        '    .okr-status.risk {', '        const statusClass=row=>')
    for prefix in prefixes:
        old = next(line for line in old_template.splitlines() if line.startswith(prefix))
        new = next(line for line in new_template.splitlines() if line.startswith(prefix))
        if prefix.startswith('    .okr-status'):
            new += '\n' + next(line for line in new_template.splitlines()
                                if line.startswith('    .okr-status.neutral {'))
        replacements.append((old, new))
    integrity.seed(base, target)
    pages = []
    names = integrity.report_names(week)
    if pro_plus_history is not None:
        names = [f'weekly-report-headout{suffix}.html' for suffix in ('', '-'+week)]
    if approved_targets:
        routes = [integrity.LEDGER_SLUG[slug] for slug in ('headout','italy','france','iberia')]
        names = [f'weekly-report-{route}{suffix}.html' for route in routes
                 for suffix in ('', '-'+week)]
    for name in names:
        original = (base / name).read_text()
        expected = ({v['market_slug']:v['market_okrs'] for v in json.loads(DATA.search(original)[1])['headlines']}
                    if approved_targets or pro_plus_history is not None else _json_safe(frozen['markets']))
        updated = patch_page(original, week, expected, replacements, approved_targets, pro_plus_history)
        (target / name).write_text(updated)
        pages.append(name)
    manifest = integrity.verify_artifact(base, target, week)
    before, after = integrity.files(base), integrity.files(target)
    changed = sorted(name for name in before if before[name] != after[name])
    if changed != sorted(pages) or before.keys() != after.keys():
        raise ValueError('Unexpected notebook change')
    result = {'schema': 'weekly-okr-status-correction/v1', 'status': 'staged',
              'week': week, 'base_notebook': str(base), 'notebook': str(target),
              'base_deployment_id': evidence['deployment_id'],
              'base_receipt': str(base_receipt), 'source_commit': subprocess.check_output(
                  ['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'changed_files': changed, 'preserved_files': len(before) - len(changed),
              'files': after, 'sidecar_sha256': storage.sha256(sidecar),
              'data_queries': False, 'snapshots_modified': False,
              'mini_audit_files_modified': False, 'old_editions_modified': False}
    if approved_targets:
        result.update(mode='approved-exact-grain-gel-targets',
                      target_source_sha256=storage.sha256(ROOT/'alert/v2/okr_market_targets.json'))
    if pro_plus_history is not None:
        result.update(mode='verified-company-pro-plus-status', status_history=pro_plus_history)
    return manifest, result
