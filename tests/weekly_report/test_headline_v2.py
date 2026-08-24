from __future__ import annotations

import copy
import gzip
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

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
        self.assertEqual(view["all_ces"][0]["previous_revenue"], 100_000)
        self.assertEqual(view["all_ces"][0]["market"], "North America")
        self.assertEqual(view["all_ces"][0]["week_end"], "2026-08-08")

    def test_business_country_views_scope_the_entire_report_without_duplicating_ce_payloads(self):
        market = copy.deepcopy(self.market)
        market["ces"][0].setdefault("metadata", {}).update(
            {"country": "Canada", "region": "North America"}
        )
        market["ces"][1].setdefault("metadata", {}).update(
            {"country": "United States", "region": "North America"}
        )
        source = copy.deepcopy(market)

        view = headline_v2.build_headline_view(market)

        self.assertEqual(market, source)
        self.assertEqual(set(view["country_views"]), {"Canada", "United States"})
        self.assertEqual(view["all_ces"][0]["business_country"], "Canada")
        self.assertEqual(view["all_ces"][1]["business_country"], "United States")
        canada = view["country_views"]["Canada"]
        self.assertEqual(canada["country"], "Canada")
        self.assertNotIn("all_ces", canada)
        self.assertEqual(canada["revenue"], market["ces"][0]["weekly"][-1]["revenue"])
        self.assertEqual(canada["movers"]["drops"][0]["ce_id"], market["ces"][0]["ce_id"])

    def test_post_diagnostic_v1_outputs_are_projected_and_country_scoped(self):
        market = copy.deepcopy(self.market)
        canada_id = str(market["ces"][0]["ce_id"])
        us_id = str(market["ces"][1]["ce_id"])
        market["ces"][0].setdefault("metadata", {})["country"] = "Canada"
        market["ces"][1].setdefault("metadata", {})["country"] = "United States"
        market["seasonality_adjustments"] = [{"ce_id": canada_id, "ce_name": "Canada CE", "pct": 10}]
        market["levers"] = [{"ce_id": us_id, "ce_name": "US CE", "lever": "pp"}]
        market["no_bid_campaigns"] = {
            "totals": {"count": 2, "spend_total": 300},
            "rows": [
                {"ce_id": canada_id, "ce_name": "Canada CE", "spend_wk": 100},
                {"ce_id": us_id, "ce_name": "US CE", "spend_wk": 200},
            ],
        }
        market["prepurchase"] = [
            {"ce_id": canada_id, "ce": "Canada CE", "dated": 1},
            {"ce_id": us_id, "ce": "US CE", "dated": 2},
        ]
        source = copy.deepcopy(market)

        view = headline_v2.build_headline_view(market)

        self.assertEqual(market, source)
        self.assertEqual(view["post_diagnostic"]["no_bid_campaigns"]["totals"]["count"], 2)
        canada = view["country_views"]["Canada"]["post_diagnostic"]
        self.assertEqual([row["ce_id"] for row in canada["seasonality_adjustments"]], [canada_id])
        self.assertEqual(canada["levers"], [])
        self.assertEqual(canada["no_bid_campaigns"]["totals"], {"count": 1, "spend_total": 100})
        self.assertEqual([row["ce_id"] for row in canada["prepurchase"]], [canada_id])

    def test_diagnostic_buckets_preserve_v1_rows_and_country_scope(self):
        market = copy.deepcopy(self.market)
        canada_id = str(market["ces"][0]["ce_id"])
        us_id = str(market["ces"][1]["ce_id"])
        market["ces"][0].setdefault("metadata", {})["country"] = "Canada"
        market["ces"][1].setdefault("metadata", {})["country"] = "United States"
        market["buckets_final"] = {
            "defend": {
                "losing_money": {
                    "existing": [{"ce_id": canada_id, "ce_name": "Canada CE", "criteria": ["C2"]}],
                    "new": [{"ce_id": us_id, "ce_name": "US CE", "criteria": ["C5"]}],
                    "paused": [{"ce_id": canada_id, "ce_name": "Canada paused"}],
                    "tracking_gap": [],
                    "burn_line": {"count": 2, "bleed_wk": -50},
                },
                "seasonality_down": [{"ce_id": canada_id, "ce_name": "Canada CE", "signal": "rpc"}],
            },
            "compound": {
                "seasonality_up": [{"ce_id": us_id, "ce_name": "US CE", "signal": "cm1_per_conv"}],
            },
            "lifecycle": {
                "new_ces": [
                    {"ce_id": canada_id, "ce_name": "Canada New", "lane": "A_graduated"},
                    {"ce_id": us_id, "ce_name": "US New", "lane": "B_on_pace"},
                ],
                "iteration": [
                    {"ce_id": canada_id, "ce_name": "Canada Iteration", "lane": "iteration"},
                    {"ce_id": us_id, "ce_name": "US Untapped", "lane": "untapped"},
                ],
            },
        }
        source = copy.deepcopy(market)

        view = headline_v2.build_headline_view(market)

        self.assertEqual(market, source)
        self.assertEqual(view["diagnostic_buckets"]["losing_money"]["existing"][0]["criteria"], ["C2"])
        canada = view["country_views"]["Canada"]["diagnostic_buckets"]
        self.assertEqual([row["ce_id"] for row in canada["losing_money"]["existing"]], [canada_id])
        self.assertEqual(canada["losing_money"]["new"], [])
        self.assertEqual(canada["losing_money"]["burn_line"], {})
        self.assertEqual([row["ce_id"] for row in canada["fluctuations"]["down"]], [canada_id])
        self.assertEqual(canada["fluctuations"]["up"], [])
        self.assertEqual([row["ce_id"] for row in canada["lifecycle"]["new_ces"]], [canada_id])
        self.assertEqual([row["ce_id"] for row in canada["lifecycle"]["iteration"]], [canada_id])

    def test_legacy_key_metric_reconstructs_display_wm1_from_v1_wow(self):
        view = headline_v2.build_headline_view(self.market)
        revenue = next(metric for metric in view["detail"]["metrics"] if metric["key"] == "revenue")

        self.assertAlmostEqual(revenue["wm1"], 1_000_000)
        self.assertAlmostEqual(revenue["delta_abs"], 100_000)
        self.assertEqual(revenue["delta_pct"], 10.0)
        self.assertTrue(all(point["ly"] is None for point in revenue["series"]))

    def test_ce_drawer_projects_absolute_delta_from_v1_operands(self):
        view = headline_v2.build_headline_view(self.market)
        revenue = next(row for row in view["all_ces"][0]["drawer_metrics"]["overall"] if row["key"] == "revenue")

        self.assertEqual(revenue["w0"], 70_000)
        self.assertEqual(revenue["wm1"], 100_000)
        self.assertEqual(revenue["delta_abs"], -30_000)

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
        self.assertEqual(first_drop["target_mtd_attainment_pct"], 81.8)
        self.assertEqual(first_drop["monthly_target"], 210_000)
        self.assertAlmostEqual(first_drop["wow_pct"], -30.0)
        self.assertIsNone(first_drop["delta_4w_pct"])

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
        self.assertNotIn('aria-label="Country" disabled', html)
        self.assertIn("base.country_views", html)
        self.assertIn("ce.business_country===selectedCountry", html)
        self.assertIn("countrySelect.addEventListener('change'", html)
        self.assertIn("renderAllCes(currentHeadline())", html)
        self.assertIn('id="week-select" hidden aria-hidden="true" tabindex="-1"', html)
        self.assertNotIn('<span class="filter-label">Week</span>', html)
        self.assertIn('.ce-resource-table td:first-child .ce-metric-label { justify-content:flex-start; text-align:left; }', html)
        self.assertIn('.ce-cell-sub.positive { color:var(--green); }', html)
        self.assertIn('.ce-cell-sub.negative { color:var(--red); }', html)
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
        self.assertNotIn('<details class="pacing-details"', html)
        self.assertIn('id="drawer-pacing-section"', html)
        self.assertIn("Performance &amp; pacing", html)
        self.assertIn('id="targets-section"', html)
        self.assertIn('id="target-summary"', html)
        self.assertIn('id="target-comparisons"', html)
        self.assertNotIn('id="target-contributors"', html)
        self.assertIn('class="drawer-kpi"', html)
        self.assertLess(html.index("Key metrics · 12-week trend"), html.index("Performance &amp; pacing"))
        self.assertIn("function renderTargets", html)
        self.assertIn("vs same week last year", html)
        self.assertIn("Projected month-end", html)
        self.assertIn("weekly revenue`", html)
        self.assertIn('data-mover-kind="${kind}"', html)
        self.assertIn('data-mover-sort="${key}"', html)
        self.assertIn("const moverSorts", html)
        self.assertNotIn('data-mover-lens=', html)
        self.assertIn("['name','CE']", html)
        self.assertIn("['wow','vs LW %']", html)
        self.assertIn("['fourWeek','vs L4W %']", html)
        self.assertIn("['yoy','vs LY %']", html)
        self.assertIn("['target','Aug target %']", html)
        self.assertIn("rows.slice(0,5)", html)
        self.assertIn("row.target_mtd_attainment_pct", html)
        self.assertIn("Shows up to five CEs with the largest revenue drops or gains", html)
        self.assertIn("using whichever move is greater: versus last week or the trailing four-week average", html)
        self.assertIn("Sort any column for a different view", html)
        self.assertIn("select a CE to open its detail", html)
        self.assertNotIn("Default order preserves V1", html)
        self.assertNotIn("Compact-source reports", html)
        self.assertIn("Largest negative revenue moves · up to 5", html)
        self.assertIn("Largest positive revenue moves · up to 5", html)
        self.assertIn('data-mover-ce="${escapeHtml(row.ce_id)}"', html)
        self.assertIn("openCeDrawer(mover.dataset.moverCe)", html)
        self.assertNotIn('class="mover-seasonality ${tagClass(row.seasonality_tag)}"', html)
        self.assertNotIn('class="sort-select" data-mover-sort', html)
        self.assertIn('id="diagnostic-buckets"', html)
        self.assertIn('id="losing-money-section"', html)
        self.assertIn('id="fluctuations-section"', html)
        self.assertIn('id="new-ces-section"', html)
        self.assertIn('id="iteration-section"', html)
        self.assertIn("function renderDiagnosticBuckets", html)
        self.assertIn("item.diagnostic_buckets", html)
        self.assertIn("data-bucket-ce", html)
        self.assertIn("Losing Money", html)
        self.assertIn("RPC / CM1 fluctuations", html)
        self.assertIn("function renderNewCes", html)
        self.assertIn("function renderIteration", html)
        self.assertIn("New CEs", html)
        self.assertIn("Iteration / Untapped", html)
        self.assertIn("item.diagnostic_buckets?.lifecycle", html)
        self.assertIn("▸ Show weekly numbers", html)
        self.assertIn("▾ Hide weekly numbers", html)
        self.assertIn("let diagnosticWeeksHidden=true", html)
        self.assertIn('aria-controls="lm-week-wrap fluctuations-week-wrap"', html)
        self.assertIn('data-diagnostic-week-wrap', html)
        self.assertIn("wr_v2_diagnostic_wk_hidden", html)
        self.assertIn("Collapsed = this week + WoW", html)
        self.assertIn("CM1/conv · W0", html)
        self.assertIn("CPC · W0", html)
        self.assertIn("tROAS now", html)
        self.assertIn("CM2 · 90d", html)
        self.assertIn("W0 loss", html)
        self.assertIn("CM1/conv", html)
        self.assertIn("function bucketActionCell", html)
        self.assertIn("const ACTIONS_API='/api/actions'", html)
        self.assertNotIn("const ACTIONS_API='/api/review'", html)
        self.assertIn("credentials:'same-origin'", html)
        self.assertIn("Saved to Weekly Actions Sheet", html)
        self.assertIn("Add a comment to sync", html)
        self.assertIn("action:'action_upsert'", html)
        self.assertIn("action:'action_delete'", html)
        self.assertIn("action=action_list", html)
        self.assertNotIn("/api/review?action=action_list", html)
        self.assertIn("function actionPrevPull", html)
        self.assertIn("last wk: <strong>", html)
        self.assertIn("'losing_money'", html)
        self.assertIn("'flux_down'", html)
        self.assertIn("'flux_up'", html)
        self.assertIn("Actions save to the established Weekly Actions Sheet", html)
        self.assertIn("${pct(relative)} vs LW", html)
        self.assertNotIn("deltaFormat==='money'", html)
        self.assertIn('id="post-diagnostic-sections"', html)
        self.assertIn("Seasonality visibility", html)
        self.assertIn("Levers visibility", html)
        self.assertNotIn("No-bid campaigns", html)
        self.assertIn("(b) Prepurchase (dim_pp_allotments → CE)", html)
        self.assertIn("function renderPostDiagnostic", html)
        self.assertIn("item.post_diagnostic", html)
        self.assertIn("data-post-ce", html)
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
        self.assertIn("Weekly evidence · V1 baseline", html)
        self.assertIn("Predicted weekly revenue", html)
        self.assertIn('id="ce-drawer-omni"', html)
        self.assertIn("function wireCeChart", html)
        self.assertIn("data-ce-metric-detail", html)
        self.assertIn("Open in Omni", html)
        self.assertIn('id="ce-resource-sections"', html)
        self.assertIn("Top experiences · TGIDs", html)
        self.assertIn('class="ce-tgid-identity"', html)
        self.assertIn('class="ce-variant-kind">Variant', html)
        self.assertIn('class="ce-variant-reconcile"', html)
        self.assertIn('class="ce-metric-trend-button"', html)
        self.assertIn("${sparkline(row,false)}", html)
        self.assertIn("${open?'Hide':'View'} ${escapeHtml(row.label)} 12-week trend", html)
        self.assertIn("resourceTrend", html)
        self.assertIn('id="ce-metric-tooltip"', html)
        self.assertIn("wireCeSparklines", html)
        self.assertIn("event.key!=='ArrowLeft'", html)
        self.assertIn(".metric-spark:focus-visible", html)
        self.assertIn("focusable?'tabindex=\"0\"'", html)
        self.assertIn("interactionTarget=svg.closest('.ce-metric-trend-button')||svg", html)
        self.assertIn("sumResourceHistory", html)
        self.assertIn("12W · TY / LY", html)
        self.assertIn("ce-resource-trend", html)
        self.assertIn("font-size:12px", html)
        self.assertIn('[data-ce-band-col]:not([data-ce-band-secondary])', html)
        self.assertIn('data-ce-band="${key}"', html)
        self.assertIn('data-ce-band-col="${key}"', html)
        self.assertIn("ceTgidBands={size:true,value:true,funnel:true,booking:true}", html)
        self.assertIn("Lead-time bands", html)
        for band in ("0 days", "1–2 days", "3–4D", "5–7D", "7D+"):
            self.assertIn(band, html)
        self.assertIn('class="ce-lead-total"', html)
        self.assertNotIn("remain in the existing V1 drawer", html)
        self.assertNotIn("Top revenue movers", html.split('id="detail-root"', 1)[1])

    def test_weekly_actions_require_authenticated_sheet_sync(self):
        root = Path(__file__).resolve().parents[2]
        apps_script = (root / "scripts/weekly_report/notes/apps_script.js").read_text()
        proxy = (root / "scripts/weekly_report/notes/review_proxy_api.js").read_text()

        self.assertIn("function reviewMutationGate", apps_script)
        self.assertIn("authenticated BGM identity required", apps_script)
        self.assertIn("reviewActorEmail(p), aNow", apps_script)
        self.assertNotIn('p.owner || "", aNow', apps_script)

        self.assertIn("mmr_session", proxy)
        self.assertIn("REVIEW_PROXY_SECRET", proxy)
        self.assertIn('params.set("actor_sig", signature)', proxy)
        self.assertIn('action") === "whoami"', proxy)

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

    def test_funnel_shapley_exposes_the_mixed_source_residual(self):
        weekly = [
            {
                "revenue": 52_335.05, "orders": 1636, "completed_orders": 1608,
                "gbv": 233_678.94, "gbv_completed": 228_321.0,
            },
            {
                "revenue": 47_658.20, "orders": 1467, "completed_orders": 1451,
                "gbv": 203_592.88, "gbv_completed": 199_790.0,
            },
        ]
        funnel_levels = {
            "wm1": {"lp_users": 23_441, "order_users": 1379},
            "w0": {"lp_users": 21_859, "order_users": 1154},
        }

        result = headline_v2._funnel_revenue_shapley(weekly, funnel_levels)

        self.assertIsNotNone(result)
        self.assertEqual([row["label"] for row in result["factors"]], [
            "Traffic", "LP→Order CVR", "Order completion", "AOV", "Take rate",
        ])
        self.assertAlmostEqual(
            result["factor_total"] + result["residual"], result["net_delta"], places=1
        )
        self.assertNotEqual(result["residual"], 0)

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

    def test_compact_v1_mover_uses_authoritative_ce_w0_revenue(self):
        market = copy.deepcopy(self.market)
        headlines = market["market_summary"]["headlines"]
        rich_drop = headlines["week_header"]["trend"]["top_droppers"][0]
        headlines["top_drops"] = [{
            "ce_id": rich_drop["ce_id"],
            "ce_name": rich_drop["ce_name"],
            "delta_wow": rich_drop["raw_wow"],
        }]
        drop = headlines["top_drops"][0]
        market["market_summary"]["headlines"].pop("week_header", None)
        drop.pop("w0_rev", None)
        expected = market["ces"][0]["weekly"][-1]["revenue"]

        first_drop = headline_v2.build_headline_view(market)["movers"]["drops"][0]

        self.assertEqual(first_drop["ce_id"], market["ces"][0]["ce_id"])
        self.assertEqual(first_drop["revenue"], expected)
        self.assertEqual(first_drop["source_rank"], 1)
        self.assertEqual(first_drop["ranking_method"], "V1 raw WoW revenue ranking")

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
        revenue_metric = next(metric for metric in metrics if metric["key"] == "revenue")
        self.assertTrue(revenue_metric["has_ly"])
        self.assertTrue(any(point["ly"] is not None for point in revenue_metric["series"]))
        self.assertEqual(revenue_metric["ly_w0"], revenue_metric["series"][-1]["ly"])
        self.assertIsNotNone(revenue_metric["yoy_pct"])

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

    def test_v2_diagnostic_tables_are_readable_and_horizontally_scrollable(self):
        template = Path(render_v2.TEMPLATE).read_text()

        self.assertIn(".diagnostic-buckets { display:grid; grid-template-columns:minmax(0,1fr)", template)
        self.assertIn(".bucket-table-wrap { width:100%; min-width:0; max-width:100%; overflow-x:scroll", template)
        self.assertIn(".bucket-table-wrap::-webkit-scrollbar { height:14px; }", template)
        self.assertIn("scrollbar-gutter:stable", template)
        self.assertIn(".bucket-table { width:100%; min-width:1020px; border-collapse:collapse; font-size:13px", template)
        self.assertIn(".bucket-ce { padding:0; border:0; color:var(--ink); background:transparent; font-size:13px", template)
        self.assertIn(".bucket-subvalue.positive { color:var(--green); }", template)
        self.assertIn(".bucket-subvalue.negative { color:var(--red); }", template)
        self.assertIn("box-shadow:1px 0 0 var(--line-dark)", template)

    def test_v2_weekly_comparisons_use_relative_percentages_everywhere(self):
        template = Path(render_v2.TEMPLATE).read_text()

        self.assertIn("const relativePct =", template)
        self.assertIn("const relativePctFromPoints =", template)
        self.assertIn("every comparison is relative percentage change", template)
        self.assertNotIn("const cePp=", template)
        self.assertNotIn("percentage points", template)
        self.assertNotIn("Snapshot-backed", template)
        self.assertNotIn("ce-live-badge", template)

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

    def test_v2_reuses_v1_action_sidecar_without_writing_during_render(self):
        with mock.patch.dict(os.environ, {"WR_NOTES_SCRIPT_URL": "https://example.com/weekly-actions"}):
            html = render_v2.render([self.market])
        match = re.search(r'<script id="report-data" type="application/json">(.*?)</script>', html, re.S)
        embedded = json.loads(match.group(1))

        self.assertEqual(embedded["notes_url"], "https://example.com/weekly-actions")
        self.assertIn("action=action_list", html)
        self.assertNotIn("fetch(NOTES_URL,{method:'POST'", html)

    def test_diagnostic_actions_use_the_legacy_actions_proxy_not_review_mode(self):
        html = render_v2.render([self.market])
        self.assertIn("const ACTIONS_API='/api/actions'", html)
        self.assertNotIn("const ACTIONS_API='/api/review'", html)
        self.assertIn("action:'action_upsert'", html)
        self.assertIn("action:'action_delete'", html)
        self.assertIn("${ACTIONS_API}?${params.toString()}", html)
        self.assertIn("${ACTIONS_API}?action=action_list", html)
        self.assertNotRegex(html, r"/api/review[^\\n]*(?:action_upsert|action_delete|action_list)")


if __name__ == "__main__":
    unittest.main()
