from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
sys.path.insert(0, str(REPORT_DIR))

import build_snapshot  # noqa: E402
import fetch  # noqa: E402


class CeDrawerLiveSourceContract(unittest.TestCase):
    def test_fetch_contracts_use_matched_w0_w1_ly_windows(self):
        windows = (
            dt.date(2026, 8, 2), dt.date(2026, 8, 8),
            dt.date(2026, 7, 26), dt.date(2026, 8, 1),
            dt.date(2025, 8, 3), dt.date(2025, 8, 9),
        )
        captured = []

        def capture(sql, label, params, **kwargs):
            captured.append((label, sql, params))
            return pd.DataFrame()

        with mock.patch.object(fetch, "query_df", side_effect=capture):
            fetch.ce_channels("North America", *windows)
            fetch.ce_variants("North America", *windows)
            fetch.ce_leadtime("North America", *windows)
            fetch.ce_countries("North America", *windows)
            fetch.ce_leadtime_history("North America", windows[0], windows[1], windows[4], windows[5], ["CE-1"])
            fetch.ce_country_history("North America", windows[0], windows[1], windows[4], windows[5], ["CE-1"])
            fetch.ce_channel_history("North America", windows[0], windows[1], windows[4], windows[5], ["CE-1"])

        by_label = {label: (sql, params) for label, sql, params in captured}

        # PMax campaigns commonly end in the same cid suffix used by Search.
        # Campaign type must win or PMax revenue is silently reported as Search.
        for label in ("ce_channels", "ce_channel_history"):
            channel_sql, _ = by_label[label]
            self.assertLess(
                channel_sql.index("THEN 'Google PMax'"),
                channel_sql.index("THEN 'Google Search'"),
            )
            self.assertIn(r"pmax|performance[ -]?max", channel_sql)

        variant_sql, variant_params = by_label["ce_variants"]
        self.assertIn("__UNATTRIBUTED__", variant_sql)
        self.assertIn("price_payable_usd", variant_sql)
        self.assertIn("order_credit", variant_sql)
        self.assertIn("CAST(b.experience_id AS STRING) = CAST(o.experience_id AS STRING)", variant_sql)
        self.assertEqual(variant_params["ly_s"], "2025-08-03")

        lead_sql, _ = by_label["ce_leadtime"]
        for band in ("0D", "1-2D", "3-4D", "5-7D", "7D+"):
            self.assertIn(f"'{band}'", lead_sql)
        self.assertIn("bookings_ly", lead_sql)
        self.assertIn("rev_wm1", lead_sql)
        self.assertIn("rev_ly", lead_sql)

        country_sql, _ = by_label["ce_countries"]
        self.assertIn("orders_ly", country_sql)
        self.assertIn("rev_ly", country_sql)
        self.assertIn("order_value_ly", country_sql)

        for label in ("ce_leadtime_history", "ce_country_history", "ce_channel_history"):
            history_sql, history_params = by_label[label]
            self.assertIn("DATE_TRUNC", history_sql)
            self.assertIn("INTERVAL 364 DAY", history_sql)
            self.assertIn("UNNEST(@ce_ids)", history_sql)
            self.assertEqual(history_params["ce_ids"], ["CE-1"])

    def test_snapshot_projects_reconciled_variant_children_and_five_lead_bands(self):
        ces = [{"ce_id": "CE-1"}]
        tgids = pd.DataFrame([{
            "combined_entity_id": "CE-1", "tgid": "4108", "experience": "Harbor cruise",
            "rev": 100.0, "rev_wm1": 80.0, "rev_ly": 50.0,
            "orders": 10.0, "orders_wm1": 8.0, "orders_ly": 5.0,
            "gbv": 200.0, "gbv_wm1": 160.0, "gbv_ly": 100.0,
            "completed_gbv": 180.0, "completed_gbv_wm1": 144.0,
            "completed_gbv_ly": 90.0,
        }])
        variants = pd.DataFrame([
            {"combined_entity_id": "CE-1", "tgid": "4108", "variant_id": "A",
             "variant_name": "Morning", "rev": 60.0, "rev_wm1": 50.0, "rev_ly": 30.0,
             "orders": 6.0, "orders_wm1": 5.0, "orders_ly": 3.0,
             "gbv": 120.0, "gbv_wm1": 100.0, "gbv_ly": 60.0,
             "completed_gbv": 108.0, "completed_gbv_wm1": 90.0,
             "completed_gbv_ly": 54.0, "lt_0d": .25, "lt_12d": .25,
             "lt_37d": .25, "lt_7p": .25},
            {"combined_entity_id": "CE-1", "tgid": "4108", "variant_id": "B",
             "variant_name": "Evening", "rev": 40.0, "rev_wm1": 30.0, "rev_ly": 20.0,
             "orders": 4.0, "orders_wm1": 3.0, "orders_ly": 2.0,
             "gbv": 80.0, "gbv_wm1": 60.0, "gbv_ly": 40.0,
             "completed_gbv": 72.0, "completed_gbv_wm1": 54.0,
             "completed_gbv_ly": 36.0, "lt_0d": None, "lt_12d": None,
             "lt_37d": None, "lt_7p": None},
        ])
        lead_rows = []
        for index, band in enumerate(("0D", "1-2D", "3-4D", "5-7D", "7D+"), 1):
            lead_rows.append({
                "combined_entity_id": "CE-1", "band": band,
                "bookings": index * 10, "bookings_wm1": index * 8, "bookings_ly": index * 5,
                "rev": index * 100, "rev_wm1": index * 80, "rev_ly": index * 50,
                "order_value": index * 200, "order_value_wm1": index * 160,
                "order_value_ly": index * 100,
            })

        build_snapshot._attach_resource_breakdowns(
            ces, tgids, variants, pd.DataFrame(), pd.DataFrame(),
            pd.DataFrame(lead_rows), pd.DataFrame(),
        )

        parent = ces[0]["tgids"][0]
        self.assertEqual(sum(row["rev"] for row in parent["variants"]), parent["rev"])
        self.assertEqual(sum(row["orders"] for row in parent["variants"]), parent["orders"])
        self.assertTrue(all(row["rpc"] is None for row in parent["variants"]))
        self.assertIsNone(parent["variants"][1]["lt_0d"])
        self.assertEqual([row["band"] for row in ces[0]["leadtime"]],
                         ["0D", "1-2D", "3-4D", "5-7D", "7D+"])
        self.assertEqual(ces[0]["leadtime"][0]["bookings_wow"], 25.0)
        self.assertEqual(ces[0]["leadtime"][0]["bookings_yoy"], 100.0)

    def test_snapshot_attaches_real_resource_history_by_cid_and_key(self):
        ces = [{
            "ce_id": "CE-1",
            "leadtime": [{"band": "0D"}],
            "countries": [{"country": "US"}],
            "channels": [{"channel": "Direct"}],
        }]
        def frame(key, value):
            return pd.DataFrame([
                {"combined_entity_id": "CE-1", key: value, "week": "2026-08-02", "period": "ty", "rev": 120.0},
                {"combined_entity_id": "CE-1", key: value, "week": "2026-08-02", "period": "ly", "rev": 90.0},
            ])

        build_snapshot._attach_resource_histories(
            ces, frame("band", "0D"), frame("country", "US"), frame("channel", "Direct")
        )

        expected = [{"week": "2026-08-02", "ty": 120.0, "ly": 90.0}]
        self.assertEqual(ces[0]["leadtime"][0]["history"], expected)
        self.assertEqual(ces[0]["countries"][0]["history"], expected)
        self.assertEqual(ces[0]["channels"][0]["history"], expected)


if __name__ == "__main__":
    unittest.main()
