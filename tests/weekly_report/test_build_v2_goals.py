from __future__ import annotations

import copy
import datetime as dt
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
    def test_fresh_headout_ce_goals_are_not_replaced_by_partial_market_sidecars(self):
        goal = {'month':'2026-09', 'scope':'all markets', 'monthly_goal':14217164,
                'ce_target_pacing':{'544':{'monthly_goal':10000}}}
        self.assertEqual(build_v2_goals.merge_headout_ce_targets(goal, {}), goal)
        stale = {'benelux':{'month':'2026-09', 'ce_target_pacing':{'544':{'monthly_goal':999}}}}
        self.assertEqual(build_v2_goals.merge_headout_ce_targets(goal, stale), goal)

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

    @mock.patch.object(build_v2_goals.fetch, "market_period_revenue")
    @mock.patch.object(build_v2_goals.fetch, "market_monthly_goal")
    def test_headout_uses_all_markets_and_only_approved_market_total(self, goal_query, revenue_query):
        market = copy.deepcopy(self.market)
        market['meta'].update(market='Headout (all markets)', market_slug='headout')
        goal_query.return_value = pd.DataFrame([dict(market_row_count=25, market_goal=14_217_164, ce_row_count=900, ce_goal=99_000_000)])
        revenue_query.return_value = self._period_revenue()
        _, goal = build_v2_goals.build_market_goal(market)
        self.assertEqual(goal['monthly_goal'], 14_217_164)
        self.assertEqual(goal['scope'], 'all markets')
        self.assertIsNone(goal_query.call_args.args[0])
        self.assertIsNone(revenue_query.call_args.args[0])
        for query in (self.market_ce_period_revenue, self.market_month_comparisons, self.market_ce_monthly_goals):
            self.assertTrue(all(call.args[0] is None for call in query.call_args_list))
        goal_query.return_value = pd.DataFrame([dict(market_row_count=0, market_goal=None, ce_row_count=900, ce_goal=99_000_000)])
        with self.assertRaisesRegex(RuntimeError, 'No approved'):
            build_v2_goals.build_market_goal(market)

    @mock.patch.object(build_v2_goals.fetch, "market_period_revenue")
    @mock.patch.object(build_v2_goals.fetch, "market_monthly_goal")
    def test_preview_does_not_count_future_days_or_partial_week(self, goal_query, revenue_query):
        market = copy.deepcopy(self.market)
        market['meta'].update(week_start='2026-09-06', week_end='2026-09-12', market_slug='headout')
        market['market_summary']['weekly'] = [dict(week=w, revenue=r) for w, r in [
            ('2026-08-09', 100), ('2026-08-16', 200), ('2026-08-23', 300), ('2026-08-30', 400), ('2026-09-06', 9999)]]
        goal_query.return_value = pd.DataFrame([dict(market_row_count=25, market_goal=10000, ce_row_count=0)])
        revenue_query.return_value = self._period_revenue()
        _, goal = build_v2_goals.build_market_goal(market, as_of=dt.date(2026, 9, 9))
        self.assertEqual(goal['as_of'], '2026-09-09')
        self.assertEqual(goal['elapsed_days'], 9)
        self.assertEqual(goal['remaining_days'], 21)
        self.assertEqual(goal['run_rate_weekly_revenue'], 250)
        self.assertEqual(revenue_query.call_args.args[-1], dt.date(2026, 9, 9))

    @mock.patch.object(build_v2_goals.fetch, 'query_df')
    def test_all_market_queries_remove_only_market_filter(self, query):
        start, end = dt.date(2026, 9, 1), dt.date(2026, 9, 9)
        f = build_v2_goals.fetch
        f.market_period_revenue(None, start, end)
        f.market_ce_period_revenue(None, start, end)
        f.market_month_comparisons(None, start, end, end, start, end, end)
        f.market_monthly_goal(None, start)
        f.market_ce_monthly_goals(None, start)
        for call in query.call_args_list:
            self.assertNotIn('@market', call.args[0])
            self.assertNotIn('market', call.args[2])
            self.assertTrue('@start' in call.args[0] or '@prior_start' in call.args[0] or '@month' in call.args[0])


if __name__ == "__main__":
    unittest.main()
