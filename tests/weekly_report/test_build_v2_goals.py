from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
FIXTURE = Path(__file__).parent / "fixtures" / "snapshot_north_america_2026-08-02.json"
sys.path.insert(0, str(REPORT_DIR))

import build_v2_goals  # noqa: E402


class BuildV2GoalsContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.market = json.loads(FIXTURE.read_text())

    def setUp(self):
        defaults = (
            ("market_month_comparisons", pd.DataFrame([{
                "prior_month_revenue": 4_500_000.0,
                "prior_mtd_revenue": 1_100_000.0,
                "ly_month_revenue": 4_000_000.0,
                "ly_mtd_revenue": 800_000.0,
            }])),
            ("market_ce_period_revenue", pd.DataFrame([{
                "ce_id": "CE-001", "ce_name": "Example Museum", "revenue": 70_000.0,
            }])),
            ("market_ce_monthly_goals", pd.DataFrame([{
                "ce_id": "CE-001", "ce_name": "Example Museum", "monthly_goal": 1_000_000.0,
            }])),
        )
        for name, value in defaults:
            patcher = mock.patch.object(build_v2_goals.fetch, name, return_value=value)
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def _period_revenue(self):
        return pd.DataFrame([{"revenue": 536_000.0}])

    @mock.patch.object(build_v2_goals.fetch, "market_period_revenue")
    @mock.patch.object(build_v2_goals.fetch, "market_monthly_goal")
    def test_market_goal_is_authoritative_and_forecast_reuses_snapshot_revenue(
        self, goal_query, revenue_query
    ):
        goal_query.return_value = pd.DataFrame([{
            "market_row_count": 1,
            "market_goal": 6_800_000.0,
            "ce_row_count": 12,
            "ce_goal": 6_700_000.0,
        }])
        revenue_query.return_value = self._period_revenue()

        slug, goal = build_v2_goals.build_market_goal(copy.deepcopy(self.market))

        self.assertEqual(slug, "north_america")
        self.assertEqual(goal["monthly_goal"], 6_800_000.0)
        self.assertEqual(goal["goal_grain"], "Market")
        self.assertEqual(goal["mtd_revenue"], 536_000.0)
        recent = [row["revenue"] for row in self.market["market_summary"]["weekly"][-4:]]
        expected_run_rate_weekly = sum(recent) / len(recent)
        expected_baseline = expected_run_rate_weekly * 4.345
        expected_remaining = expected_run_rate_weekly * 23 / 7
        expected_forecast = 536_000.0 + expected_remaining
        self.assertEqual(goal["forecast_revenue"], expected_forecast)
        self.assertEqual(goal["run_rate_weekly_revenue"], expected_run_rate_weekly)
        self.assertEqual(goal["forecast_baseline_revenue"], expected_baseline)
        self.assertEqual(goal["forecast_remaining_revenue"], expected_remaining)
        self.assertAlmostEqual(goal["forecast_remaining_share_pct"], 100 * 23 / 31)
        self.assertIn("actual MTD", goal["forecast_method"])
        self.assertAlmostEqual(goal["expected_mtd_revenue"], 6_800_000 * 8 / 31)
        self.assertAlmostEqual(goal["expected_mtd_share_pct"], 100 * 8 / 31)
        self.assertEqual(goal["expected_mtd_method"], "calendar-linear target pacing")
        self.assertAlmostEqual(goal["mtd_gap"], 536_000 - 6_800_000 * 8 / 31)
        self.assertAlmostEqual(goal["mtd_vs_last_year_pct"], 100 * (536_000 / 800_000 - 1))
        self.assertAlmostEqual(goal["mtd_vs_last_month_pct"], 100 * (536_000 / 1_100_000 - 1))
        self.assertAlmostEqual(goal["required_weekly_revenue"], (6_800_000 - 536_000) / 23 * 7)
        self.assertAlmostEqual(goal["forecast_vs_last_month_pct"], 100 * (expected_forecast / 4_500_000 - 1))
        self.assertEqual(goal["ce_gap_contributors"][0]["ce_id"], "CE-001")
        self.assertEqual(goal["ce_target_pacing"]["CE-001"]["monthly_goal"], 1_000_000.0)
        self.assertEqual(goal["ce_target_pacing"]["CE-001"]["prior_mtd_revenue"], 70_000.0)
        self.assertEqual(goal["ce_target_pacing"]["CE-001"]["prior_month_revenue"], 70_000.0)
        self.assertEqual(goal["ce_target_pacing"]["CE-001"]["ly_mtd_revenue"], 70_000.0)
        self.assertEqual(goal["ce_target_pacing"]["CE-001"]["ly_month_revenue"], 70_000.0)
        self.assertAlmostEqual(
            goal["ce_target_pacing"]["CE-001"]["mtd_gap_pct"],
            100 * (70_000 / (1_000_000 * 8 / 31) - 1),
        )
        goal_query.assert_called_once()
        revenue_query.assert_called_once()

    @mock.patch.object(build_v2_goals.fetch, "market_period_revenue")
    @mock.patch.object(build_v2_goals.fetch, "market_monthly_goal")
    def test_ce_rollup_is_used_only_when_market_goal_is_absent(self, goal_query, revenue_query):
        goal_query.return_value = pd.DataFrame([{
            "market_row_count": 0,
            "market_goal": None,
            "ce_row_count": 12,
            "ce_goal": 6_700_000.0,
        }])
        revenue_query.return_value = self._period_revenue()

        _, goal = build_v2_goals.build_market_goal(copy.deepcopy(self.market))

        self.assertEqual(goal["monthly_goal"], 6_700_000.0)
        self.assertEqual(goal["goal_grain"], "Combined Entity roll-up")
        self.assertEqual(goal["goal_row_count"], 12)

    @mock.patch.object(build_v2_goals.fetch, "market_period_revenue")
    @mock.patch.object(build_v2_goals.fetch, "market_monthly_goal")
    def test_calendar_pacing_does_not_depend_on_last_year_shape(
        self, goal_query, revenue_query
    ):
        goal_query.return_value = pd.DataFrame([{
            "market_row_count": 1,
            "market_goal": 6_200_000.0,
            "ce_row_count": 0,
            "ce_goal": None,
        }])
        revenue_query.return_value = self._period_revenue()
        self.market_month_comparisons.return_value = pd.DataFrame([{
            "prior_month_revenue": 4_500_000.0,
            "ly_month_revenue": 0.0,
            "ly_mtd_revenue": None,
        }])

        _, goal = build_v2_goals.build_market_goal(copy.deepcopy(self.market))

        self.assertAlmostEqual(goal["expected_mtd_share_pct"], 100 * 8 / 31)
        self.assertAlmostEqual(goal["forecast_remaining_share_pct"], 100 * 23 / 31)
        self.assertEqual(goal["expected_mtd_method"], "calendar-linear target pacing")

    @mock.patch.object(build_v2_goals.fetch, "market_monthly_goal")
    def test_missing_goal_fails_closed(self, goal_query):
        goal_query.return_value = pd.DataFrame([{
            "market_row_count": 0,
            "market_goal": None,
            "ce_row_count": 0,
            "ce_goal": None,
        }])

        with self.assertRaisesRegex(RuntimeError, "No approved monthly target"):
            build_v2_goals.build_market_goal(copy.deepcopy(self.market))

    def test_headout_keeps_company_goal_and_unions_same_month_ce_targets(self):
        headout = {
            "month": "2026-08",
            "monthly_goal": 15_000_000.0,
            "goal_grain": "Headout total",
            "ce_target_pacing": {},
        }
        market_goals = {
            "north_america": {
                "month": "2026-08",
                "ce_target_pacing": {
                    "3111": {"monthly_goal": 200_000.0, "mtd_gap": -10_000.0},
                    "18 - Chicago": {"monthly_goal": 300_000.0, "mtd_gap": 5_000.0},
                },
            },
            "france": {
                "month": "2026-08",
                "ce_target_pacing": {
                    "254": {"monthly_goal": 350_000.0, "mtd_gap": -20_000.0},
                },
            },
            "stale_market": {
                "month": "2026-07",
                "ce_target_pacing": {"old": {"monthly_goal": 999_000.0}},
            },
        }

        result = build_v2_goals.merge_headout_ce_targets(headout, market_goals)

        self.assertEqual(result["monthly_goal"], 15_000_000.0)
        self.assertEqual(result["goal_grain"], "Headout total")
        self.assertEqual(set(result["ce_target_pacing"]), {"3111", "18 - Chicago", "254"})
        self.assertEqual(
            result["ce_target_pacing"]["18 - Chicago"]["source_market_slug"],
            "north_america",
        )
        self.assertEqual(result["ce_target_row_count"], 3)
        self.assertEqual(result["ce_target_conflict_count"], 0)
        self.assertEqual(result["ce_gap_contributors"][0]["monthly_goal"], 350_000.0)
        self.assertAlmostEqual(result["ce_target_coverage_pct"], 100 * 850_000 / 15_000_000)

    def test_headout_omits_conflicting_duplicate_ce_ids(self):
        result = build_v2_goals.merge_headout_ce_targets({"month": "2026-08"}, {
            "france": {"month": "2026-08", "ce_target_pacing": {"254": {"monthly_goal": 1}}},
            "italy": {"month": "2026-08", "ce_target_pacing": {"254": {"monthly_goal": 2}}},
        })

        self.assertNotIn("254", result["ce_target_pacing"])
        self.assertEqual(result["ce_target_conflict_count"], 1)


if __name__ == "__main__":
    unittest.main()
