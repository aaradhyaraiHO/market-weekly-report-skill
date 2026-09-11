"""RPC frozen patch preserves the complete pre-existing report and integrations."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import release_rpc_precision


class FrozenRpcRelease(unittest.TestCase):
    def test_only_optional_fluctuation_field_is_added(self):
        row = {'ce_id': '1', 'weeks': [], 'verdict': 'watch'}
        payload = {'notes_url': '/api/review', 'headlines': [
            {'market_slug': 'test', 'week_start': '2026-08-30', 'diagnostic_buckets': {
                'fluctuations': {'down': [row], 'up': []},
                'losing_money': {'existing': [{'roi_wow_pct': -6.1297}]}}}]}
        template = (ROOT / 'scripts/weekly_report/template/report_v2_template.html').read_text()
        html = template.replace('__REPORT_DATA_JSON__', json.dumps(payload))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, target, cache = root/'source', root/'target', root/'cache'
            source.mkdir(); cache.mkdir()
            (source/'weekly-report-test.html').write_text(html)
            (source/'notes.js').write_text('unchanged')
            with patch.object(release_rpc_precision, 'verify', return_value=[]):
                result = release_rpc_precision.stage(source, target, cache)
            updated = (target/'weekly-report-test.html').read_text()
            old_match = release_rpc_precision.DATA.search(html)
            new_match = release_rpc_precision.DATA.search(updated)
            expected = copy.deepcopy(payload)
            expected['headlines'][0]['diagnostic_buckets']['fluctuations']['down'][0]['roi_wow_pct'] = None
            self.assertEqual(json.loads(new_match.group(1)), expected)
            self.assertEqual(html[:old_match.start(1)], updated[:new_match.start(1)])
            self.assertEqual(html[old_match.end(1):], updated[new_match.end(1):])
            self.assertEqual((source/'notes.js').read_bytes(), (target/'notes.js').read_bytes())
            self.assertEqual(result['roi_unavailable'], 1)


if __name__ == '__main__':
    unittest.main()
