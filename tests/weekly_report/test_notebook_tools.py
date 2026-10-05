import copy
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/weekly_report"))
from notebook_tools import TOOLS_LINKS, render_tools_nav
from render_v2 import render
from publish_weekly import render_matrix


class NotebookToolsTests(unittest.TestCase):
    def test_only_approved_links_with_safe_new_tabs(self):
        menu = render_tools_nav()
        self.assertEqual(len(TOOLS_LINKS), 4)
        self.assertEqual(menu.count('target="_blank" rel="noopener noreferrer"'), 4)
        self.assertIn('https://okr.headout.com/band-explorer?focus=reverse-kr', menu)
        self.assertIn('Churn Tracker', menu)
        self.assertNotIn('href="#"', menu)
        self.assertNotIn('New CE Performance', menu)
        self.assertNotIn('Seed+', menu)
        self.assertIn("event.key==='Escape'", menu)
        self.assertIn("!tools.contains(event.target)", menu)
        self.assertIn(":focus-visible", menu)

    def test_report_keeps_payload_and_has_one_sticky_menu_below_drawers(self):
        market = json.loads((Path(__file__).parent / "fixtures/snapshot_north_america_2026-08-02.json").read_text())
        original = copy.deepcopy(market)
        result = render([market])
        self.assertEqual(market, original)
        self.assertEqual(result.count('id="notebook-tools"'), 1)
        self.assertNotIn('__NOTEBOOK_TOOLS__', result)
        self.assertIn('.topbar { position:sticky; top:0; z-index:10;', result)
        self.assertIn('.drawer-root { position:fixed; inset:0; z-index:20;', result)
        payload = re.search(r'<script[^>]*id="report-data"[^>]*>(.*?)</script>', result, re.S)
        self.assertIsNotNone(payload)
        self.assertEqual(json.loads(payload.group(1))['schema_version'], 2)

    def test_weekly_home_keeps_navigation(self):
        result = render_matrix({"markets": []}, "2026-09-20", ["2026-09-20"])
        self.assertEqual(result.count('id="notebook-tools"'), 1)
        self.assertIn('href="/"', result)
        self.assertIn('href="/weekly"', result)

    def test_monthly_component_copy_matches_when_sibling_is_available(self):
        monthly = ROOT.parent / "market-monthly-review-skill/engine/notebook_tools.py"
        if not monthly.exists():
            self.skipTest("Monthly repository is not checked out")
        self.assertEqual(monthly.read_bytes(), (ROOT / "scripts/weekly_report/notebook_tools.py").read_bytes())
