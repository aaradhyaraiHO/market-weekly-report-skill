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
            "review_suggestion_decide", "review_granola_link_submit",
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

    def test_ce_search_and_add_are_present_and_wired(self):
        for fragment in (
            'id="rv-add-ce"',
            'id="rv-picker-input"',
            'type="search"',
            "data-pick-ce",
            "api.saveReviewSetItem",
        ):
            self.assert_ui_contract(fragment)

    def test_role_notes_and_slack_have_separate_composers(self):
        for role in ("bgm", "performance", "bdm"):
            self.assertIn(f'renderRoleNote(weekly,"{role}")', self.view)
        self.assertIn('id="rv-slack-message"', self.view)
        start_slack = self.view.split("function startSlack()", 1)[1].split("function syncThread()", 1)[0]
        self.assertIn('querySelector("#rv-slack-message")', start_slack)
        self.assertNotIn('querySelector("#rv-note")', start_slack)
        self.assertIn("discussion_text: text", self.view)

    def test_mentions_are_resolved_and_ambiguity_is_visible_before_posting(self):
        for fragment in (
            "api.resolveMentions",
            "rv-mention-preview",
            "rv-mention-ok",
            "rv-mention-ambiguous",
            "Post to Slack",
        ):
            self.assert_ui_contract(fragment)
        resolver = self.view.split("function startSlack()", 1)[1].split("function syncThread()", 1)[0]
        self.assertIn("resolveMentions", resolver)

    def test_slack_summary_has_automatic_and_manual_paths(self):
        for fragment in (
            'id="rv-sync-thread"',
            "Summarize now",
            "Automatic sync every 5 minutes",
            "api.syncWeeklyDiscussion",
        ):
            self.assert_ui_contract(fragment)

    def test_slack_and_granola_suggestions_are_source_attributed(self):
        self.assertIn("api.suggestions", self.view)
        for fragment in ("AI · Slack", "AI · Granola", "data-suggestion"):
            self.assert_ui_contract(fragment)
        self.assertRegex(self.view, r'kind\s*===\s*["\']action["\']')
        self.assertRegex(self.view, r'kind\s*===\s*["\']check["\']')

    def test_work_items_support_edit_delete_and_scheduled_dates(self):
        for fragment in (
            "data-work-edit",
            "data-work-delete",
            'type="date"',
            "Choose the next review date",
        ):
            self.assert_ui_contract(fragment)

    def test_ce_memory_preserves_perf_as_read_only_or_unavailable(self):
        for fragment in ("CE Memory", "Perf", "Performance history source unavailable"):
            self.assert_ui_contract(fragment)
        memory = self.view.split("function renderMemory(res)", 1)[1].split(
            "function wireMemory", 1
        )[0]
        self.assertNotRegex(memory, r"savePerf|upsertPerf|deletePerf")

    def test_ce_drawer_navigation_captures_visible_local_drafts(self):
        self.assertIn("function captureVisibleDrafts()", self.view)
        self.assertIn(
            "S.roleDrafts[roleDraftKey(el.dataset.roleInput)] = el.value", self.view
        )
        self.assertRegex(
            self.view,
            r"function openAnalyticsDrawer\(ceId\) \{\s+captureVisibleDrafts\(\);",
        )

    def test_ce_drawer_return_scrolls_only_the_bounded_queue(self):
        self.assertIn("function revealQueueSelection(ceId)", self.view)
        self.assertIn("panel.scrollTop += rowRect.bottom - panelRect.bottom", self.view)
        self.assertIn("active.focus({ preventScroll: true })", self.view)
        self.assertNotIn("active.scrollIntoView", self.view)
        self.assertIn("S.queueRevealUntil=Date.now()+2500", self.view)
        self.assertIn("revealQueueSelection(S.selected)", self.view)
        self.assertIn(".rv-queue-panel{max-height:", self.css)
        self.assertIn("overflow-y:auto", self.css)

    def test_narrow_queue_is_an_on_demand_ce_browser(self):
        for fragment in (
            'id="rv-browse-ces"', 'id="rv-close-queue"',
            'S.queueBrowse = true', 'S.queueBrowse = false',
        ):
            self.assertIn(fragment, self.view)
        self.assertIn(".rv-side{display:none;position:fixed", self.css)
        self.assertIn(".rv-side.open{display:flex", self.css)
        self.assertIn(".rv-mobile-current{display:flex", self.css)

    def test_queue_rows_have_no_nested_interactive_targets(self):
        row = self.view.split("function queueRow(q)", 1)[1].split(
            "function renderProcessPanel", 1
        )[0]
        self.assertNotIn('role="link"', row)
        self.assertEqual(row.count('data-open-drawer-ce="'), 1)
        self.assertIn('data-select-ce="', row)
        self.assertIn('class="rv-ce-details"', row)

    def test_queue_filters_are_local_and_cover_review_states(self):
        for fragment in (
            'queueFilter: "all"', '"needs_review"', '"in_progress"',
            '"reviewed"', 'id="rv-reason-filter"', 'id="rv-category-filter"',
            "function visibleQueueRows()",
        ):
            self.assertIn(fragment, self.view)

    def test_candidate_and_shortlist_reuse_existing_treatments(self):
        for fragment in (
            "function shortlistState(q)", 'return "candidate"',
            'return "selected"', 'return "skipped"', 'return "reviewed"',
            'id="rv-shortlist-guide"', "Recommended: 3–5 CEs. The BGM decides.",
            "function renderQueueGroups(rows)", "Selected this week", "Candidates",
            "Skipped / deferred", "Reviewed",
        ):
            self.assertIn(fragment, self.view)
        self.assertNotIn("review_candidate_upsert", self.view)
        self.assertNotIn("review_shortlist_upsert", self.view)

    def test_next_ce_prefers_selected_then_candidates(self):
        next_ce = self.view.split("function nextCe()", 1)[1].split(
            "function openMemory()", 1
        )[0]
        self.assertIn('state==="selected"?0', next_ce)
        self.assertIn('state==="candidate"?1', next_ce)

    def test_existing_thread_offers_explicit_continue_or_new_parent(self):
        for fragment in (
            'id="rv-continue-slack"', 'id="rv-new-slack"',
            'id="rv-new-thread-reason"', 'id="rv-new-thread-cancel"',
            "thread_operation", "replacement_reason",
            "Continue Slack discussion #", "Start a new discussion",
            "prior thread remains in CE Memory",
        ):
            self.assertIn(fragment, self.view)

    def test_slack_is_primary_and_compatibility_notes_remain_separate(self):
        card = self.view.split("function renderCommentaryCard(q)", 1)[1].split(
            "function normalizedSuggestionBody", 1
        )[0]
        self.assertIn("Discussion highlights", card)
        self.assertIn("rv-module-surface", card)
        self.assertIn("BGM observation · Optional", self.view)
        self.assertLess(card.index("+composer+"), card.index('renderRoleNote(weekly,"bgm")'))
        self.assertIn('renderRoleNote(weekly,"performance")', card)
        self.assertIn('renderRoleNote(weekly,"bdm")', card)
        role = self.view.split("function renderRoleNote(weekly,role)", 1)[1].split(
            "function renderWeeklySummary", 1
        )[0]
        self.assertIn('role!=="bgm"&&!saved)return ""', role)
        self.assertIn("Historical · read-only", role)

    def test_core_completion_has_no_outcome_authoring_dependency(self):
        for fragment in (
            "function completionBlockers(q)", "noDiscussionDrafts",
            'id="rv-no-discussion-reason"', "Triage ",
            "Assign/date or carry forward", "api.finishReview",
        ):
            self.assertIn(fragment, self.view)
        for fragment in ("function renderOutcomeCard", 'id="rv-outcome-type"', 'id="rv-outcome-decision"', 'id="rv-save-outcome"', "api.saveOutcome"):
            self.assertNotIn(fragment, self.view)
        self.assertNotIn("bgm_note) blockers.push", self.view)

    def test_follow_through_groups_and_timeline_are_progressive_and_local(self):
        for fragment in (
            "Actions &amp; follow-ups", "Needs review", "Open", "Later", "Completed",
            "suggested from ", "Slack discussion #", "rv-action-tabs",
            "rv-focus-summary", "timeline=res.timeline||[]",
            "rv-timeline-event",
        ):
            self.assertIn(fragment, self.view)
        self.assertIn(".rv-action-surface", self.css)
        self.assertIn(".rv-action-tab.active", self.css)
        self.assertNotIn('e.related_work_id?"Work "+e.related_work_id', self.view)

    def test_nomination_requires_reason_and_uses_stable_ce_id(self):
        for fragment in (
            'id="rv-nomination-reason"', "Add a nomination reason first",
            'source: "nomination"', 'event_type:"nomination"',
            'idempotency_key:"nomination:"+S.week_start+":"+String(ceId)',
        ):
            self.assertIn(fragment, self.view)

    def test_owner_and_task_force_filters_render_only_when_metadata_exists(self):
        self.assertIn("owners.length?", self.view)
        self.assertIn("taskForces.length?", self.view)
        self.assertIn('id="rv-owner-filter"', self.view)
        self.assertIn('id="rv-task-force-filter"', self.view)

    def test_pilot_telemetry_is_fail_soft_and_covers_core_funnel(self):
        self.assertIn("function track(event,fields)", self.view)
        self.assertIn(".catch(function(){})", self.view)
        for event in (
            "shortlist_size", "treatment_selected", "slack_discussion_started",
            "suggestion_triaged", "action_closed",
            "review_completed", "review_return_usage",
        ):
            self.assertIn(f'"{event}"', self.view)

    def test_action_inbox_deduplicates_and_hides_trace_by_default(self):
        self.assertIn("function dedupeSuggestions(rows)", self.view)
        self.assertIn("normalizedSuggestionBody", self.view)
        self.assertIn('class="rv-trace"', self.view)
        self.assertIn("matching sources", self.view)
        self.assertIn("Actions &amp; follow-ups", self.view)
        action_card = self.view.split("function renderActionsCard", 1)[1].split("function workRow", 1)[0]
        self.assertIn("dedupeSuggestions(sugg.filter", action_card)
        self.assertNotIn("esc(s.source_ref || s.source_author || \"source\")", action_card)
        self.assertIn("rv-suggestion-text", action_card)
        self.assertIn("data-sugg-edit", action_card)
        self.assertNotIn("data-sugg-expand", action_card)

    def test_approved_visual_hierarchy_keeps_source_and_state_distinct(self):
        summary = self.view.split("function renderWeeklySummary", 1)[1].split(
            "function renderCommentaryCard", 1
        )[0]
        actions = self.view.split("function renderActionsCard", 1)[1].split(
            "function workRow", 1
        )[0]
        for fragment in (
            "Draft summary", "Needs BGM approval", "Approve summary",
            "Discussion highlights", "Actions &amp; follow-ups",
        ):
            self.assertIn(fragment, self.view)
        self.assertIn("rv-summary-surface", summary)
        self.assertIn("rv-source-bridge", actions)
        self.assertIn("rv-suggestion-main", actions)
        self.assertIn("data-sugg-accept", actions)
        self.assertIn("data-sugg-ignore", actions)
        self.assertIn("position:static", self.css.split(".rv-footer", 1)[1].split("}", 1)[0])

    def test_completion_checklist_links_to_the_actual_controls(self):
        self.assertIn("function renderFinishBar", self.view)
        self.assertIn('data-resolve=', self.view)
        self.assertIn("function focusRequirement", self.view)
        self.assertIn('S.workTab="needs"', self.view)
        self.assertIn('data-work-tab="needs"', self.view)
        self.assertNotIn('id="rv-footer-treatment"', self.view)
        self.assertIn("Next unreviewed", self.view)
        self.assertEqual(self.view.count('id="rv-treatment"'), 1)

    def test_memory_loading_is_structured_and_fail_soft(self):
        self.assertIn("function renderMemoryLoading()", self.view)
        self.assertIn("Current Review stays usable", self.view)
        self.assertIn("missing history never blocks this report", self.view)
        self.assertIn(".rv-skeleton", self.css)

    def test_granola_stays_hidden_until_guarded_beta_is_approved(self):
        for fragment in (
            "Granola meeting",
            "WIP · meeting access is being connected",
            "api.ingestGranolaLink",
        ):
            self.assert_ui_contract(fragment)
        self.assertNotIn('id="rv-granola-toggle"', self.view)
        self.assertIn(".rv-granola-wip{display:none}", self.css)

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
