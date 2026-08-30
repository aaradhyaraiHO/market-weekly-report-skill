import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = (ROOT / "scripts/weekly_report/notes/review_apps_script.js").read_text()
VIEW = (ROOT / "scripts/weekly_report/review/review-view.js").read_text()


class ReviewSummaryBindingContract(unittest.TestCase):
    def test_summary_has_its_own_exact_discussion_binding(self):
        for field in ('"summary_thread_binding_id"', '"summary_slack_discussion_number"'):
            self.assertIn(field, BACKEND)
        self.assertIn('summary belongs to a different Slack discussion', BACKEND)
        self.assertIn('rec.summary_thread_binding_id=String(state.thread_binding_id||"")', BACKEND)
        self.assertIn('rec.summary_slack_discussion_number=String(state.slack_discussion_number||"")', BACKEND)

    def test_new_parent_archives_approved_summary_then_clears_active_summary(self):
        self.assertIn('reviewArchiveApprovedSummary(current)', BACKEND)
        self.assertIn('event_type:"slack_summary"', BACKEND)
        self.assertIn('next.summary_thread_binding_id=""', BACKEND)
        self.assertIn('next.summary_slack_discussion_number=""', BACKEND)
        self.assertIn('next.summary_draft_json=""', BACKEND)

    def test_stale_or_unbound_summary_is_not_relabelled(self):
        self.assertIn('summaryBound=legacySingleDiscussion', VIEW)
        self.assertIn('Summary pending for ', VIEW)
        self.assertIn('This discussion has no summary yet. The previous discussion remains in CE Memory.', VIEW)
        self.assertIn("pending=summaryBound", VIEW)


if __name__ == "__main__":
    unittest.main()
