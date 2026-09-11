"""Frozen release permits only approved presentation additions."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import release_roi_levers


class FrozenRoiLeversRelease(unittest.TestCase):
    def test_staging_preserves_notes_api_payload_and_unknown_fields(self):
        template = (ROOT / 'scripts/weekly_report/template/report_v2_template.html').read_text()
        old = '\n'.join(line for line in template.replace('roi_wow_pct', 'legacy_placeholder').splitlines()
                        if not line.strip().startswith('.legacy-disclosure'))
        roi = {'ce_id': '1', 'weeks': [], 'criteria': ['C2']}
        payload = {'notes_url': '/api/review', 'unknown_future_field': [1, None], 'headlines': [
            {'market_slug': 'test', 'week_start': '2026-08-30', 'diagnostic_buckets': {
                'losing_money': {'existing': [roi], 'new': []}}, 'saved_context': ['keep']}]}
        html = old.replace('__REPORT_DATA_JSON__', json.dumps(payload))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, target, cache = root / 'source', root / 'target', root / 'cache'
            source.mkdir(); cache.mkdir()
            (source / 'weekly-report-test.html').write_text(html)
            (source / 'notes.js').write_text('unchanged notes runtime')
            (source / 'weekly_state.json').write_text('{"latest":"2026-08-30"}')
            with patch.object(release_roi_levers.subprocess, 'check_output', return_value=old), \
                 patch.object(release_roi_levers, 'verify', return_value=[]):
                receipt = release_roi_levers.stage(source, target, cache)
            result = json.loads(release_roi_levers.DATA.search((target / 'weekly-report-test.html').read_text()).group(1))
            expected = copy.deepcopy(payload)
            expected['headlines'][0]['diagnostic_buckets']['losing_money']['existing'][0]['roi_wow_pct'] = None
            self.assertEqual(result, expected)
            self.assertEqual((source / 'notes.js').read_bytes(), (target / 'notes.js').read_bytes())
            self.assertEqual((source / 'weekly_state.json').read_bytes(), (target / 'weekly_state.json').read_bytes())
            self.assertEqual(receipt['status'], 'pass')


if __name__ == '__main__':
    unittest.main()
