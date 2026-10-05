"""Offline, frozen-source storage rehearsal. Never deploys, queries BQ or posts.

Requires an empty output path outside the report cache and an explicit complete
base. Uses real renderers/publishers, comparing old copy behavior with CoW.
Production source files are hashed before/after. Keeps rehearsal receipts.
"""
import argparse
from collections import Counter
from contextlib import ExitStack
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

import config
import release_integrity as integrity
import release_v2
import render
import render_v2
import publish_weekly as publish
import report_storage as storage


def run(args):
    root = Path(__file__).resolve().parents[2]
    cache = root / '.cache/weekly_report'
    base, out = storage.no_symlinks(args.base), storage.no_symlinks(args.out)
    if out.exists() or out == cache or cache in out.parents or out in base.parents:
        raise ValueError('Use a new isolated output directory outside the live cache')
    source_json = sorted(args.monthly_data.glob('*.json'))
    snapshots = [cache / f'snapshot_{s}_{args.week}.json' for s in (*config.MARKETS, 'headout')]
    sources = snapshots + source_json + [args.goals, args.okrs]
    source_hashes = {str(p): storage.sha256(p) for p in sources}
    before = integrity.files(base)
    methods = Counter()
    original_copy = storage.copy_independent

    def observed_copy(source, target):
        method = original_copy(source, target)
        methods[method] += 1
        return method

    with storage.release_guard('frozen-storage-rehearsal', [out, cache, args.monthly_data], baseline=base):
        out.mkdir(parents=True)
        reports = out / 'weekly-rendered'
        result = release_v2.release(snapshots, reports, args.goals, False, args.okrs)
        if result['status'] != 'pass':
            raise ValueError('Frozen weekly parity failed')
        members = render.load_markets([str(cache / f'snapshot_{s}_{args.week}.json') for s in ('csee', 'nordics')])
        group = config.MARKET_REPORT_GROUPS['csee_nordics']
        (reports / f'report_csee_nordics_{args.week}.html').write_text(render_v2.render(
            members, goals=render_v2.load_goals(reports / 'goals_v2.json'),
            okr_results=render_v2.load_okr_results(args.okrs),
            report_group={'slug': 'csee_nordics', 'name': group['name']}))
        stages = [out / 'old-copy-notebook', out / 'cow-notebook']
        for stage, cow in zip(stages, (False, True)):
            with patch.object(storage, 'copy_independent', side_effect=observed_copy):
                integrity.seed(base, stage)
            with ExitStack() as stack:
                stack.enter_context(patch.dict(os.environ, {'MMR_NOTEBOOK_DIR': str(stage)}))
                stack.enter_context(patch.object(publish, 'REPORT_DIR_V2', reports))
                stack.enter_context(patch.object(publish, 'copy_independent', observed_copy if cow else shutil.copyfile))
                if cow:
                    stack.enter_context(patch.object(storage, 'copy_independent', side_effect=observed_copy))
                else:
                    stack.enter_context(patch.object(publish, 'share_identical_route_storage', return_value=None))
                publish.main(['all', '--week', args.week, '--renderer', 'v2', '--skip-perf-sheet'])
            manifest = integrity.verify_artifact(base, stage, args.week)
            (out / ('weekly-cow-manifest.json' if cow else 'weekly-old-copy-manifest.json')).write_text(json.dumps(manifest, indent=2))
        if integrity.files(stages[0]) != integrity.files(stages[1]):
            raise ValueError('Weekly publication changed bytes')
        weekly_preserved = integrity.files(stages[1])
        # Monthly data is frozen and cloned into a private artifact directory.
        # The renderer/publisher performs no regeneration or source queries.
        data = out / 'monthly-data'
        data.mkdir()
        for source in source_json:
            observed_copy(source, data / source.name)
        env = dict(os.environ, MMR_DATA_DIR=str(data), MMR_NOTEBOOK_DIR=str(stages[1]))
        engine = args.monthly_repo / 'engine'
        # Each target's final render includes its existing Ledger back-link.
        sys.path.insert(0, str(engine))
        from market_registry import report_names
        monthly_results = []
        mutable = {'index.html', 'ledger_state.json'}
        for market in [*report_names(), 'overall']:
            from market_registry import slugify
            slug = slugify(market)
            build_env = dict(env, MMR_LEDGER_HOME='/')
            subprocess.run([sys.executable, str(engine / 'build/build_report_v2.py'), market, args.month], env=build_env, check=True)
            built = data / 'build' / f'report-v2-{slug}-{args.month}.html'
            expected = storage.sha256(built)
            # Previously this was a second render; verify deterministic output
            # and final publication against the same frozen inputs.
            subprocess.run([sys.executable, str(engine / 'publish_ledger.py'), market, args.month], env=env, check=True)
            name = 'report.html' if slug == 'italy' else f'report-{slug}.html'
            actual = stages[1] / name
            assert storage.sha256(built) == expected == storage.sha256(actual), slug
            assert built.stat().st_ino != actual.stat().st_ino
            mutable.add(name)
            monthly_results.append({'market': slug, 'sha256': expected, 'bytes': actual.stat().st_size})
        after_monthly = integrity.files(stages[1])
        assert all(after_monthly.get(n) == sha for n, sha in weekly_preserved.items() if n not in mutable)
        assert not (after_monthly.keys() - weekly_preserved.keys() - mutable)
        # Rollback is another independently writable clone, never a source swap.
        rollback = out / 'rollback-rehearsal'
        with patch.object(storage, 'copy_independent', side_effect=observed_copy):
            integrity.seed(base, rollback)
        assert integrity.files(rollback) == before
        assert integrity.files(base) == before
        assert all(storage.sha256(Path(p)) == sha for p, sha in source_hashes.items())
        receipt = {'status': 'pass', 'mode': 'offline frozen source; no live writes or queries',
                   'week': args.week, 'month': args.month,
                   'weekly_market_parity_checks': len(result['markets']),
                   'weekly_routes_byte_identical_old_vs_cow': len(integrity.report_names(args.week)),
                   'monthly_reports_byte_identical': monthly_results,
                   'source_files_unchanged': len(source_hashes),
                   'base_and_rollback_files_unchanged': len(before),
                   'monthly_preserved_weekly_api_and_history_files': len(weekly_preserved.keys() - mutable),
                   'copy_methods_observed_in_parent': dict(methods),
                   'weekly_producer_html_bytes': sum(p.stat().st_size for p in reports.glob('*.html')),
                   'weekly_new_canonical_html_bytes': sum((stages[0] / n).stat().st_size for n in integrity.report_names(args.week) if n.endswith(args.week + '.html')),
                   'weekly_snapshot_bytes': sum(p.stat().st_size for p in snapshots),
                   'monthly_canonical_html_bytes': sum(r['bytes'] for r in monthly_results),
                   'mini_audit_backend_writes': 0, 'production_deployments': 0, 'slack_writes': 0,
                   'limits': ['Frozen-source rehearsal, not fresh BQ generation or a live Mini Audit interaction test',
                              'Monthly renderer contains pre-existing user edits; compared identical working-tree renderers, not unrelated HEAD metrics',
                              'APFS allocated-size sums do not measure unique shared extents']}
        (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'out', 'monthly-data', 'monthly-repo', 'goals', 'okrs'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--week', required=True)
    p.add_argument('--month', required=True)
    run(p.parse_args())
