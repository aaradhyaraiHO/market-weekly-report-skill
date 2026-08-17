from __future__ import annotations

import gzip
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
ALERT_V2 = ROOT / "alert" / "v2" / "weekly_alert_v2.py"
OKR_BUILDER_V2 = ROOT / "alert" / "v2" / "build_market_okr_results.py"
READINESS_V2 = ROOT / "alert" / "v2" / "check_readiness.py"
DENSE_FIXTURE = Path(__file__).parent / "fixtures" / "captured" / "snapshot_dense_2026-08-02.json.gz"

sys.path.insert(0, str(REPORT_DIR))
import headline_v2  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


weekly_alert_v2 = _load("weekly_alert_v2_contract", ALERT_V2)
build_market_okr_results = _load("build_market_okr_results_contract", OKR_BUILDER_V2)
check_readiness = _load("check_readiness_contract", READINESS_V2)


class WeeklyAlertV2Contract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with gzip.open(DENSE_FIXTURE, "rt") as fixture:
            cls.market = json.load(fixture)
        trend = cls.market["market_summary"]["headlines"]["week_header"]["trend"]
        ce_ids = [str(row["ce_id"]) for row in trend["top_gainers"] + trend["top_droppers"]]
        goal = {
            "month": "2026-08",
            "monthly_goal": 2_000_000,
            "mtd_revenue": 600_000,
            "forecast_revenue": 1_800_000,
            "as_of": "2026-08-08",
            "ce_target_pacing": {
                ce_id: {"mtd_gap": -1_000, "mtd_gap_pct": -10.0, "monthly_goal": 20_000}
                for ce_id in ce_ids
            },
        }
        cls.headline = headline_v2.build_headline_view(cls.market, goal)
        cls.bgms = {"markets": {cls.headline["market_slug"]: {"slack_user_ids": ["U123ABC"]}}}

    def test_two_message_shape_uses_v2_headline_and_no_v1_tables(self):
        payload = weekly_alert_v2.build_payload(self.headline, self.bgms)

        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0]["threads"], [])
        top, bottom = weekly_alert_v2.report_movers(self.headline)
        self.assertEqual(len(payload["messages"][1]["threads"]), len({
            str(row["ce_id"]) for row in top + bottom
        }))
        self.assertEqual(payload["_v2"]["headline_source"], "codex/v2-market-headlines")
        self.assertEqual(payload["_v2"]["format_version"], "2026-08-17.1")
        self.assertTrue(payload["_v2"]["format_locked"])
        rendered = json.dumps(payload, ensure_ascii=False)
        self.assertIn("<@U123ABC>", rendered)
        self.assertIn("|KPI|Actual|vs LW|vs same week LY|vs target|", rendered)
        self.assertIn(":bar_chart: *Revenue*", rendered)
        self.assertIn("*Overall*", rendered)
        self.assertIn("*Paid · Google Search + Bing*", rendered)
        self.assertIn("calculated-CM fallback before Sep 2025", rendered)
        self.assertIn("|Revenue|", rendered)
        self.assertIn("|Overall ROI|", rendered)
        self.assertIn("|AOV|", rendered)
        self.assertIn("|Take rate|", rendered)
        self.assertIn("|Paid ROI|", rendered)
        self.assertIn("|Paid clicks|", rendered)
        self.assertIn("|Paid CVR|", rendered)
        self.assertIn("Open this market's weekly report", rendered)
        self.assertIn("F0BKPP4C7GC", rendered)
        self.assertIn("Top 5", rendered)
        self.assertIn("Bottom 5", rendered)
        self.assertNotIn("Losing Money", rendered)
        self.assertNotIn("RPC Fluctuations", rendered)

    def test_alert_1_restores_each_v1_kpi_as_a_separate_line(self):
        payload = weekly_alert_v2.build_payload(self.headline, self.bgms)
        section = payload["messages"][0]["blocks"][1]["text"]["text"]
        by_key = {row["key"]: row for row in self.headline["detail"]["metrics"]}

        table_rows = [line for line in section.splitlines() if line.startswith("|")]
        self.assertEqual(len(table_rows), 13)
        self.assertIn(weekly_alert_v2.fmt_attainment(by_key["roi1"]["w0"], 2), section)
        self.assertIn(weekly_alert_v2.fmt_attainment(by_key["paid_roi"]["w0"], 2), section)
        self.assertIn(weekly_alert_v2.fmt_money(by_key["aov"]["w0"]), section)
        self.assertIn(weekly_alert_v2.fmt_attainment(by_key["tr_pct"]["w0"], 2), section)
        self.assertIn(weekly_alert_v2.fmt_count(by_key["paid_clicks"]["w0"]), section)
        self.assertIn(weekly_alert_v2.fmt_attainment(by_key["paid_cvr"]["w0"], 2), section)

        self.assertIn("projected", table_rows[2])
        self.assertEqual(table_rows[3], "|KPI|Actual|vs LW|vs same week LY|")
        self.assertEqual(table_rows[8], "|KPI|Actual|vs LW|vs same week LY|")
        for key in ("roi1", "aov", "tr_pct", "paid_roi", "paid_clicks", "paid_cvr"):
            self.assertIn(weekly_alert_v2.fmt_delta(by_key[key]["yoy_pct"], 1), section)

    def test_optional_restored_metrics_render_unavailable_without_breaking_alert(self):
        headline = dict(self.headline)
        headline["detail"] = {"metrics": []}

        payload = weekly_alert_v2.build_payload(headline, self.bgms)
        section = payload["messages"][0]["blocks"][1]["text"]["text"]

        self.assertIn("|Overall ROI|—|—|—|", section)
        self.assertIn("|Paid ROI|—|—|—|", section)
        self.assertIn("|Paid clicks|—|—|—|", section)
        self.assertIn("|Paid CVR|—|—|—|", section)

    def test_movers_preserve_v2_order_and_thread_order(self):
        top, bottom = weekly_alert_v2.report_movers(self.headline)
        payload = weekly_alert_v2.build_payload(self.headline, self.bgms)
        expected = []
        for row in top + bottom:
            ce_id = str(row["ce_id"])
            if ce_id not in expected:
                expected.append(ce_id)

        self.assertEqual(payload["_rca"]["ce_ids"], expected)
        self.assertEqual(
            [thread["$rca"] for thread in payload["messages"][1]["threads"]],
            expected,
        )

    def test_mover_target_without_pacing_renders_unavailable(self):
        row = dict(self.headline["movers"]["gains"][0])
        row["monthly_target"] = 20_000
        row["target_mtd_attainment_pct"] = None

        rendered = weekly_alert_v2._mover_line(row, "top")

        self.assertIn("Target Unavailable", rendered)
        self.assertNotIn("Target No target", rendered)

    def test_schema_v1_html_is_rejected_as_a_fallback(self):
        html = '<script id="report-data" type="application/json">{"schema_version":1,"markets":[]}</script>'
        with tempfile.TemporaryDirectory(prefix="alert-v2-") as tmp:
            path = Path(tmp) / "v1.html"
            path.write_text(html)
            with self.assertRaisesRegex(ValueError, "V1 report-data is not a fallback"):
                weekly_alert_v2.load_headline(path, "north_america")

    def test_missing_bgm_and_stale_target_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "No BGM Slack IDs"):
            weekly_alert_v2.build_payload(self.headline, {"markets": {}})

        stale = dict(self.headline)
        stale["monthly"] = {"state": "stale"}
        with self.assertRaisesRegex(ValueError, "no current approved target"):
            weekly_alert_v2.build_payload(stale, self.bgms)

    def test_okr_is_optional_until_selection_is_finalized(self):
        pending = weekly_alert_v2.build_payload(self.headline, self.bgms)
        configured = weekly_alert_v2.build_payload(
            self.headline,
            self.bgms,
            {"markets": {self.headline["market_slug"]: [
                {"label": "Grow Pro+ CEs", "current": "48", "target": "53", "status": "At risk"}
            ]}},
        )

        self.assertEqual(pending["_v2"]["okr_selection_status"], "pending")
        self.assertEqual(configured["_v2"]["okr_selection_status"], "configured")
        self.assertIn("Grow Pro+ CEs", json.dumps(configured))

    def test_okr_block_links_tracker_and_keeps_methodology_out_of_scan_copy(self):
        rows = build_market_okr_results.build_results(
            [{
                "market": "North America",
                "pro_plus_ces": 43,
                "new_pro_plus_mature_on_pace": 7,
                "new_pro_plus_mature_reached": 4,
                "new_pro_plus_emerging_growth_on_pace": 5,
                "new_pro_plus_emerging_growth_reached": 2,
                "gel_revenue_ty": 125000,
                "gel_revenue_ly": 100000,
                "gel_yoy_pct": 25.0,
            }],
            {self.headline["market_slug"]: "North America"},
            self.headline["week_start"],
        )
        for row, status in zip(rows["markets"][self.headline["market_slug"]], [
            ":large_green_circle: On track",
            ":large_yellow_circle: At risk",
            ":large_yellow_circle: At risk",
            ":large_green_circle: On track",
        ]):
            row["status"] = status

        payload = weekly_alert_v2.build_payload(self.headline, self.bgms, rows)
        okr_block = payload["messages"][0]["blocks"][2]["text"]["text"]

        self.assertIn("<https://central-tracking.vercel.app/okr-tracker|Selected OKRs>", okr_block)
        self.assertIn("*New Pro+ CEs · Mature* — 7 on pace (4 reached)", okr_block)
        self.assertIn("*New Pro+ CEs · Emerging & Growth* — 5 on pace (2 reached)", okr_block)
        self.assertIn("*Non-POI GEL revenue* — +25.0% YoY QTD", okr_block)
        self.assertNotIn("L92 predicted revenue", okr_block)
        self.assertNotIn("prior 4 quarters", okr_block)

    def test_okr_sidecar_week_must_match_headline(self):
        stale = {
            "week_start": "2026-07-26",
            "markets": {self.headline["market_slug"]: [
                {"label": "Grow cumulative Pro+ CEs", "current": "42 CEs"}
            ]},
        }
        with self.assertRaisesRegex(ValueError, "does not match headline week"):
            weekly_alert_v2.build_payload(self.headline, self.bgms, stale)


class MarketOKRBuilderContract(unittest.TestCase):
    def test_market_result_has_exact_four_selected_krs(self):
        rows = [{
            "market": "North America",
            "pro_plus_ces": 43,
            "new_pro_plus_mature_on_pace": 7,
            "new_pro_plus_mature_reached": 4,
            "new_pro_plus_emerging_growth_on_pace": 5,
            "new_pro_plus_emerging_growth_reached": 2,
            "gel_revenue_ty": 125000,
            "gel_revenue_ly": 100000,
            "gel_yoy_pct": 25.0,
        }]
        payload = build_market_okr_results.build_results(
            rows, {"north_america": "North America"}, "2026-08-02"
        )
        results = payload["markets"]["north_america"]

        self.assertEqual([row["id"] for row in results], list(build_market_okr_results.OKR_IDS))
        self.assertEqual(results[0]["current"], "43 CEs")
        self.assertEqual(results[1]["current"], "7 on pace")
        self.assertEqual(results[1]["reached"], 4)
        self.assertEqual(results[2]["current"], "5 on pace")
        self.assertEqual(results[2]["reached"], 2)
        self.assertEqual(results[3]["current"], "+25.0% YoY")
        self.assertEqual(
            [row["status"] for row in results],
            [
                ":large_yellow_circle: At risk",
                ":large_yellow_circle: At risk",
                ":large_yellow_circle: At risk",
                ":large_green_circle: On track",
            ],
        )
        self.assertEqual(payload["week_end"], "2026-08-08")

    def test_sql_preserves_current_engine_definitions_and_market_grain(self):
        sql = build_market_okr_results.MARKET_OKR_SQL
        self.assertIn("sum_revenue_predicted", sql)
        self.assertIn("INTERVAL 84 DAY", sql)
        self.assertIn("max_prior_4q_revenue, 0) < 10000", sql)
        self.assertIn("INTERVAL 27 DAY", sql)
        self.assertIn("projected_quarter_revenue >= 10000", sql)
        self.assertIn("evolution_bucket = 'Mature'", sql)
        self.assertIn("evolution_bucket IN ('Emerging', 'Growth')", sql)
        self.assertIn("category != 'POI/ Attractions'", sql)
        self.assertIn("management_type IN ('Managed', 'Managed Lite')", sql)
        self.assertIn("INTERVAL 1 YEAR", sql)
        self.assertNotIn("INTERVAL 364 DAY", sql)
        self.assertNotIn("weekly_kr_metrics", sql)
        self.assertIn("FROM UNNEST(@markets)", sql)

    def test_missing_configured_market_fails_instead_of_guessing_zero(self):
        with self.assertRaisesRegex(ValueError, "returned no row"):
            build_market_okr_results.build_results(
                [], {"north_america": "North America"}, "2026-08-02"
            )


class AlertV2ReadinessContract(unittest.TestCase):
    def test_finalized_market_readiness_names_only_missing_bgm_assignment(self):
        result = check_readiness.check()

        self.assertFalse(result["ready"])
        self.assertEqual(result["format_version"], "2026-08-17.1")
        self.assertEqual(result["blockers"]["missing_bgm_assignments"], ["rest_of_mea"])
        for key, values in result["blockers"].items():
            if key != "missing_bgm_assignments":
                self.assertEqual(values, [], key)

    def test_headout_is_an_explicit_extra_readiness_scope(self):
        result = check_readiness.check(include_headout=True)

        self.assertEqual(
            result["blockers"]["missing_bgm_assignments"],
            ["rest_of_mea", "headout"],
        )


if __name__ == "__main__":
    unittest.main()
