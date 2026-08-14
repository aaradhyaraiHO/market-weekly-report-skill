from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
FIXTURE = Path(__file__).parent / "fixtures" / "snapshot_north_america_2026-08-02.json"
sys.path.insert(0, str(REPORT_DIR))

import headline_v2  # noqa: E402
import render_v2  # noqa: E402


class HeadlineV2Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.market = json.loads(FIXTURE.read_text())

    def test_existing_snapshot_drives_weekly_headline_without_mutation(self):
        source = copy.deepcopy(self.market)
        view = headline_v2.build_headline_view(source)

        self.assertEqual(source, self.market)
        self.assertEqual(view["revenue"], 1_100_000)
        self.assertEqual(view["wow_abs"], 100_000)
        self.assertEqual(view["wow_pct"], 10.0)
        self.assertAlmostEqual(view["trailing_four_revenue"], 1_022_500)
        self.assertAlmostEqual(view["vs_trailing_four_pct"], 7.5794621027)
        self.assertEqual(view["yoy_pct"], 15.0)
        self.assertEqual(view["monthly"], {"state": "missing"})
        self.assertEqual(len(view["chart"]), 12)

    def test_current_goal_adds_monthly_outlook(self):
        goal = {
            "month": "2026-08",
            "monthly_goal": 1_872_857.14,
            "mtd_revenue": 536_000,
            "forecast_revenue": 1_311_000,
            "forecast_attainment_pct": 70,
            "yoy_pct": -21,
            "mom_pct": -12,
            "as_of": "2026-08-08",
            "source": "approved goals view",
        }
        monthly = headline_v2.build_headline_view(self.market, goal)["monthly"]

        self.assertEqual(monthly["state"], "current")
        self.assertEqual(monthly["forecast_attainment_pct"], 70)
        self.assertAlmostEqual(monthly["mtd_attainment_pct"], 28.619375, places=5)

    def test_stale_goal_cannot_drive_current_verdict(self):
        goal = {
            "month": "2026-08",
            "monthly_goal": 1_000_000,
            "mtd_revenue": 500_000,
            "forecast_revenue": 1_100_000,
            "as_of": "2026-08-01",
            "source": "old goals extract",
        }
        monthly = headline_v2.build_headline_view(self.market, goal)["monthly"]

        self.assertEqual(monthly["state"], "stale")

    def test_incomplete_goal_fails_closed(self):
        goal = {"month": "2026-08", "forecast_attainment_pct": 120, "as_of": "2026-08-08"}
        self.assertEqual(headline_v2.build_headline_view(self.market, goal)["monthly"], {"state": "missing"})

    def test_v2_renderer_is_separate_and_embeds_only_derived_headlines(self):
        markets = render_v2.render_v1.load_markets([str(FIXTURE)])
        html = render_v2.render(markets)
        match = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', html, re.S)

        self.assertIsNotNone(match)
        embedded = json.loads(match.group(1))
        self.assertEqual(embedded["schema_version"], 2)
        self.assertEqual(embedded["source_schema_version"], 1)
        self.assertEqual(len(embedded["headlines"]), 1)
        self.assertNotIn("ces", embedded)
        self.assertIn("Weekly calculations remain sourced from the existing snapshot", html)
        self.assertIn("Weekly WoW", html)
        self.assertIn("Weekly YoY", html)
        self.assertIn('id="country-select"', html)
        self.assertIn('id="week-select"', html)
        self.assertNotIn('id="market-select"', html)

    def test_report_scope_is_one_market_with_week_history(self):
        older = copy.deepcopy(self.market)
        older["meta"]["week_start"] = "2026-07-26"
        older["meta"]["week_end"] = "2026-08-01"
        another_market = copy.deepcopy(self.market)
        another_market["meta"]["market"] = "Another Market"
        another_market["meta"]["market_slug"] = "another_market"

        html = render_v2.render([self.market, another_market, older])
        match = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', html, re.S)
        embedded = json.loads(match.group(1))

        self.assertEqual(
            [item["week_start"] for item in embedded["headlines"]],
            ["2026-07-26", "2026-08-02"],
        )
        self.assertEqual({item["market_slug"] for item in embedded["headlines"]}, {"north_america"})


if __name__ == "__main__":
    unittest.main()
