from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NOTES = ROOT / "scripts" / "weekly_report" / "notes"
COMBINED_BACKEND = NOTES / "apps_script.js"
REVIEW_BACKEND = NOTES / "review_apps_script.js"
REVIEW_CLIENT = NOTES / "review_client.js"
REVIEW_PROXY = NOTES / "review_proxy_api.js"
ACTIONS_PROXY = NOTES / "actions_proxy_api.js"
GRANOLA_ADAPTER = NOTES / "granola_review_adapter.js"
REVIEW_VIEW = ROOT / "scripts" / "weekly_report" / "review" / "review-view.js"
REVIEW_CSS = ROOT / "scripts" / "weekly_report" / "review" / "review-view.css"
NATIVE_API = ROOT / "scripts" / "weekly_report" / "review-app" / "src" / "api.ts"
NATIVE_VIEW = ROOT / "scripts" / "weekly_report" / "review-app" / "src" / "review.tsx"
CANONICAL_MOCKUP = ROOT / "docs" / "weekly-review" / "review-tab-redesign-mockup.html"


def route_actions(source: str) -> set[str]:
    """Return only literal Apps Script route comparisons, not helper names."""
    return set(re.findall(r'action\s*={2,3}\s*["\']([^"\']+)["\']', source))


class ReviewBackendIsolationContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.combined = COMBINED_BACKEND.read_text()
        cls.review = REVIEW_BACKEND.read_text()
        cls.client = REVIEW_CLIENT.read_text()
        cls.proxy = REVIEW_PROXY.read_text()
        cls.actions_proxy = ACTIONS_PROXY.read_text()
        cls.granola = GRANOLA_ADAPTER.read_text()

    def test_review_backend_contains_only_review_routes(self):
        routes = route_actions(self.review)
        legacy_routes = {
            "list",
            "upsert",
            "delete",
            "post",
            "action_list",
            "action_upsert",
            "action_delete",
        }
        self.assertTrue(routes, "isolated Review Apps Script must expose explicit routes")
        self.assertTrue(
            any(route.startswith("review_") for route in routes),
            "isolated artifact has no Review routes",
        )
        self.assertEqual(routes & legacy_routes, set())
        self.assertNotIn("action_upsert", self.review)
        self.assertNotIn("action_delete", self.review)

    def test_combined_backend_keeps_the_v1_hotfix_contract(self):
        self.assertIn('var mutations = ["upsert", "delete", "post", "action_delete", "action_upsert"]', self.combined)
        self.assertIn("authenticated BGM identity required", self.combined)
        self.assertIn("reviewActorEmail(p), aNow", self.combined)

    def test_proxy_has_a_dedicated_fail_closed_review_configuration(self):
        for variable in ("REVIEW_MODE_APPS_SCRIPT_URL", "REVIEW_MODE_PROXY_SECRET"):
            self.assertIn(f"process.env.{variable}", self.proxy)
        self.assertNotIn("REVIEW_APPS_SCRIPT_URL", self.proxy)
        self.assertNotIn("REVIEW_PROXY_SECRET", self.proxy)
        self.assertNotIn("script.google.com/macros/s/", self.proxy)
        self.assertRegex(
            self.proxy.lower(),
            r'(isolated )?review backend (configuration )?(unavailable|misconfigured)',
        )

    def test_review_ingestion_uses_only_review_mode_secrets(self):
        self.assertIn("process.env.REVIEW_MODE_INGEST_SECRET", self.granola)
        self.assertNotRegex(self.granola, r"process\.env\.REVIEW_INGEST_SECRET\b")
        self.assertNotIn("process.env.REVIEW_PROXY_SECRET", self.granola)

    def test_review_client_never_calls_legacy_mutation_routes(self):
        for route in ("action_upsert", "action_delete", 'request("upsert"', 'request("post"'):
            self.assertNotIn(route, self.client)

    def test_review_work_delete_is_an_isolated_soft_delete(self):
        self.assertIn('action === "review_work_delete"', self.review)
        self.assertIn("deleted_at", self.review)
        self.assertIn('post("review_work_delete"', self.client)
        self.assertNotIn("action_delete", self.client)

    def test_review_mutations_use_post_and_get_is_read_only(self):
        for action in (
            "review_comment_upsert", "review_work_upsert", "review_work_delete",
            "review_weekly_note_upsert", "review_weekly_slack_post",
            "review_suggestion_decide",
        ):
            self.assertIn(f'post("{action}"', self.client)
            self.assertIn(f'"{action}"', self.review)
        self.assertIn('requires POST', self.review)

    def test_id_only_mutations_verify_signature_before_scope_enrichment(self):
        gate = self.review.split("function reviewMutationGate(action,p){", 1)[1].split(
            "function reviewUpsertBy", 1
        )[0]
        self.assertIn("var authenticated=reviewAuthenticatedActor(p);", gate)
        self.assertIn('action==="review_suggestion_decide"', gate)
        self.assertIn('p.market_slug=suggestion.market_slug', gate)
        self.assertLess(
            gate.index("var authenticated=reviewAuthenticatedActor(p);"),
            gate.index('action==="review_suggestion_decide"'),
        )
        # Scope is resolved after signature verification, then authorized with
        # the already verified identity—otherwise the enriched payload no
        # longer matches what the same-origin proxy signed.
        self.assertIn("authenticated.actor_email", gate)

    def test_proxy_uses_an_explicit_review_route_allowlist(self):
        self.assertIn("const REVIEW_ACTIONS = new Set([", self.proxy)
        self.assertIn("!REVIEW_ACTIONS.has(action)", self.proxy)
        self.assertNotIn('"action_upsert"', self.proxy)

    def test_diagnostic_actions_have_an_explicit_legacy_only_proxy(self):
        self.assertIn('const LEGACY_ACTIONS_URL = "https://script.google.com/macros/s/AKfycbyvXB69WxTM1p9qO4tQXxPfV28mkXOOiTKqW8J4SH2P_vtblTYd6bUQGJSb8HyLLGhOjA/exec"', self.actions_proxy)
        self.assertIn('process.env.ACTIONS_PROXY_SECRET', self.actions_proxy)
        self.assertIn('"action_list", "action_upsert", "action_delete"', self.actions_proxy)
        self.assertNotIn("REVIEW_MODE_APPS_SCRIPT_URL", self.actions_proxy)
        self.assertNotIn("REVIEW_MODE_PROXY_SECRET", self.actions_proxy)
        self.assertNotIn("REVIEW_APPS_SCRIPT_URL", self.actions_proxy)

    def test_review_proxy_rejects_diagnostic_actions(self):
        self.assertIn('const REVIEW_ACTION = /^review_/', self.proxy)
        self.assertIn('error: "review action required"', self.proxy)


class ReviewV0UiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = REVIEW_VIEW.read_text()
        cls.css = REVIEW_CSS.read_text()
        cls.mockup = CANONICAL_MOCKUP.read_text()

    def assert_ui_contract(self, fragment: str):
        self.assertIn(fragment, self.view)
        self.assertIn(fragment, self.mockup)

    def test_single_search_opens_any_ce_without_a_nomination_form(self):
        for fragment in (
            'id="rv-search-ce"',
            'type="search"',
            'data-select-ce',
            'ensureLocalCe(b.dataset.selectCe)',
            'renderAuditQueueRows',
        ):
            self.assertIn(fragment, self.view)


    def test_mentions_are_resolved_inline_and_ambiguity_is_visible(self):
        for fragment in ("api.resolveMentions", "rv-mention-status", "Use a full Slack name", "S.slackDrafts[ceId]!==text"):
            self.assertIn(fragment, self.view)
        self.assertIn("ambiguous Slack mentions", (ROOT / "scripts/weekly_report/notes/review_apps_script.js").read_text())

    def test_slack_summary_has_automatic_and_manual_paths(self):
        for fragment in ('id="rv-sync-thread"','Summarize discussion','api.syncWeeklyDiscussion'):
            self.assertIn(fragment,self.view)
        self.assertIn('installReviewAutomation', REVIEW_BACKEND.read_text())


    def test_slack_and_granola_suggestions_are_source_attributed(self):
        for fragment in ('api.suggestions','source_url','source_author','source_type','data-suggestion'):
            self.assertIn(fragment,self.view)


    def test_work_items_support_edit_delete_and_scheduled_dates(self):
        for fragment in (
            "data-work-edit",
            "data-work-delete",
            'type="date"',
            "Choose the next review date",
        ):
            self.assert_ui_contract(fragment)

    def test_ce_memory_preserves_perf_as_read_only_or_unavailable(self):
        for fragment in ('CE memory','Historical record · read-only','Performance history source is unavailable'):
            self.assertIn(fragment,self.view)
        memory=self.view.split('function ceMemoryEntries',1)[1].split('global.weeklyCeMemoryEntries',1)[0]
        self.assertNotRegex(memory,r'savePerf|upsertPerf|deletePerf')


    def test_ce_drawer_navigation_captures_visible_local_drafts(self):
        self.assertIn("function captureVisibleDrafts()", self.view)
        self.assertIn(
            "S.roleDrafts[roleDraftKey(el.dataset.roleInput)] = el.value", self.view
        )
        self.assertRegex(
            self.view,
            r"function openAnalyticsDrawer\(ceId\) \{\s+captureVisibleDrafts\(\);",
        )



    def test_queue_rows_have_no_nested_interactive_targets(self):
        row=self.view.split('function renderAuditQueueRows',1)[1].split('function renderPickerResults',1)[0]
        self.assertNotIn('role="link"',row)
        self.assertIn('data-select-ce',row)
        self.assertNotIn('data-open-drawer-ce',row)


    def test_next_ce_prefers_selected_then_candidates(self):
        next_ce = self.view.split("function nextCe()", 1)[1].split(
            "function openMemory()", 1
        )[0]
        self.assertIn('state==="selected"?0', next_ce)
        self.assertIn('state==="candidate"?1', next_ce)



    def test_core_completion_has_no_outcome_authoring_dependency(self):
        main=self.view.split('function renderMain()',1)[1].split('function completionBlockers',1)[0]
        for fragment in ('renderFinishBar','renderOutcomeCard','renderTreatment'):
            self.assertNotIn(fragment,main)
        self.assertIn('renderActionsCard(q)',main)


    def test_ce_memory_presents_two_user_oriented_histories(self):
        for fragment in ('ceMemoryWeeks','Week of ','Follow-through','Sources ·',"disclosure('memory',false)"):
            self.assertIn(fragment,self.view)
        self.assertNotIn('function renderMemoryDrawer',self.view)


    def test_nomination_requires_reason_and_uses_stable_ce_id(self):
        queue=self.view.split('function renderAuditQueueRows',1)[1].split('function renderPickerResults',1)[0]
        self.assertIn('ce.ce_id',queue)
        self.assertNotIn('rv-nomination-reason',queue)


    def test_pilot_telemetry_is_fail_soft_and_covers_core_funnel(self):
        self.assertIn("function track(event,fields)", self.view)
        self.assertIn(".catch(function(){})", self.view)
        for event in (
            "treatment_selected", "slack_discussion_started",
            "suggestion_triaged", "action_closed",
            "review_completed", "review_return_usage",
        ):
            self.assertIn(f'"{event}"', self.view)

    def test_action_inbox_deduplicates_and_hides_trace_by_default(self):
        self.assertIn("function dedupeSuggestions(rows)", self.view)
        self.assertIn("normalizedSuggestionBody", self.view)
        self.assertIn('class="rv-trace"', self.view)
        self.assertIn("matching sources", self.view)
        self.assertIn("Actions", self.view)
        action_card = self.view.split("function renderActionsCard", 1)[1].split("function workRow", 1)[0]
        self.assertIn("dedupeSuggestions(sugg.filter", action_card)
        self.assertNotIn("esc(s.source_ref || s.source_author || \"source\")", action_card)
        self.assertIn("rv-suggestion-text", action_card)
        self.assertIn("data-sugg-edit", action_card)
        self.assertNotIn("data-sugg-expand", action_card)



    def test_memory_loading_is_structured_and_fail_soft(self):
        self.assertIn('Loading CE history',self.view)
        self.assertIn('Previously loaded records remain below',self.view)
        self.assertIn('loadMemoryInline',self.view)


    def test_native_review_uses_post_for_mutations_and_posts_to_slack(self):
        api = NATIVE_API.read_text()
        native = NATIVE_VIEW.read_text()
        self.assertIn('if (mutations.has(action)) return post(action, params);', api)
        for action in ("review_weekly_note_upsert", "review_weekly_slack_post", "review_work_upsert"):
            self.assertIn(f'"{action}"', api)
        self.assertIn("const startSlackDiscussion", native)
        self.assertIn("api.startSlackDiscussion", native)
        self.assertIn("Summarize now", native)
        self.assertIn("api.syncWeeklyDiscussion", native)


if __name__ == "__main__":
    unittest.main()
