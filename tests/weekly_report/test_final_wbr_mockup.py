from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
FINAL = ROOT / "docs" / "weekly-review" / "final-wbr-review-mode.html"
CANONICAL = ROOT / "docs" / "weekly-review" / "review-tab-redesign-mockup.html"
VIEW = ROOT / "scripts" / "weekly_report" / "review" / "review-view.js"


class FinalWbrMockupTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.final = FINAL.read_text()
        cls.canonical = CANONICAL.read_text()
        cls.view = VIEW.read_text()

    def test_shared_final_path_is_the_canonical_mockup(self):
        self.assertEqual(self.final, self.canonical)

    def test_v0_commentary_to_slack_flow_is_visible(self):
        for text in ('Save note','Reply in Slack','Summarize discussion','api.syncWeeklyDiscussion'):
            self.assertIn(text,self.view)


    def test_actions_and_scheduled_checks_remain_editable(self):
        for text in (
            "＋ Add action",
            "Open work across all weeks.",
            "Save changes",
            "Choose the next review date",
            "Work item deleted · audit retained",
        ):
            self.assertIn(text, self.view)

    def test_ce_memory_simplifies_sources_into_review_and_action_history(self):
        for text in ('ceMemoryWeeks','historical_comments','perf_history','Follow-through','Sources ·','Performance history source is unavailable'):
            self.assertIn(text,self.view)
        self.assertNotIn('function renderMemoryDrawer',self.view)


    def test_slack_is_not_duplicated_in_the_footer(self):
        self.assertNotIn('function renderFinishBar',self.view)
        main=self.view.split('function renderMain()',1)[1].split('function completionBlockers',1)[0]
        self.assertEqual(main.count('renderCommentaryCard(q)'),1)



if __name__ == "__main__":
    unittest.main()
