"""A published status correction must not refresh any report measurement."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import release_okr_status as release


class FrozenOKRStatusRelease(unittest.TestCase):
    def rows(self):
        rows = [{'id': key, 'value': 10, 'current': '10 CEs',
                 'status': ':large_yellow_circle: At risk'}
                for key in release.builder.OKR_IDS]
        rows[3].update(value=48.979455795926775, current='+49.0% YoY',
                       target='+100% YoY', detail='$2.3M vs $1.5M QTD LY',
                       status=':large_green_circle: On track')
        return rows

    def test_preserves_frozen_money_comparisons_and_input(self):
        rows = self.rows()
        before = copy.deepcopy(rows)
        corrected = release.corrected_rows(rows, 'headout', '2026-10-25')
        self.assertEqual(rows, before)
        self.assertEqual(corrected[3]['status'], ':large_yellow_circle: At risk')
        self.assertEqual(release.without_status(corrected), release.without_status(before))

    def test_unknown_baseline_never_invents_a_valid_comparison(self):
        for detail in ('unavailable', '$1K vs $0 QTD LY', '$1K vs — QTD LY'):
            rows = self.rows()
            rows[3]['detail'] = detail
            self.assertEqual(release.corrected_rows(rows, 'headout', '2026-10-25')[3]['status'],
                             'Status unavailable')

    def test_only_selected_status_arrays_and_badge_code_change(self):
        rows = self.rows()
        payload = {'headlines': [{'market_slug': 'headout', 'week_start':'2026-10-25',
                                 'market_okrs': rows, 'revenue':1234.5678,
                                 'diagnostic_buckets':{'untouched':[3,2,1]}}],
                   'notes_url':'/api/review'}
        serialized = json.dumps(payload, separators=(',', ':'))
        original = '<style>OLD</style><script id="report-data" type="application/json">' + serialized + '</script><script>MINI AUDIT</script>'
        patched = release.patch_page(original, '2026-10-25', {'headout':rows}, [('OLD','NEW')])
        actual = json.loads(release.DATA.search(patched)[1])
        self.assertEqual(release.without_status(actual), release.without_status(payload))
        self.assertIn('<script>MINI AUDIT</script>', patched)
        self.assertIn('"revenue":1234.5678', patched)
        self.assertIn('"untouched":[3,2,1]', patched)
        self.assertIn('<style>NEW</style>', patched)
        self.assertNotIn('large_green_circle', patched)

    def test_wrong_week_or_mismatched_sidecar_stops_patch(self):
        rows = self.rows()
        text = '<script id="report-data" type="application/json">' + json.dumps({
            'headlines':[{'market_slug':'headout','week_start':'2026-10-18','market_okrs':rows}]
        }) + '</script>'
        with self.assertRaisesRegex(ValueError, 'Wrong week'):
            release.patch_page(text, '2026-10-25', {'headout':rows}, [])


if __name__ == '__main__':
    unittest.main()
