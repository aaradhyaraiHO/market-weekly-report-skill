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
        for text in (
            "Save note",
            "Preview Slack post",
            "Post to Slack",
            "Summarize now",
            "Automatic sync every 5 minutes",
            "AI · Slack",
        ):
            self.assertIn(text, self.view)

    def test_actions_and_scheduled_checks_remain_editable(self):
        for text in (
            "＋ Add action",
            "＋ Schedule check",
            "Save changes",
            "Choose the next review date",
            "Work item deleted · audit retained",
        ):
            self.assertIn(text, self.view)

    def test_ce_memory_keeps_story_work_and_read_only_perf(self):
        for text in (
            'data-mem="story"',
            'data-mem="work"',
            'data-mem="perf"',
            "BGM note · original",
            "thread summary",
            "Read-only · Perf source",
            "Perf history source unavailable",
        ):
            self.assertIn(text, self.view)

    def test_slack_is_not_duplicated_in_the_footer(self):
        footer = self.view.split('<footer class="rv-footer">', 1)[1].split("</footer>", 1)[0]
        self.assertNotIn("Slack", footer)
        self.assertIn("Finish CE review", footer)


if __name__ == "__main__":
    unittest.main()
