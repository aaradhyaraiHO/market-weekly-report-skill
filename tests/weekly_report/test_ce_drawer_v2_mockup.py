from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
MOCKUP = ROOT / "scripts" / "weekly_report" / "mockups" / "ce_drawer_v2_mockup.html"
MATRIX = ROOT / "thoughts" / "shared" / "weekly-report-v2" / "ce-drawer-parity-matrix.md"


class CeDrawerV2MockupContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = MOCKUP.read_text()
        cls.matrix = MATRIX.read_text()

    def test_mockup_is_sanitized_and_has_no_live_io(self):
        self.assertIn("Harbor Discovery Pass", self.html)
        self.assertNotIn("fetch(", self.html)
        self.assertNotIn("localStorage", self.html)
        self.assertNotIn("docs.google.com", self.html)
        self.assertNotIn("slack.com", self.html)

    def test_mockup_covers_v1_drawer_surfaces(self):
        for label in (
            "Overall", "Paid", "What moved revenue", "Funnel", "Channel mix",
            "Top experiences · TGIDs", "Lead-time bands", "Top countries",
            "Open in Omni",
        ):
            self.assertIn(label, self.html)

    def test_v1_baseline_precedes_grouped_roadmap_data_asks(self):
        self.assertIn("Weekly evidence · V1 baseline", self.html)
        self.assertIn("Resource tables · V1 baseline", self.html)
        self.assertIn("Roadmap data asks · iterate after parity", self.html)
        self.assertLess(self.html.index("Resource tables · V1 baseline"), self.html.index("Roadmap data asks · iterate after parity"))

    def test_first_fold_has_contextual_headline_and_large_revenue_trajectory(self):
        for label in (
            "Combined entity detail", "Predicted weekly revenue", "Versus last week",
            "−$18.6K · W-1 $145.0K", "LY base $116.6K", "Review · Perf",
            "12-week predicted revenue trajectory",
        ):
            self.assertIn(label, self.html)
        self.assertIn('id="hero-trend"', self.html)
        self.assertIn("renderHeroTrend", self.html)
        self.assertLess(self.html.index('id="summary"'), self.html.index('id="metrics"'))

    def test_drawer_uses_full_width_without_mockup_sidebar(self):
        self.assertNotIn('class="rail"', self.html)
        self.assertNotIn('aria-label="Drawer sections"', self.html)
        self.assertIn("grid-template-columns:minmax(0,1fr)", self.html)

    def test_metric_trend_is_a_line_with_expandable_weekly_data(self):
        self.assertIn('class="trend-line"', self.html)
        self.assertIn('data-trend-detail=', self.html)
        self.assertIn("12-week trend · open data", self.html)
        self.assertIn('class="ly-dot"', self.html)
        self.assertIn('class="trend-legend"', self.html)
        self.assertIn("Both use one shared scale", self.html)
        self.assertNotIn('class="spark"', self.html)

    def test_trends_have_hover_and_keyboard_tooltips(self):
        self.assertIn('id="trend-tooltip"', self.html)
        self.assertIn('data-ty=', self.html)
        self.assertIn('data-ly=', self.html)
        self.assertIn("pointermove", self.html)
        self.assertIn("focusin", self.html)

    def test_trends_use_filled_plot_and_nearest_week_cursor(self):
        self.assertIn('class="trend-area"', self.html)
        self.assertIn('class="trend-cursor"', self.html)
        self.assertIn("function updateTrendCursor", self.html)
        self.assertIn('data-hover-ty', self.html)
        self.assertIn('data-hover-ly', self.html)

    def test_resource_trends_are_labeled_as_data_extensions(self):
        self.assertEqual(self.html.count('class="data trendable-table"'), 4)
        self.assertIn("12W trend · data extension", self.html)
        self.assertIn("12-week channel, funnel, lead-time and country series need historical resource sidecars", self.html)

    def test_slack_context_card_is_removed(self):
        self.assertNotIn("CE-scoped Slack context", self.html)
        self.assertNotIn("#market-north-coast", self.html)

    def test_resources_are_stacked_and_tgid_bands_are_collapsible(self):
        self.assertNotIn('class="resource-tabs"', self.html)
        self.assertNotIn("data-resource=", self.html)
        for band in ("size", "value", "funnel", "booking"):
            self.assertIn(f'data-band-toggle="{band}"', self.html)
            self.assertIn(f'data-band-col="{band}"', self.html)
        self.assertIn("Share sub-lines are WoW / YoY pp", self.html)

    def test_collapsed_tgid_bands_use_stable_v1_ellipsis_fallback(self):
        self.assertIn("function prepareBandFallbacks()", self.html)
        self.assertIn("cell.textContent='•••'", self.html)
        self.assertIn("prepareBandFallbacks();", self.html)
        self.assertIn(".band-head.collapsed{width:48px}", self.html)

    def test_tgid_expand_restores_full_fields_and_keeps_explicit_state(self):
        for label in (
            "W-1", "−11% WoW", "−1.8pp / +2.4ppy", "−0.7pp", "+0.5pp",
        ):
            self.assertIn(label, self.html)
        self.assertEqual(self.html.count('aria-controls="tgid-body"'), 4)
        self.assertIn("const tgidBandState={size:true,value:true,funnel:true,booking:true}", self.html)
        self.assertIn("tgidBandState[band]=!open", self.html)
        self.assertIn("complete V1 metrics and band controls", self.html)

    def test_variants_expand_under_their_source_linked_tgid(self):
        self.assertIn("Experience / Variant", self.html)
        self.assertIn("Expand a TGID to reveal its source-linked variants in the same columns", self.html)
        for label in (
            'data-variant-toggle="TG-4108"', 'data-variant-toggle="TG-7742"',
            'id="variants-TG-4108"', 'id="variants-TG-7742"',
            "VAR-57670", "Morning harbor cruise", "VAR-44102", "<th data-band-col=\"size\">Orders</th>",
        ):
            self.assertIn(label, self.html)
        for removed in ("Top variants", "variant-shell", "LP→Order CVR"):
            self.assertNotIn(removed, self.html)
        self.assertEqual(self.html.count('class="variant-detail variant-row"'), 5)
        self.assertIn('document.querySelectorAll(`[data-variant-group="${group}"]`)', self.html)
        self.assertIn("details.forEach(detail=>{detail.hidden=open})", self.html)
        self.assertIn('data-expanded-cols="4"', self.html)

    def test_variant_rows_align_to_tgid_bands_and_fail_closed(self):
        for label in (
            'data-variant-group="TG-4108"', 'data-band-col="size"',
            'data-band-col="value"', 'data-band-col="funnel"',
            'data-band-col="booking"', "RPC requires TGID-grain funnel data",
            "Select users are unavailable below TGID grain", "TGID only",
        ):
            self.assertIn(label, self.html)
        self.assertIn("RPC and funnel remain TGID-only and render as unavailable", self.html)
        self.assertGreaterEqual(self.html.count('class="source-na"'), 25)

    def test_variant_fixture_totals_reconcile_to_tgid_parents(self):
        for total in (
            "Child totals: $54.2K · 1,086 orders · 42.9% share",
            "Child totals: $39.7K · 734 orders · 31.4% share",
        ):
            self.assertIn(total, self.html)
        self.assertIn("unattributed bucket when the source ID is null", self.html)
        self.assertIn("zero Revenue and Order difference", self.matrix)
        self.assertIn("never project TGID funnel values onto variants", self.matrix)

    def test_channel_returns_to_scan_friendly_revenue_mix(self):
        for label in (
            "Google Search", "Bing", "Direct (App)", "Referral", "CPR",
            "<th>Rev</th>", "<th>W-1</th>", "<th>WoW</th>",
            "<th>YoY</th>", "<th>Share</th>", "−2pp WoW · −3pp YoY",
        ):
            self.assertIn(label, self.html)
        self.assertNotIn("comparison extension", self.html)
        self.assertNotIn("Order share", self.html)

    def test_lead_time_splits_same_day_and_keeps_compact_comparisons(self):
        for band in ("0 days", "1–2 days", "3–4D", "5–7D", "7D+"):
            self.assertIn(f'<td class="metric-name">{band}', self.html)
        for removed in ("Same day", "Next day", "90+ days", "requested 8-band view"):
            self.assertNotIn(removed, self.html)
        for label in (
            "<th>Orders · W0</th>", "<th>Revenue · W0</th>",
            'data-trend-value-col="4"', 'data-trend-current="$20.8K"',
            "Same-day availability", "Near-term availability",
        ):
            self.assertIn(label, self.html)
        self.assertNotIn('<td class="metric-name">0–2D</td>', self.html)
        self.assertIn("integer `lead_time_days` supports distinct `0 days` and `1–2 days`", self.matrix)
        self.assertIn('class="lead-total"', self.html)

    def test_countries_keep_v1_orders_revenue_share_and_aov_shape(self):
        self.assertIn("Top countries</h3>", self.html)
        self.assertIn("Orders and actual revenue with WoW movement", self.html)
        for label in (
            "<th>Orders</th>", "<th>Rev</th>", "<th>Share</th>",
            "<th>AOV</th>", "Spain", "842", "$49.8K", "$59.14",
            'data-trend-value-col="3"', 'data-trend-current="$49.8K"',
        ):
            self.assertIn(label, self.html)
        self.assertNotIn("LY comparison", self.html)
        self.assertNotIn("W-1 925 · LY 791", self.html)

    def test_comment_and_action_ui_is_owned_by_review_mode_worktree(self):
        for removed in ("Notes and action history", "GM note", "Note history", "Action log · Perf"):
            self.assertNotIn(removed, self.html)

    def test_data_asks_are_grouped_outside_the_v1_baseline(self):
        for request in ("A3", "A7", "B4", "B7", "B11", "B12", "D5", "E1", "E2", "G11"):
            self.assertIn(request, self.html)
        self.assertIn("These are deliberately grouped outside the V1 baseline", self.html)
        self.assertNotIn("Languages · planned", self.html)
        self.assertNotIn("Launch QA · planned", self.html)

    def test_matrix_names_every_drawer_feedback_item(self):
        for request in ("A3", "A7", "A10", "B4", "B11", "B12", "E6", "E9", "E11", "G11"):
            self.assertIn(f"| {request} |", self.matrix)

    def test_matrix_assigns_every_v1_contract_an_explicit_disposition(self):
        expected = {
            "Entry points": "Missing parity",
            "Drawer lifecycle": "Mock-only",
            "CE identity and Omni": "Mock-only",
            "Watchlist": "Mock-only",
            "Revenue headline": "Present",
            "Key metrics": "Present",
            "Metric hover evidence": "Present",
            "Overall-CVR definition": "Missing parity",
            "WoW Shapley": "Present",
            "Channel mix": "Present",
            "Funnel": "Present",
            "Top experiences / TGIDs": "Present",
            "Lead-time mix": "Present",
            "Customer-country mix": "Present",
            "Slack context": "Intentionally excluded",
            "Current weekly note": "Delegated",
            "Slack note post": "Delegated",
            "Note history": "Delegated",
            "Perf action history": "Delegated",
            "Action-store compatibility": "Delegated",
            "Graceful absence": "Missing parity",
        }
        for capability, disposition in expected.items():
            self.assertIn(f"| {capability} | {disposition} |", self.matrix)

    def test_matrix_records_known_nonvisual_gaps_and_no_stale_sidebar(self):
        for gap in (
            "All-CE, movers, buckets, and follow-ups",
            "Focus trap/return, Escape, scrim close, scroll lock",
            "shared key/shape and repaint contract",
            "`ce.weekly`/`weekly_ly`",
            "`LY n/a`",
            "Canonical source definition must be resolved upstream",
            "review-mode worktree",
            "Removed following product feedback",
        ):
            self.assertIn(gap, self.matrix)
        self.assertNotIn("section rail", self.matrix.lower())


if __name__ == "__main__":
    unittest.main()
