"""Add RPC/CM1 presentation precision to frozen pages; no regeneration or posting."""
import argparse
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import shutil

from headline_v2 import _fluctuation_roi_precision
from upgrade_frozen_release import DATA, assert_payload_preserved, digest
from review_release_preflight import verify


def stage(source, target, cache):
    source, target, cache = map(Path, (source, target, cache))
    if target.exists():
        raise ValueError('Candidate must be a new directory')
    shutil.copytree(source, target, ignore=shutil.ignore_patterns('node_modules', 'output', '.env*', '.git'))
    receipt = {'source': str(source), 'target': str(target), 'pages': [], 'unchanged_files': [],
               'snapshots': {}, 'roi_available': 0, 'roi_unavailable': 0}

    @lru_cache(maxsize=3)
    def snapshot(slug, week):
        path = cache / f'snapshot_{slug}_{week}.json'
        if not path.is_file():
            return {}
        receipt['snapshots'][path.name] = digest(path)
        return json.loads(path.read_text())

    def enrich(view, raw):
        buckets = view.get('diagnostic_buckets', {}).get('fluctuations', {})
        for lane in ('up', 'down'):
            if lane not in buckets:
                continue
            old = buckets[lane]
            new = _fluctuation_roi_precision(raw, old)
            restored = deepcopy(new)
            for row in restored:
                value = row.pop('roi_wow_pct')
                receipt['roi_available' if value is not None else 'roi_unavailable'] += 1
            if restored != old:
                raise ValueError('Existing bucket fields changed or precision already present')
            buckets[lane] = new
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
        if "Object.prototype.hasOwnProperty.call(row,'roi_wow_pct')" not in original:
            raise ValueError('Precise ROI renderer missing')
        before = deepcopy(payload)
        for view in payload['headlines']:
            enrich(view, snapshot(view['market_slug'], view['week_start']))
        assert_payload_preserved(before, payload)
        serialized = json.dumps(payload, separators=(',', ':'), allow_nan=False).replace('<', '\\u003c')
        updated = original[:match.start(1)] + serialized + original[match.end(1):]
        destination = target / page.name
        destination.write_text(updated)
        modified.add(page.name)
        receipt['pages'].append({'page': page.name, 'sha256': digest(destination),
                                 'existing_payload_preserved': True, 'template_unchanged': True})
    for file in source.rglob('*'):
        if not file.is_file() or any(p in ('node_modules', 'output', '.git') for p in file.parts) or file.name.startswith('.env'):
            continue
        relative = file.relative_to(source)
        if str(relative) not in modified:
            if digest(file) != digest(target / relative):
                raise ValueError(f'Unrelated file changed: {relative}')
            receipt['unchanged_files'].append(str(relative))
    failures = verify(target, 'weekly-report-north-america.html', source)
    if failures:
        raise ValueError(failures)
    receipt['status'] = 'pass'
    (target.parent / (target.name + '_receipt.json')).write_text(json.dumps(receipt, indent=2))
    return receipt


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', required=True)
    p.add_argument('--target', required=True)
    p.add_argument('--cache', default='.cache/weekly_report')
    args = p.parse_args()
    result = stage(args.source, args.target, args.cache)
    print(json.dumps({k: len(v) if isinstance(v, list) else v for k, v in result.items() if k != 'snapshots'}))
