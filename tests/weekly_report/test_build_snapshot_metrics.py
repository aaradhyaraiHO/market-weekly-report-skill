from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
sys.path.insert(0, str(REPORT_DIR))

import build_snapshot  # noqa: E402
import headline_v2  # noqa: E402


class WeeklyMetricContractTests(unittest.TestCase):
    def test_paid_cm1_cutover_matches_omni_strict_post_sep_1_rule(self):
        source = (REPORT_DIR / "fetch.py").read_text()

        # Omni's contribution_margin_one uses offline CM1 strictly after
        # 2025-09-01. All three Weekly CM1 projections must preserve that exact
        # boundary; conversion-count cutovers are a separate metric contract.
        self.assertEqual(
            source.count("WHEN report_date > '2025-09-01'\n"
                         "                 AND sum_conversion_value_offline_contribution_margin > 0"),
            3,
        )
        self.assertNotIn(
            "WHEN report_date >= '2025-09-01'\n"
            "                 AND sum_conversion_value_offline_contribution_margin > 0",
            source,
        )

    def test_take_rate_uses_actual_order_revenue(self):
        business = pd.Series({
            "revenue": 3_113.78,
            "orders": 99,
            "clicks": 0,
            "ad_conversions": 0,
            "gbv": 18_000,
            "gbv_completed": 14_699.03,
            "organic_gbv": 0,
        })

        metric = build_snapshot._weekly_metrics(
            business, None, actual_revenue=3_689.31
        )

        self.assertEqual(metric["revenue"], 3_113.78)
        self.assertEqual(metric["actual_revenue"], 3_689.31)
        self.assertEqual(metric["tr_pct"], 25.1)

    def test_channel_attachment_keeps_prior_week_only_channels(self):
        ces = [{"ce_id": "2093"}]
        channels = pd.DataFrame([
            {"combined_entity_id": "2093", "channel": "Google Search", "period": "w0", "rev": 7_614.51},
            {"combined_entity_id": "2093", "channel": "Google Search", "period": "wm1", "rev": 8_247.35},
            {"combined_entity_id": "2093", "channel": "Organic", "period": "w0", "rev": 0.0},
            {"combined_entity_id": "2093", "channel": "Organic", "period": "wm1", "rev": 44.5},
        ])

        build_snapshot._attach_channels_funnel(ces, channels, pd.DataFrame())

        by_channel = {row["channel"]: row for row in ces[0]["channels"]}
        self.assertEqual(by_channel["Organic"]["rev"], 0.0)
        self.assertEqual(by_channel["Organic"]["rev_wm1"], 44.5)

    def test_v2_subtotal_uses_actual_revenue_for_take_rate(self):
        weekly = headline_v2._aggregate_weekly([
            {"ce_id": "2093", "weekly": [{
                "week": "2026-08-16", "revenue": 8_576.96,
                "actual_revenue": 8_584.26, "gbv_completed": 33_843.51,
            }]},
        ], "weekly")

        self.assertAlmostEqual(weekly[0]["tr_pct"], 25.3646, places=4)

    def test_v1_group_subtotal_uses_actual_revenue_for_take_rate(self):
        template = (REPORT_DIR / "template" / "report_template.html").read_text()

        self.assertIn("actualRev", template)
        self.assertIn("a.actualRev/a.gbvC", template)


if __name__ == "__main__":
    unittest.main()
