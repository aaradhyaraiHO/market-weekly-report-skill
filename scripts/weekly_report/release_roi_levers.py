"""Stage only ROI precision and Levers disclosure over a frozen live artifact.

Offline, no external writes. Preserve all existing payload values and all other
site files, including Mini Audit, API handlers, links and incomplete-week notices.
"""
import argparse
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import shutil
import subprocess

from headline_v2 import _losing_money_roi_precision
from upgrade_frozen_release import DATA, assert_payload_preserved, digest
from review_release_preflight import verify


def function_block(text, start, end):
    return text[text.index(start):text.index(end)]


def stage(source, target, cache):
    source, target, cache = map(Path, (source, target, cache))
    if target.exists():
        raise ValueError('Candidate must be a new directory')
    template_path = 'scripts/weekly_report/template/report_v2_template.html'
    old_template = subprocess.check_output(['git', 'show', f'a67c168:{template_path}'], text=True)
    template = Path(template_path).read_text()
    spans = [('      function renderLevers(item) {', '      const NOTES_URL='),
             ('      function bucketMetricCell(', '      function losingCriteria(')]
    replacements = [(function_block(old_template, *span), function_block(template, *span)) for span in spans]
    css = '\n'.join(line for line in template.splitlines() if line.strip().startswith('.legacy-disclosure'))
    if not css:
        raise ValueError('Disclosure CSS missing')
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('node_modules', 'output', '.env*', '.git'))
    receipt = {'source': str(source), 'target': str(target), 'pages': [], 'unchanged_files': [],
               'snapshots': {}, 'roi_available': 0, 'roi_unavailable': 0}

    @lru_cache(maxsize=3)
    def snapshot(slug, week):
        path = cache / f'snapshot_{slug}_{week}.json'
        if not path.is_file():
            return {'ces': []}
        receipt['snapshots'][path.name] = digest(path)
        return json.loads(path.read_text())

    def enrich(view, raw):
        losing = view.get('diagnostic_buckets', {}).get('losing_money', {})
        for lane in ('existing', 'new'):
            if lane not in losing:
                continue
            old = losing[lane]
            new = _losing_money_roi_precision(raw, old)
            restored = deepcopy(new)
            for row in restored:
                value = row.pop('roi_wow_pct')
                receipt['roi_available' if value is not None else 'roi_unavailable'] += 1
            if restored != old:
                raise ValueError('Existing bucket data changed')
            losing[lane] = new
        for child in view.get('country_views', {}).values():
            enrich(child, raw)

    modified = set()
    for page in sorted(source.glob('weekly-report-*.html')):
        original = page.read_text()
        match = DATA.search(original)
        if not match:
            continue
        payload = json.loads(match.group(1))
        if not isinstance(payload.get('headlines'), list):
            continue
        old_payload = deepcopy(payload)
        for view in payload['headlines']:
            enrich(view, snapshot(view['market_slug'], view['week_start']))
        assert_payload_preserved(old_payload, payload)
        # Assert every byte outside the approved function/CSS/data replacements.
        updated = original
        for before, after in replacements:
            if updated.count(before) != 1:
                raise ValueError(f'{page.name}: unexpected original renderer')
            updated = updated.replace(before, after, 1)
        updated = updated.replace('</style>', css + '\n</style>', 1)
        restored = updated.replace(css + '\n</style>', '</style>', 1)
        for before, after in reversed(replacements):
            restored = restored.replace(after, before, 1)
        if restored != original:
            raise ValueError('Unexpected presentation change')
        match = DATA.search(updated)
        serialized = json.dumps(payload, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
        updated = updated[:match.start(1)] + serialized + updated[match.end(1):]
        destination = target / page.name
        destination.write_text(updated)
        modified.add(page.name)
        receipt['pages'].append({'page': page.name, 'sha256': digest(destination), 'existing_payload_preserved': True})
    for page in source.rglob('*'):
        if not page.is_file() or any(part in ('node_modules', 'output', '.git') for part in page.parts) or page.name.startswith('.env'):
            continue
        relative = page.relative_to(source)
        if str(relative) in modified:
            continue
        if digest(page) != digest(target / relative):
            raise ValueError(f'Unrelated file changed: {relative}')
        receipt['unchanged_files'].append(str(relative))
    failures = verify(target, 'weekly-report-north-america.html', source)
    if failures:
        raise ValueError(failures)
    receipt['status'] = 'pass'
    (target.parent / (target.name + '_receipt.json')).write_text(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--target', required=True)
    parser.add_argument('--cache', default='.cache/weekly_report')
    args = parser.parse_args()
    receipt = stage(args.source, args.target, args.cache)
    print(json.dumps({'status': receipt['status'], 'pages': len(receipt['pages']),
                      'unchanged_files': len(receipt['unchanged_files']),
                      'roi_available': receipt['roi_available'], 'roi_unavailable': receipt['roi_unavailable']}))
