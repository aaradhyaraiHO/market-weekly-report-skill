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

    def test_create_action_is_optimistic_deduplicated_and_rolls_back(self):
        save = VIEW.split("function saveCompose()", 1)[1].split("function toggleWork", 1)[0]
        for fragment in ("S.asyncBusy.createWork", "_pending:true", "render();toast", "rolled back", "performance.now()"):
            self.assertIn(fragment, save)

    def test_role_drafts_are_ce_and_role_scoped(self):
        self.assertIn('return String(S.selected)+":"+role', VIEW)
        self.assertIn("roleDrafts", VIEW)
        self.assertIn("slackDrafts", VIEW)

    def test_client_keeps_legacy_note_compatibility(self):
        self.assertIn('note.note_type || "bgm"', CLIENT)
        self.assertIn('note.bgm_note || note.performance_note || note.bdm_note', CLIENT)


if __name__ == "__main__":
    unittest.main()
