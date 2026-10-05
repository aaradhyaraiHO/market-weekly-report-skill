import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/weekly_report'))
from stage_tools_navigation import patch_page


class StageToolsNavigationTests(unittest.TestCase):
    def test_patch_keeps_data_and_existing_markup_in_each_layout(self):
        data = '<script id="report-data" type="application/json">{"revenue":123,"notes":"keep"}</script>'
        bodies = [
            '<header class="topbar"><div>Market</div><div class="filters">Country</div></header>',
            '<!-- NAV --><div style="position:sticky"><div class="wrap"><div>Monthly</div></div></div>',
            '<!-- NAV --><div style="position:sticky"><div style="display:flex"><div>Market</div><div class="mm-topnav">All CEs</div></div></div>',
            '<div class="page"><div class="masthead">Archive</div></div>',
        ]
        for body in bodies:
            with self.subTest(body=body):
                page = '<html><head></head><body>' + body + data + '</body></html>'
                patched, _ = patch_page(page)
                self.assertIn(data, patched)
                self.assertEqual(patched.count('id="notebook-tools"'), 1)
                if 'class="page"' in body:
                    self.assertIn('.jumpnav{top:61px;z-index:9}', patched)
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    patch_page(patched)

    def test_unknown_page_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            patch_page('<html><body>Not a notebook</body></html>')
