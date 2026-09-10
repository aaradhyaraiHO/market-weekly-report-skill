"""Stage current UI against frozen production payloads, without metric refreshes.

No network calls, deploys, Slack sends, or Sheet mutations. Reuses the canonical
drawer view-model producer only for additive YoY/platform enrichment. Existing
metric operands must match before attaching it; all other report JSON is retained.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import datetime as dt
from functools import lru_cache
import hashlib
import html
import json
from pathlib import Path
import re
import shutil

import config
import headline_v2
import inject_review_view
import publish_weekly
import release_v2
import render_v2
import review_release_preflight

DATA = re.compile(r'<script id="report-data" type="application/json">(.*?)</script>', re.S)
ADDITIONS = {'ly_w0', 'yoy_pct', 'breakdown'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attach_metrics(old, new):
    """Never change a previously displayed parent metric or comparison."""
    result = deepcopy(old)
    for group, rows in result.items():
        by_key = {r['key']: r for r in new.get(group, [])}
        for row in rows:
            candidate = by_key.get(row['key'])
            if not candidate:
                continue
            for key in ('w0', 'wm1', 'delta_abs', 'delta_pct', 'series'):
                if row.get(key) != candidate.get(key):
                    raise ValueError(f"frozen metric drift: {group}/{row['key']}/{key}")
            for key in ADDITIONS:
                if key in candidate:
                    row[key] = candidate[key]
    return result


def attach_frozen_mover_dollars(view):
    """Add display-only LY dollars from the exact CE operands already published."""
    ces = {str(ce['ce_id']): ce for ce in view.get('all_ces', [])}
    for rows in view.get('movers', {}).values():
        for row in rows:
            ce = ces.get(str(row['ce_id']))
            ly = ce.get('weekly_ly_revenue') if ce else None
            current = row.get('revenue')
            if ce and current != ce.get('revenue'):
                raise ValueError(f"frozen mover revenue mismatch: {row['ce_id']}")
            value = current - ly if current is not None and ly is not None else None
            if 'yoy_abs' in row and row['yoy_abs'] != value:
                raise ValueError(f"frozen mover dollar mismatch: {row['ce_id']}")
            row['yoy_abs'] = value
    for child in view.get('country_views', {}).values():
        attach_frozen_mover_dollars(child)


def assert_payload_preserved(old, new, path='payload'):
    """Every pre-existing value, record and ordering must remain unchanged."""
    if isinstance(old, dict):
        for key, value in old.items():
            if key not in new:
                raise ValueError(f'{path}.{key}: removed')
            assert_payload_preserved(value, new[key], f'{path}.{key}')
    elif isinstance(old, list):
        if len(old) != len(new):
            raise ValueError(f'{path}: length changed')
        for i, value in enumerate(old):
            assert_payload_preserved(value, new[i], f'{path}[{i}]')
    elif old != new:
        raise ValueError(f'{path}: changed')


def stage_proxy(source, target):
    """Replace only the review proxy; preserve every published page byte-for-byte."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if target.exists() or source == target:
        raise ValueError('target must be a new artifact directory')
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('node_modules', 'output', '.env*'))
    proxy = Path(__file__).parent / 'notes' / 'review_proxy_api.js'
    shutil.copyfile(proxy, target / 'api' / 'review.js')
    receipt = {'source': str(source), 'target': str(target), 'mode': 'review-proxy-only',
               'proxy_sha256': digest(proxy), 'pages': [], 'unchanged_files': []}
    for original in sorted(source.rglob('*')):
        if not original.is_file() or 'node_modules' in original.parts or 'output' in original.parts:
            continue
        relative = str(original.relative_to(source))
        if original.name.startswith('.env') or relative == 'api/review.js':
            continue
        if not (target / relative).is_file() or digest(original) != digest(target / relative):
            raise ValueError(f'unrelated artifact changed: {relative}')
        receipt['unchanged_files'].append(relative)
        if original.suffix == '.html':
            receipt['pages'].append({'page': relative, 'sha256': digest(original), 'byte_preserved': True})
    failures = review_release_preflight.verify(target, 'weekly-report-north-america.html', source)
    if failures:
        raise ValueError(failures)
    receipt['status'] = 'pass'
    (target.parent / (target.name + '_receipt.json')).write_text(json.dumps(receipt, indent=2))
    return receipt


def stage_presentation(source, target, resume=False):
    """Mid-week presentation cutover: no snapshot, ledger, date or source refresh."""
    source, target = Path(source).resolve(), Path(target).resolve()
    if (target.exists() and not resume) or source == target:
        raise ValueError('target must be a new artifact directory')
    if not target.exists():
        shutil.copytree(source, target, ignore=shutil.ignore_patterns('node_modules', 'output', '.env*'))
    template = Path(render_v2.TEMPLATE).read_text()
    receipt = {'source': str(source), 'target': str(target), 'mode': 'presentation-only',
               'pages': [], 'source_hashes': {}, 'unchanged_files': []}
    here = Path(__file__).parent
    for name in ('template/report_v2_template.html', 'inject_review_view.py',
                 'review/review-view.js', 'review/review-view.css', 'notes/review_client.js',
                 'notes/review_apps_script.js', 'notes/review_proxy_api.js',
                 'notes/review_summary_api.js', 'notes/review_extract_api.js',
                 'lib/review_ai_provider.mjs', 'lib/review_meeting_import.mjs'):
        receipt['source_hashes'][name] = digest(here / name)
    modified = set()
    for original in sorted(source.glob('weekly-report-*.html')):
        old = original.read_text()
        match = DATA.search(old)
        if not match:
            continue
        payload = json.loads(match.group(1))
        if not isinstance(payload.get('headlines'), list):
            continue  # Historical V1 pages are preserved byte-for-byte.
        before = deepcopy(payload)
        for view in payload['headlines']:
            attach_frozen_mover_dollars(view)
        assert_payload_preserved(before, payload)
        names = ' · '.join(v['market'] for v in payload['headlines'])
        serialized = json.dumps(render_v2._json_safe(payload), separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
        output = template.replace('__REPORT_DATA_JSON__', serialized).replace('__TITLE__', html.escape('Weekly V2 — ' + names))
        preview = re.search(r'<aside\b[^>]*data-incomplete-week="true".*?</aside>', old, re.S)
        if preview:
            output = output.replace('<main class="main">', '<main class="main">' + preview.group(0), 1)
        page = target / original.name
        page.write_text(output)
        if inject_review_view.HEADOUT_RE.match(page.name):
            inject_review_view.remove_review(page)
        elif not inject_review_view.inject(page, target):
            raise ValueError(f'failed Mini Audit injection: {page.name}')
        modified.add(page.name)
        receipt['pages'].append({'page': page.name, 'sha256': digest(page),
                                 'original_values_preserved': True, 'preview_preserved': bool(preview)})
    inject_review_view.stage_review_api(target)
    for name in ('api/review.js', 'api/review-summary.js', 'api/review-extract.js',
                 'lib/review_ai_provider.mjs', 'lib/review_meeting_import.mjs'):
        modified.add(name)
    for original in sorted(source.rglob('*')):
        if not original.is_file() or 'node_modules' in original.parts or 'output' in original.parts:
            continue
        relative = str(original.relative_to(source))
        if original.name.startswith('.env') or relative in modified:
            continue
        if not (target / relative).is_file() or digest(original) != digest(target / relative):
            raise ValueError(f'unrelated artifact changed: {relative}')
        receipt['unchanged_files'].append(relative)
    failures = review_release_preflight.verify(target, 'weekly-report-north-america.html', source)
    if failures:
        raise ValueError(failures)
    receipt['status'] = 'pass'
    (target.parent / (target.name + '_receipt.json')).write_text(json.dumps(receipt, indent=2))
    return receipt


def stage(source, target, cache, latest, resume=False):
    source, target, cache = map(lambda p: Path(p).resolve(), (source, target, cache))
    if (target.exists() and not resume) or source == target:
        raise ValueError('target must be a new artifact directory')
    publish_weekly.require_completed_week(latest)
    if not target.exists():
        shutil.copytree(source, target, ignore=shutil.ignore_patterns('node_modules', 'output', '.env*'))
    template = Path(render_v2.TEMPLATE).read_text()
    receipt = {'latest': latest, 'source': str(source), 'target': str(target),
               'pages': [], 'parity': [], 'snapshot_hashes': {}, 'source_hashes': {}}
    for name in ('template/report_v2_template.html', 'review/review-view.js',
                 'review/review-view.css', 'notes/review_apps_script.js'):
        receipt['source_hashes'][name] = digest(Path(__file__).parent / name)

    @lru_cache(maxsize=2)
    def snapshot(slug, week):
        p = cache / f'snapshot_{slug}_{week}.json'
        if not p.exists():
            return None
        receipt['snapshot_hashes'][p.name] = digest(p)
        return json.loads(p.read_text())

    def enrich(view, ce_map):
        for ce in view.get('all_ces', []):
            raw = ce_map.get(str(ce['ce_id']))
            if raw is None:
                raise ValueError(f"missing frozen CE {ce['ce_id']}")
            metrics = headline_v2._ce_drawer_metrics(
                sorted(raw.get('weekly', []), key=lambda r: r.get('week', '')),
                raw.get('weekly_ly', []), raw.get('funnel'))
            ce['drawer_metrics'] = attach_metrics(ce.get('drawer_metrics', {}), metrics)
        for child in view.get('country_views', {}).values():
            enrich(child, ce_map)

    # Upgrade dated pages before current aliases, whose contents are replaced below.
    pages = sorted(target.glob('weekly-report-*.html'))
    for page in pages:
        if not re.search(r'-\d{4}-\d{2}-\d{2}\.html$', page.name):
            continue
        old = (source / page.name).read_text()
        match = DATA.search(old)
        if not match:  # preserve historical V1 archives byte-for-byte
            continue
        payload = json.loads(match.group(1))
        if not isinstance(payload.get('headlines'), list):
            continue
        for view in payload['headlines']:
            # Older historical payloads may predate subsequent snapshot repairs.
            # Upgrade their presentation only; never rehydrate them from newer data.
            snap = snapshot(view['market_slug'], view['week_start']) if view['week_start'] >= latest else None
            if snap is not None:
                enrich(view, {str(ce['ce_id']): ce for ce in snap.get('ces', [])})
                parity = release_v2.verify_market(snap, view)
                if parity['failures']:
                    raise ValueError(f"{page.name}: {parity['failures']}")
                receipt['parity'].append({k: parity[k] for k in ('market_slug','week_start','status','failures')})
        names = ' · '.join(v['market'] for v in payload['headlines'])
        serialized = json.dumps(render_v2._json_safe(payload), separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
        output = template.replace('__REPORT_DATA_JSON__', serialized).replace('__TITLE__', html.escape('Weekly V2 — ' + names))
        incomplete = any(v['week_start'] > latest for v in payload['headlines'])
        if incomplete:
            warning = ('<aside role="note" data-incomplete-week="true" style="padding:12px 24px;'
                       'background:var(--purple-soft);color:var(--purple-dark);font-size:14px;line-height:1.5">'
                       '<strong>Preview · incomplete week.</strong> These frozen figures are not a completed-week report. '
                       'Use the latest report for the last completed week.</aside>')
            output = output.replace('<main class="main">', '<main class="main">' + warning, 1)
        page.write_text(output)
        if inject_review_view.HEADOUT_RE.match(page.name):
            inject_review_view.remove_review(page)
        elif not inject_review_view.inject(page, target):
            raise ValueError(f'failed Mini Audit injection: {page.name}')
        receipt['pages'].append({'page':page.name, 'sha256':digest(page), 'incomplete_preview':incomplete})

    # Every current alias is an exact copy of the completed-week dated artifact.
    for page in pages:
        if re.search(r'-\d{4}-\d{2}-\d{2}\.html$', page.name):
            continue
        dated = target / f'{page.stem}-{latest}.html'
        if not dated.exists():
            raise ValueError(f'missing completed-week alias source: {dated.name}')
        shutil.copyfile(dated, page)
    publish_weekly.stage_v2_proxies(target)

    # Rebuild only Weekly ledger state from unchanged completed-week snapshots.
    state = publish_weekly.load_state(target)
    for slug in config.MARKETS:
        snap = snapshot(slug, latest)
        if snap is None:
            raise ValueError(f'missing completed snapshot {slug}')
        ledger_slug, name, flag, region = publish_weekly.MARKET_META[slug]
        series = publish_weekly.weekly_series(snap, publish_weekly.N_COLS)
        publish_weekly.upsert(state, dict(slug=ledger_slug,name=name,flag=flag,region=region,
            report_path=f'weekly-report-{ledger_slug}.html',series=series,
            spark=publish_weekly._sparkline([s['rev'] for s in series])))
    ho = snapshot('headout', latest)
    series = publish_weekly.weekly_series(ho, publish_weekly.N_COLS)
    state['headout'] = dict(report_path='weekly-report-headout.html',series=series,
        spark=publish_weekly._sparkline([s['rev'] for s in series]),n_markets=ho['meta'].get('n_markets'))
    weeks = sorted({s['week'] for m in state['markets'] for s in m.get('series', [])})[-publish_weekly.N_COLS:]
    if any(w > latest for w in weeks):
        raise ValueError('future week retained in ledger')
    state['edition'] = {'week':latest,'cols':weeks}
    (target/'weekly_state.json').write_text(json.dumps(state,indent=2,ensure_ascii=False))
    (target/'weekly.html').write_text(publish_weekly.render_matrix(state,latest,weeks,target))
    failures = review_release_preflight.verify(target,'weekly-report-north-america.html',source)
    if failures:
        raise ValueError(failures)
    # Monthly and V1 artifacts must not change as a side effect of weekly packaging.
    for page in source.glob('*.html'):
        if page.name == 'weekly.html':
            continue
        if not page.name.startswith('weekly-report-') or not DATA.search(page.read_text()):
            if digest(page) != digest(target/page.name):
                raise ValueError(f'unrelated artifact changed: {page.name}')
    receipt['status'] = 'pass'
    (target.parent / (target.name + '_receipt.json')).write_text(json.dumps(receipt,indent=2))
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',required=True,type=Path)
    p.add_argument('--target',required=True,type=Path)
    p.add_argument('--cache',default=Path('.cache/weekly_report'),type=Path)
    p.add_argument('--latest',default=config.latest_complete_week().isoformat())
    p.add_argument('--resume',action='store_true',help='retry this known staging directory from unchanged source artifacts')
    p.add_argument('--presentation-only',action='store_true',help='preserve all published metrics, ledger and dates for a mid-week UI release')
    p.add_argument('--review-proxy-only',action='store_true',help='replace only api/review.js; preserve all published pages byte-for-byte')
    a = p.parse_args()
    if a.review_proxy_only:
        r = stage_proxy(a.source,a.target)
    else:
        r = stage_presentation(a.source,a.target,a.resume) if a.presentation_only else stage(a.source,a.target,a.cache,a.latest,a.resume)
    print(json.dumps({'status':r['status'],'pages':len(r['pages']),'parity':len(r.get('parity',[])),'latest':r.get('latest'),'mode':r.get('mode')}))
