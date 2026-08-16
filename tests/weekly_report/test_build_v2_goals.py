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
        self.assertEqual(goal["forecast_revenue"], 1_100_000 * 4.345)
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


if __name__ == "__main__":
    unittest.main()
