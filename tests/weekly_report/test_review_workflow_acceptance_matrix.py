import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = ROOT / "docs/weekly-review/review-workflow-design-mockup.html"
INVENTORY = ROOT / "docs/weekly-review/ui-first-control-inventory.md"


class ReviewWorkflowAcceptanceMatrixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = MOCKUP.read_text()
        cls.inventory = INVENTORY.read_text()

    def test_all_required_lifecycle_states_have_deterministic_fixtures(self):
        for state in ("loading", "failure", "none", "prior", "current", "startnew", "multiple"):
            with self.subTest(state=state):
                self.assertIn(f'value="{state}"', self.html)
                self.assertIn(state, self.inventory)

    def test_discovery_never_infers_no_thread(self):
        self.assertIn("Checking for an existing CE thread", self.html)
        self.assertIn("Could not check the existing CE thread", self.html)
        self.assertIn("never assumes this means no thread", self.html)
        self.assertIn('data-thread-action="retry"', self.html)

    def test_prior_and_current_thread_choices_are_explicit(self):
        for copy in (
            "Continue Slack discussion #1 (recommended)",
            "Start a new discussion",
            "Continue Slack discussion #",
            "Write the message to post in Slack",
        ):
            self.assertIn(copy, self.html)

    def test_start_new_requires_preview_and_preserves_provenance(self):
        for copy in (
            "Why start a new discussion?",
            "Confirmation preview · #adhoc-north-america",
            "@parag @varun @suren @rahul @pranathi",
            "Confirm new discussion",
            "Slack discussion #",
        ):
            self.assertIn(copy, self.html)

    def test_market_week_ce_and_draft_contract_are_visible(self):
        for copy in ("North America", "CE 3111", "w/c 16 Aug 2026", "#adhoc-north-america"):
            self.assertIn(copy, self.html)
        self.assertIn('id="observation"', self.html)
        self.assertIn("observationDraft", self.html)

    def test_nomination_is_local_and_has_candidate_selected_states(self):
        for copy in ("Search CE name or ID", "Add CE", "Selected this week", "Candidates", "Skipped / deferred", "Reviewed", "Defer", "Reopen"):
            self.assertIn(copy, self.html)
        self.assertNotIn("api.", self.html)

    def test_nomination_uses_explicit_row_action_and_preserves_queue_state(self):
        self.assertNotIn('id="addCe"', self.html)
        self.assertIn("data-queue-action", self.html)
        self.assertIn("ce.stage=b.dataset.queueAction==='defer'?'deferred':'selected'", self.html)
        self.assertNotIn("reason:'Selected this week'", self.html)

    def test_search_can_find_and_add_ce_outside_the_review_queue(self):
        for copy in (
            "ceDirectory",
            "Immersive Theatre - Las Vegas",
            "id:'1104 - Las Vegas'",
            "Cruises - Las Vegas",
            "Available to add",
            "data-add-directory",
            "Search by CE name or stable ID",
        ):
            self.assertIn(copy, self.html)
        self.assertIn("ces.push(ce)", self.html)
        self.assertIn("search.value=searchQuery", self.html)

    def test_search_has_explicit_state_and_clear_restores_all_groups(self):
        for copy in (
            'id="clearSearch"',
            "searchQuery=params.get('q')||''",
            "searchQuery=search.value",
            "searchQuery=''",
            "next.searchParams.delete('q')",
            "search.focus({preventScroll:true})",
        ):
            self.assertIn(copy, self.html)

    def test_every_editing_draft_is_scoped_by_market_week_and_stable_ce(self):
        for copy in (
            "north_america|2026-08-16|",
            "ceDraftState",
            "saveCeDraft()",
            "loadCeDraft()",
            "manualDraft",
            "slackDraft",
            "newThreadReason",
            "observationDraft",
            "summaryDraftText",
            "suggestionDrafts",
            "workDrafts",
        ):
            self.assertIn(copy, self.html)

    def test_completion_requires_discussion_and_triage_without_bulk_carry_forward(self):
        for copy in (
            "Start Slack or add a no-discussion reason",
            "noDiscussionReason",
            "data-finish-check",
            "focus({preventScroll:true})",
        ):
            self.assertIn(copy, self.html)
        self.assertNotIn('id="workManagement"', self.html)
        self.assertNotIn("Manage or carry forward", self.html)
        render = self.html.split("function renderAll()", 1)[1].split("search.oninput", 1)[0]
        self.assertNotIn("workManaged", render)

    def test_review_history_is_visible_in_queue_and_selected_ce_header(self):
        for copy in (
            "Never reviewed",
            "Last reviewed 9 Aug 2026 by Parag",
            "lastReviewed:'22 Aug 2026',reviewer:'Pranathi'",
            "if(ce.stage==='reviewed')return `Reviewed ${ce.lastReviewed} by ${ce.reviewer}`",
            'id="reviewHistory"',
            'class="review-meta"',
        ):
            self.assertIn(copy, self.html)

    def test_fixture_add_action_requires_a_local_explicit_draft(self):
        handler = self.html.split("addAction.onclick=", 1)[1].split("document.addEventListener", 1)[0]
        self.assertIn("manualKind='action'", handler)
        self.assertNotIn("openItems.push", handler)
        self.assertNotIn("New BGM action", self.html)
        self.assertIn("Create action", self.html)
        self.assertIn("cancelManual", self.html)

    def test_manual_action_editor_opens_below_trigger_without_document_jump(self):
        trigger = self.html.index('class="rv-add-row actions"')
        composer = self.html.index('class="manual-composer" id="manualComposer"')
        self.assertLess(trigger, composer)
        self.assertIn("manualText.focus({preventScroll:true})", self.html)

    def test_committed_work_controls_are_functional_local_handlers(self):
        for fragment in (
            "data-toggle-work", "data-edit-work", "data-save-work",
            "data-work-owner", "data-work-date", "data-work-status",
            "Reopen", "Completed",
        ):
            self.assertIn(fragment, self.html)

    def test_ce_memory_markup_is_preserved(self):
        for copy in ("Open CE Memory →", "Loading current source tabs", "The Review workspace remains usable while history loads."):
            self.assertIn(copy, self.html)
        self.assertNotIn("CE Memory", self.html.split("requirements.innerHTML", 1)[1].split("finishBtn", 1)[0])

    def test_bgm_observation_is_visible_and_one_click_to_edit(self):
        self.assertIn("BGM observation · Optional", self.html)
        self.assertNotIn('id="observationDetails"', self.html)
        self.assertIn("Add observation", self.html)
        self.assertIn("document.querySelector('#observationInput').focus({preventScroll:true})", self.html)

    def test_bgm_observation_uses_native_input_treatment(self):
        for copy in (
            "font-family:var(--font-text)",
            "font-size:13px",
            "line-height:20px",
            "font-weight:400",
            "padding:12px 14px",
            "border:1px solid var(--line-dark)",
            "border-radius:var(--radius-control)",
            "resize:vertical",
            "#observationInput::placeholder",
            "#observationInput:focus",
        ):
            self.assertIn(copy, self.html)

    def test_every_summary_has_exact_source_binding(self):
        for copy in (
            'data-discussion-id="${id}"',
            'data-ce-id="${selected}"',
            'data-market="north_america"',
            'data-week="2026-08-16"',
            "Summary pending for Slack discussion #${id}",
            "Previous discussion summaries · ${previousCount}",
            "authoritative CE Memory",
        ):
            self.assertIn(copy, self.html)

    def test_approved_summary_compacts_and_previous_history_moves_to_memory(self):
        for copy in (
            "approved-summary-compact",
            "View details",
            'aria-expanded="${details}"',
            "Open CE Memory",
            "summaryCards",
        ):
            if copy == "summaryCards":
                continue
            self.assertIn(copy, self.html)
        self.assertIn("follow-up${suggestions.length===1?'':'s'} suggested from Slack discussion #${latest.id}", self.html)

    def test_checkbox_has_visible_confirmation_and_undo(self):
        for copy in ("Marked “${x.text}” complete.", 'id="undoWork"', "actionFeedback.previous", "aria-live=\"polite\""):
            self.assertIn(copy, self.html)

    def test_approved_suggestions_have_unique_ids_and_visible_destinations(self):
        self.assertIn("function nextWorkId()", self.html)
        self.assertNotIn("id:'w'+Date.now()", self.html)
        self.assertIn("Approved and moved to ${destination}.", self.html)
        self.assertIn("actionTab=destination.toLowerCase()", self.html)

    def test_checkbox_moves_only_one_item_without_switching_tabs(self):
        toggle = self.html.split("document.querySelectorAll('[data-toggle-work]')", 1)[1].split(
            "const undoWork", 1
        )[0]
        self.assertIn("currentTab=actionTab", toggle)
        self.assertIn("actionTab=currentTab", toggle)
        self.assertNotIn("actionTab=x.status", toggle)

    def test_committed_rows_do_not_repeat_tab_status(self):
        renderer = self.html.split("function committedRows(items)", 1)[1].split("function allWork()", 1)[0]
        self.assertNotIn('<span class="status-chip">${x.status}</span>', renderer)
        self.assertIn('data-work-status', self.html)

    def test_multiple_discussions_keep_independent_summary_states(self):
        self.assertIn("summaryStates[1]='approved'", self.html)
        self.assertIn("summaryStates[2]='pending'", self.html)
        self.assertIn("summaryStates[activeId]='loading'", self.html)
        self.assertIn("discussionRecords:JSON.parse(JSON.stringify(discussionRecords))", self.html)


if __name__ == "__main__":
    unittest.main()
