"""Exercise Headout's real post-finalizer path without warehouse queries."""
import ast
import copy
import datetime as dt
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import build_global


class GlobalMarketLabelsTests(unittest.TestCase):
    def run_tail(self, snapshot, ces):
        # Execute the actual builder statements after finalize_common. In
        # particular, a lookup removed with legacy sparkline code must not
        # survive only in a test fixture or depend on a module-level global.
        tree = ast.parse(Path(build_global.__file__).read_text())
        builder = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'build_global')
        start = next(i for i, n in enumerate(builder.body)
                     if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                     and isinstance(n.value.func, ast.Attribute)
                     and n.value.func.attr == 'finalize_common') + 1
        wrapper = ast.parse('def finish(snapshot, ces, w0_start):\n    pass\n')
        wrapper.body[0].body = copy.deepcopy(builder.body[start:])
        ast.fix_missing_locations(wrapper)
        context_loader = Mock()
        namespace = dict(vars(build_global))
        namespace.pop('ce_by_id', None)
        namespace['snapshot_finalize'] = types.SimpleNamespace(load_review_context=context_loader)
        exec(compile(wrapper, str(build_global.__file__), 'exec'), namespace)
        result = namespace['finish'](snapshot, ces, dt.date(2026, 9, 6))
        context_loader.assert_called_once()
        return result

    def test_labels_preserve_rows_metrics_and_order(self):
        def row(ce_id):
            return {'ce_id': ce_id, 'revenue': 247.25, 'roi_pct': 127.123, 'rank': 2}
        snapshot = {
            'market_summary': {'weekly': [{'revenue': 987654.321}]},
            'bucket1_fluctuations': [row('18 - Chicago'), row('missing')],
            'buckets_final': {
                'rpc': {'down': [row('3286'), row('18 - Chicago')]},
                'losing_money': {'segments': {
                    'existing': [row('3286')], 'new': [row('18 - Chicago')],
                    'paused': [row('3286')], 'tracking_gap': [row('missing')],
                }},
            },
        }
        before = copy.deepcopy(snapshot)
        ces = [{'ce_id': '3286', 'metadata': {'market': 'CSEE'}},
               {'ce_id': '18 - Chicago', 'metadata': {'market': 'North America'}}]
        result = self.run_tail(snapshot, ces)
        self.assertEqual(result['bucket1_fluctuations'][0]['market'], 'North America')
        self.assertNotIn('market', result['bucket1_fluctuations'][1])
        self.assertEqual(result['buckets_final']['rpc']['down'][0]['market'], 'CSEE')
        for key in ('existing', 'new', 'paused'):
            self.assertIn('market', result['buckets_final']['losing_money']['segments'][key][0])

        def remove_labels(value):
            if isinstance(value, dict):
                return {k: remove_labels(v) for k, v in value.items() if k != 'market'}
            if isinstance(value, list):
                return [remove_labels(v) for v in value]
            return value
        self.assertEqual(remove_labels(result), before)

    def test_empty_buckets_and_unknown_metadata(self):
        snapshot = {'bucket1_fluctuations': [{'ce_id': '1'}], 'buckets_final': {}}
        result = self.run_tail(snapshot, [{'ce_id': '1', 'metadata': {}}])
        self.assertIsNone(result['bucket1_fluctuations'][0]['market'])
        self.assertEqual(result['buckets_final'], {})


if __name__ == '__main__':
    unittest.main()
