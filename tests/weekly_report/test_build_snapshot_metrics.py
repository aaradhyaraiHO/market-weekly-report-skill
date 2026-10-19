from __future__ import annotations

import sys
import json
import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
sys.path.insert(0, str(REPORT_DIR))

import build_snapshot  # noqa: E402
import headline_v2  # noqa: E402


class WeeklyMetricContractTests(unittest.TestCase):
    def test_optional_percentage_point_delta_rejects_nonfinite_operands(self):
        for invalid in (None, float('nan'), float('inf'), -float('inf')):
            with self.subTest(invalid=invalid):
                self.assertIsNone(build_snapshot._dpp(invalid, 12.5))
                self.assertIsNone(build_snapshot._dpp(12.5, invalid))

    def test_finite_percentage_point_formula_and_precision_are_unchanged(self):
        for current, previous in ((0, 0), (61.23456, 38.76543), (-3.1, 7.2), (100, 0)):
            self.assertEqual(build_snapshot._dpp(current, previous), round(current - previous, 1))

    def test_missing_channel_baseline_cannot_emit_nan_or_invent_zero_share_change(self):
        ces = [{'ce_id': '1019 - London'}]
        channels = pd.DataFrame([
            {'combined_entity_id': '1019 - London', 'channel': name, 'period': period, 'rev': revenue}
            for name, current, previous in [('Google Search', 75.0, float('nan')), ('Organic', 25.0, 20.0)]
            for period, revenue in [('w0', current), ('wm1', previous)]
        ])
        before = channels.copy(deep=True)
        build_snapshot._attach_channels_funnel(ces, channels, pd.DataFrame())
        rows = {row['channel']: row for row in ces[0]['channels']}
        self.assertEqual(rows['Google Search']['rev'], 75.0)
        self.assertIsNone(rows['Google Search']['rev_wm1'])
        self.assertIsNone(rows['Google Search']['wow_pct'])
        self.assertIsNone(rows['Google Search']['share_wow_pp'])
        self.assertIsNone(rows['Organic']['share_wow_pp'])
        self.assertEqual(rows['Organic']['wow_pct'], 25.0)
        self.assertEqual(rows['Organic']['share_pct'], 25.0)
        json.dumps(ces, allow_nan=False)
        pd.testing.assert_frame_equal(channels, before)

    def test_nonfinite_channel_change_is_null_but_real_zero_and_finite_values_remain(self):
        for invalid in (float('nan'), float('inf'), -float('inf')):
            ces = [{'ce_id': 'test'}]
            channels = pd.DataFrame([
                {'combined_entity_id': 'test', 'channel': 'Google Search', 'period': 'w0', 'rev': invalid},
                {'combined_entity_id': 'test', 'channel': 'Google Search', 'period': 'wm1', 'rev': 10.0},
            ])
            build_snapshot._attach_channels_funnel(ces, channels, pd.DataFrame())
            self.assertIsNone(ces[0]['channels'][0]['wow_pct'])
            json.dumps(ces, allow_nan=False)
        ces = [{'ce_id': 'test'}]
        channels = pd.DataFrame([
            {'combined_entity_id': 'test', 'channel': 'Google Search', 'period': 'w0', 'rev': 0.0},
            {'combined_entity_id': 'test', 'channel': 'Google Search', 'period': 'wm1', 'rev': 10.0},
        ])
        build_snapshot._attach_channels_funnel(ces, channels, pd.DataFrame())
        self.assertEqual(ces[0]['channels'][0]['wow_pct'], -100.0)
        self.assertEqual(ces[0]['channels'][0]['rev'], 0.0)
        self.assertIsNone(ces[0]['channels'][0]['share_wow_pp'])

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
