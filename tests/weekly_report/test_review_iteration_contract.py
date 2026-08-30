from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
VIEW = (ROOT / "scripts/weekly_report/review/review-view.js").read_text()
BACKEND = (ROOT / "scripts/weekly_report/notes/review_apps_script.js").read_text()
CLIENT = (ROOT / "scripts/weekly_report/notes/review_client.js").read_text()


class ReviewIterationContract(unittest.TestCase):
    def test_role_note_schema_is_additive_and_legacy_bgm_is_default(self):
        for field in ("performance_note", "performance_author", "performance_updated_at", "bdm_note", "bdm_author", "bdm_updated_at"):
            self.assertIn(field, BACKEND)
        self.assertIn('p.note_type||"bgm"', BACKEND)
        self.assertIn('["bgm","performance","bdm"]', BACKEND)

    def test_slack_does_not_mutate_role_notes(self):
        fn = BACKEND.split("function reviewWeeklySlackPost(p){", 1)[1].split("function reviewJson", 1)[0]
        self.assertIn("discussion_text", fn)
        self.assertNotIn("next.bgm_note=", fn)
        self.assertNotIn("next.performance_note=", fn)
        self.assertNotIn("next.bdm_note=", fn)

    def test_search_is_local_accessible_and_preserves_selection(self):
        self.assertIn('id="rv-search-ce"', VIEW)
        self.assertIn('aria-label="Clear CE search"', VIEW)
        search = VIEW.split('var search=root.querySelector("#rv-search-ce")', 1)[1].split('bind("#rv-clear-search"', 1)[0]
        self.assertNotIn("api.", search)
        self.assertNotIn("S.selected =", search)
        self.assertIn("clear.hidden=", search)

    def test_create_action_is_optimistic_deduplicated_and_rolls_back(self):
        save = VIEW.split("function saveCompose()", 1)[1].split("function toggleWork", 1)[0]
        for fragment in ("S.asyncBusy.createWork", "_pending:true", "render();toast", "rolled back", "performance.now()"):
            self.assertIn(fragment, save)

    def test_role_drafts_are_ce_and_role_scoped(self):
        self.assertIn('return String(S.selected)+":"+role', VIEW)
        self.assertIn("roleDrafts", VIEW)
        self.assertIn("slackDrafts", VIEW)

    def test_manual_work_and_thread_choice_drafts_survive_ce_switches(self):
        for fragment in (
            "composeDrafts",
            "composeByCe",
            "composeDraftKey(S.selected,S.compose)",
            "captureVisibleDrafts();",
            'S.compose = S.composeByCe[S.selected]||""',
            "newThreadReasonDrafts",
            "threadOperationByCe",
        ):
            self.assertIn(fragment, VIEW)
        compose = VIEW.split("function renderCompose(kind)", 1)[1].split(
            "function renderMemoryRail", 1
        )[0]
        self.assertIn("draft.text", compose)
        self.assertIn("draft.owner", compose)
        self.assertIn("draft.due", compose)
        self.assertIn("draft.status", compose)

    def test_non_bgm_role_notes_are_read_only_compatibility_memory(self):
        role = VIEW.split("function renderRoleNote(weekly,role)", 1)[1].split(
            "function renderWeeklySummary", 1
        )[0]
        self.assertIn('role!=="bgm"&&!saved)return ""', role)
        self.assertIn('role!=="bgm"&&saved', role)
        self.assertIn("Historical · read-only", role)
        self.assertNotIn('data-role-open="performance"', role)
        self.assertNotIn('data-role-open="bdm"', role)
        self.assertIn('data-role-open="bgm"', role)

    def test_client_keeps_legacy_note_compatibility(self):
        self.assertIn('note.note_type || "bgm"', CLIENT)
        self.assertIn('note.bgm_note || note.performance_note || note.bdm_note', CLIENT)

    def test_slack_summary_is_visible_and_sync_releases_ui_immediately(self):
        for fragment in ("function renderWeeklySummary", 'group("Finding"', 'group("Decision"', 'group("Open question"', "rv-summary-bullets", "summary_updated_at", "summary_delayed"):
            self.assertIn(fragment, VIEW)
        sync = VIEW.split("function syncThread()", 1)[1].split("function addGranola()", 1)[0]
        self.assertLess(sync.index("render();"), sync.index("Promise.all([loadCe"))

    def test_current_thread_continue_opens_composer_instead_of_navigating(self):
        self.assertIn('id="rv-continue-slack"', VIEW)
        self.assertIn('S.threadOperation="continue"', VIEW)
        self.assertIn('S.threadOperationByCe[String(S.selected)]="continue"', VIEW)
        self.assertIn('S.mentionPreview=null;render()', VIEW)
        self.assertIn('S.threadOperation==="continue"?\'<button class="rv-btn small primary"', VIEW)
        self.assertIn('weekly.slack_post_ts && !S.threadOperation', VIEW)

    def test_approved_suggestion_moves_to_a_visible_destination(self):
        self.assertIn('S.workTab=destination==="check"?"later":"open"', VIEW)
        self.assertIn('Approved · moved to Later', VIEW)
        self.assertIn('Approved · moved to Open', VIEW)

    def test_memory_drawer_survives_ce_hydration_render(self):
        self.assertIn("memoryOpen: false", VIEW)
        self.assertIn("if (S.memoryOpen) setTimeout(openMemory, 0)", VIEW)
        self.assertIn("current&&S.memoryOpen", VIEW)


if __name__ == "__main__":
    unittest.main()
