from __future__ import annotations

import copy
import gzip
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
FIXTURE = Path(__file__).parent / "fixtures" / "snapshot_north_america_2026-08-02.json"
DENSE_FIXTURE = Path(__file__).parent / "fixtures" / "captured" / "snapshot_dense_2026-08-02.json.gz"
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
        self.assertEqual(len(view["all_ces"]), 2)
        self.assertEqual(view["all_ces"][0]["ce_name"], "Example Museum")
        self.assertEqual(view["all_ces"][0]["revenue"], 70_000)
        self.assertEqual(view["all_ces"][0]["wow_abs"], -30_000)

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

    def test_current_goal_enriches_movers_by_cid_without_changing_rank(self):
        goal = {
            "month": "2026-08",
            "monthly_goal": 1_872_857.14,
            "mtd_revenue": 536_000,
            "forecast_revenue": 1_311_000,
            "as_of": "2026-08-08",
            "ce_target_pacing": {
                "101": {"mtd_gap": -12_500, "mtd_gap_pct": -18.2, "monthly_goal": 210_000}
            },
        }
        view = headline_v2.build_headline_view(self.market, goal)
        first_drop = view["movers"]["drops"][0]

        self.assertEqual(first_drop["source_rank"], 1)
        self.assertEqual(first_drop["target_mtd_gap"], -12_500)
        self.assertEqual(first_drop["target_mtd_gap_pct"], -18.2)
        self.assertEqual(first_drop["monthly_target"], 210_000)

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
        self.assertIn("Sources: frozen weekly snapshot", html)
        self.assertIn("Weekly WoW", html)
        self.assertIn("Weekly YoY", html)
        self.assertIn('id="country-select"', html)
        self.assertIn('id="week-select"', html)
        self.assertNotIn('id="market-select"', html)
        self.assertIn('id="open-detail"', html)
        self.assertEqual(html.count('id="open-detail"'), 1)
        self.assertNotIn('id="weekly-engine-section"', html)
        self.assertNotIn('id="weekly-engine-context"', html)
        self.assertNotIn('id="drawer-overview"', html)
        self.assertIn('id="metric-tooltip"', html)
        self.assertIn("function wireMetricSparklines", html)
        self.assertIn("Key metrics · 12-week trend", html)
        self.assertNotIn("Data provenance", html)
        self.assertIn('<details class="pacing-details" id="pacing-details">', html)
        self.assertIn('id="targets-section"', html)
        self.assertIn('id="target-summary"', html)
        self.assertIn('id="target-comparisons"', html)
        self.assertIn('id="target-contributors"', html)
        self.assertIn("function renderTargets", html)
        self.assertIn("vs same week last year", html)
        self.assertIn("Projected month-end", html)
        self.assertIn("weekly revenue`", html)
        self.assertIn('data-mover-kind="${kind}"', html)
        self.assertIn('data-mover-sort="${key}"', html)
        self.assertIn("const moverSorts", html)
        self.assertNotIn('data-mover-lens=', html)
        self.assertIn("['name','CE']", html)
        self.assertIn("['wow','vs LW']", html)
        self.assertIn("['fourWeek','vs L4W']", html)
        self.assertIn("['yoy','vs LY']", html)
        self.assertIn("['target','vs Aug target']", html)
        self.assertIn("rows.slice(0,5)", html)
        self.assertIn("row.target_mtd_gap", html)
        self.assertNotIn('class="mover-seasonality ${tagClass(row.seasonality_tag)}"', html)
        self.assertNotIn('class="sort-select" data-mover-sort', html)
        self.assertIn('id="all-ces-view"', html)
        self.assertIn("const CE_METRICS", html)
        self.assertIn("const CE_SUB_SORTS", html)
        self.assertIn("data-ce-sort=\"${metric.key}\"", html)
        self.assertIn('data-ce-sort="${metric.key}:${spec.key}"', html)
        self.assertIn("function ceSortValue", html)
        self.assertIn('id="ce-expand-metrics"', html)
        self.assertIn('id="ce-filter-toggle"', html)
        self.assertIn('id="ce-filter-panel"', html)
        self.assertIn('class="ce-context-controls"', html)
        self.assertNotIn('id="ce-bdm"', html)
        self.assertNotIn('id="ce-growth"', html)
        self.assertIn('class="ce-hover-revenue"', html)
        self.assertIn('data-ce-expand="${metric.key}"', html)
        self.assertIn("const ceMetricExpanded", html)
        self.assertIn("function ceRevealMetric", html)
        self.assertIn('class="ce-static-trend"', html)
        self.assertIn('id="ce-filter-chips"', html)
        self.assertIn('id="ce-group"', html)
        self.assertIn('id="ce-detail-root"', html)
        self.assertIn('id="ce-pagination"', html)
        self.assertIn('pageSize:50', html)
        self.assertIn('id="ce-manage-portfolio"', html)
        self.assertIn('id="portfolio-root"', html)
        self.assertIn('id="portfolio-file"', html)
        self.assertIn('id="portfolio-preview"', html)
        self.assertIn('id="ce-watch-only"', html)
        self.assertIn('value="__custom_group"', html)
        self.assertIn("const portfolioStorageKey", html)
        self.assertIn("function ensurePortfolioMetadata", html)
        self.assertIn("function buildPortfolioPreview", html)
        self.assertIn("function loadPortfolioExample", html)
        self.assertIn('data-portfolio-demo="load"', html)
        self.assertIn('data-ce-watch="${escapeHtml(ce.ce_id)}"', html)
        self.assertIn("{key:'__tag',label:'Custom tags'", html)
        self.assertIn("{key:'delta',label:'Change'}", html)
        self.assertIn("{key:'wow',label:'WoW %'}", html)
        self.assertIn("{key:'yoy',label:'YoY %'}", html)
        self.assertIn('Apply locally', html)
        self.assertIn('id="ce-weekly-evidence"', html)
        self.assertIn('id="ce-resource-sections"', html)
        self.assertIn("Top experiences · TGIDs", html)
        self.assertIn("Lead-time bands", html)
        self.assertNotIn("remain in the existing V1 drawer", html)
        self.assertNotIn("Top revenue movers", html.split('id="detail-root"', 1)[1])

    def test_ce_ownership_dimensions_require_an_explicit_sidecar(self):
        ce_id = self.market["ces"][0]["ce_id"]
        without_sidecar = headline_v2.build_headline_view(self.market)["all_ces"][0]
        with_sidecar = headline_v2.build_headline_view(
            self.market,
            ce_dimensions={ce_id: {"bdm_region": "BDM West", "growth_region": "Growth Core"}},
        )["all_ces"][0]

        self.assertIsNone(without_sidecar["bdm_region"])
        self.assertIsNone(without_sidecar["growth_region"])
        self.assertEqual(with_sidecar["bdm_region"], "BDM West")
        self.assertEqual(with_sidecar["growth_region"], "Growth Core")

    def test_ce_drawer_cvr_uses_the_same_lp_to_order_source_as_funnel(self):
        market = copy.deepcopy(self.market)
        ce = market["ces"][0]
        ce["funnel"] = {
            "CVR": {"current": 1.42, "wm1": 1.17, "wow": 0.25, "yoy": -0.08}
        }
        ce["weekly"][-1]["overall_cvr_pct"] = 8.8

        projected = headline_v2.build_headline_view(market)["all_ces"][0]
        cvr = next(
            row for row in projected["drawer_metrics"]["overall"]
            if row["key"] == "funnel_cvr_pct"
        )

        self.assertEqual(cvr["label"], "LP→Order CVR")
        self.assertEqual(cvr["w0"], 1.42)
        self.assertEqual(cvr["wm1"], 1.17)
        self.assertEqual(cvr["delta_pct"], 0.25)
        self.assertEqual(cvr["delta_kind"], "pp")
        self.assertEqual(cvr["series"], [])

    def test_existing_movers_are_normalized_without_recalculation(self):
        view = headline_v2.build_headline_view(self.market)

        self.assertEqual(view["movers"]["drops"][0]["ce_name"], "Example Museum")
        self.assertEqual(view["movers"]["drops"][0]["primary_delta"], -30_000)
        self.assertEqual(view["movers"]["drops"][0]["primary_lens"], "vs last week")
        self.assertIsNone(view["movers"]["drops"][0]["seasonality_tag"])
        self.assertEqual(view["movers"]["drops"][0]["source_rank"], 1)
        self.assertEqual(
            view["movers"]["drops"][0]["source_path"],
            "market_summary.headlines.week_header.trend.top_droppers",
        )
        self.assertEqual(view["movers"]["gains"][0]["primary_delta"], 50_000)

    def test_dense_snapshot_drives_drawer_metrics_shapley_and_rich_movers(self):
        with gzip.open(DENSE_FIXTURE, "rt") as fixture:
            market = json.load(fixture)

        view = headline_v2.build_headline_view(market)
        metric_keys = [metric["key"] for metric in view["detail"]["metrics"]]

        self.assertEqual(metric_keys[:6], ["revenue", "gbv", "orders", "aov", "cr_pct", "tr_pct"])
        self.assertEqual(len(view["detail"]["metrics"][0]["series"]), 12)
        self.assertEqual(
            [factor["key"] for factor in view["detail"]["shapley"]["factors"]],
            ["traffic", "cvr", "aov", "cr", "tr"],
        )
        first_drop = view["movers"]["drops"][0]
        source_header = market["market_summary"]["headlines"]["week_header"]
        source_drop = source_header["trend"]["top_droppers"][0]
        self.assertEqual(first_drop["primary_delta"], -19_532)
        self.assertEqual(first_drop["primary_lens"], "vs trailing 4w")
        self.assertEqual(first_drop["seasonality_tag"], source_drop["tag"])
        self.assertEqual(first_drop["wow_abs"], -4_858)
        self.assertEqual(first_drop["source_rank"], 1)
        self.assertEqual(
            first_drop["source_path"],
            "market_summary.headlines.week_header.trend.top_droppers",
        )
        self.assertIn("V1 dual-lens ranking", first_drop["ranking_method"])

        metrics = view["detail"]["metrics"]
        self.assertEqual(
            [metric["key"] for metric in metrics],
            [
                "revenue", "gbv", "orders", "aov", "cr_pct", "tr_pct",
                "paid_clicks", "paid_cvr", "paid_conv_value", "avg_cm1", "paid_roi", "roi1",
            ],
        )
        self.assertFalse(next(metric for metric in metrics if metric["key"] == "orders")["paid"])
        self.assertTrue(next(metric for metric in metrics if metric["key"] == "paid_clicks")["paid"])

        ce = next(row for row in view["all_ces"] if row["buckets"])
        self.assertIn("subcategory", ce)
        self.assertIn("tier", ce)
        self.assertIn("lifecycle", ce)
        self.assertEqual(set(ce["periods"]), {"w0", "w1", "ly"})
        self.assertIn("revenue", ce["periods"]["w0"])
        self.assertIn("drawer_metrics", ce)
        self.assertIn("channels", ce)
        self.assertIn("funnel", ce)
        self.assertIn("tgids", ce)
        self.assertIn("leadtime", ce)
        self.assertIn("country_mix", ce)
        self.assertTrue(all(set(bucket) == {"key", "label", "family"} for bucket in ce["buckets"]))

    def test_current_v1_seasonality_tag_is_passed_through_without_reclassification(self):
        with gzip.open(DENSE_FIXTURE, "rt") as fixture:
            market = json.load(fixture)
        source = market["market_summary"]["headlines"]["week_header"]["trend"]["top_droppers"][0]
        source["tag"] = ""
        source["ly_wow"] = 999_999

        first_drop = headline_v2.build_headline_view(market)["movers"]["drops"][0]

        self.assertEqual(first_drop["seasonality_tag"], "")

    def test_v1_market_drawer_backfills_legacy_orders_aov_and_average_cm1(self):
        market = copy.deepcopy(self.market)
        metrics = market["market_summary"]["headlines"]["key_metrics"]
        metrics.pop("aov", None)
        for index, row in enumerate(market["market_summary"]["weekly"]):
            row.update({"orders": 100 + index, "aov": 80 + index, "cm1": 2_000 + index * 100, "paid_conversions": 40})

        view = headline_v2.build_headline_view(market)
        by_key = {metric["key"]: metric for metric in view["detail"]["metrics"]}

        self.assertEqual(by_key["orders"]["w0"], 111)
        self.assertEqual(by_key["aov"]["w0"], 91)
        self.assertEqual(by_key["avg_cm1"]["w0"], 77.5)
        self.assertNotIn("orders", metrics)
        self.assertNotIn("avg_cm1", metrics)

    def test_v2_template_uses_oak_eevee_foundation(self):
        template = Path(render_v2.TEMPLATE).read_text()

        self.assertIn("--font-display:halyard-display", template)
        self.assertIn("--font-text:halyard-text", template)
        self.assertIn("--purple:#8000ff", template)
        self.assertIn("--purple-soft:#f3e9ff", template)
        self.assertIn("--radius-control:8px", template)
        self.assertIn("--radius-card:16px", template)
        self.assertIn("--radius-hero:20px", template)
        self.assertNotIn("Hanken Grotesk", template)
        self.assertNotIn("#6d2cff", template.lower())
        self.assertIsNone(re.search(r"transition\s*:\s*all\b", template, re.I))

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
