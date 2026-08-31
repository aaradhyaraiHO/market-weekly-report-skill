from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = (ROOT / "scripts/weekly_report/notes/review_apps_script.js").read_text()
CLIENT = (ROOT / "scripts/weekly_report/notes/review_client.js").read_text()
PROXY = (ROOT / "scripts/weekly_report/notes/review_proxy_api.js").read_text()
VIEW = (ROOT / "scripts/weekly_report/review/review-view.js").read_text()


class ReviewP0CoreContract(unittest.TestCase):
    def test_thread_discovery_is_authoritative_and_stable_id_scoped(self):
        endpoint = BACKEND.split('if (action === "review_thread_list")', 1)[1].split("\n", 1)[0]
        self.assertIn("reviewThreadFor(p.market_slug,p.ce_id)", endpoint)
        self.assertIn("reviewThreadsFor(p.market_slug,p.ce_id)", endpoint)
        self.assertIn('threads: function(identity, options)', CLIENT)
        self.assertIn('"review_thread_list"', PROXY)
        self.assertIn("api.threads({ market_slug:S.market_slug,ce_id:ceId }", VIEW)

    def test_all_three_slack_states_are_explicit(self):
        card = VIEW.split("function renderCommentaryCard(q)", 1)[1].split(
            "function normalizedSuggestionBody", 1
        )[0]
        for text in (
            "Start Slack discussion",
            "Continue Slack discussion #",
            "Start a new discussion",
            "Use the durable CE thread",
        ):
            self.assertIn(text, card)
        self.assertIn('S.threadOperation==="new_parent"', card)
        self.assertIn("Why start a new discussion?", card)
        for text in (
            "threadRegistryLoaded", "Checking the existing CE thread",
            "Could not check the existing CE thread", 'id="rv-retry-threads"',
        ):
            self.assertIn(text, VIEW)

    def test_summary_requires_bgm_approval_before_timeline_or_memory(self):
        sync = BACKEND.split("function reviewWeeklySyncCore(p)", 1)[1].split(
            "function reviewWeeklySync(p)", 1
        )[0]
        self.assertIn('rec.summary_status="pending"', sync)
        self.assertIn("summary_draft_json", sync)
        timeline = BACKEND.split("function reviewTimeline(p)", 1)[1].split(
            "function reviewBacklog(p)", 1
        )[0]
        self.assertIn('String(r.summary_status)==="approved"', timeline)
        memory = VIEW.split("function renderMemory(res)", 1)[1].split(
            "function wireMemory", 1
        )[0]
        self.assertIn('String(w.summary_status||"")==="approved"', memory)
        for action in ("Approve summary", "Dismiss", "Regenerate"):
            self.assertIn(action, VIEW)

    def test_reconciliation_is_read_only_and_does_not_infer_attribution(self):
        block = BACKEND.split("function reviewReconciliation(p)", 1)[1].split(
            "function reviewWorkDelete", 1
        )[0]
        for view in (
            "completed_since_prior",
            "open",
            "blocked_overdue",
            "carried_forward",
            "evidence_suggesting_completion",
            "revisit_required",
        ):
            self.assertIn(view, block)
        self.assertIn('status:"unavailable"', block)
        self.assertNotIn("reviewWrite(", block)
        self.assertIn('"review_reconciliation"', PROXY)
        self.assertIn("Monday reconciliation", VIEW)

    def test_follow_through_separates_attention_from_committed_work(self):
        actions = VIEW.split("function renderActionsCard(q)", 1)[1].split(
            "function workRow(w)", 1
        )[0]
        for label in ("Needs review", "Open", "Later", "Completed"):
            self.assertIn(label, actions)
        self.assertIn("rv-focus-summary", actions)
        self.assertIn("pending.slice(0,3)", actions)
        self.assertIn("See ", actions)
        self.assertIn("S.expandedSuggestion", actions)
        self.assertIn('s.kind === "comment" || !s.kind', actions)
        self.assertIn("Approve observation", actions)
        self.assertIn("suggested from", actions)
        self.assertIn("rv-suggestion-text", actions)
        self.assertIn("rv-inline-actions", actions)
        self.assertIn('isComment?"comment":s.kind', actions)
        self.assertNotIn("rv-check", actions)
        committed = VIEW.split("function workRow(w)", 1)[1].split(
            "function renderWorkEdit", 1
        )[0]
        self.assertIn("rv-check", committed)
        self.assertIn("rv-trace", VIEW)

    def test_completion_counts_the_same_deduplicated_suggestions_the_inbox_shows(self):
        blockers = VIEW.split("function completionBlockers(q)", 1)[1].split(
            "function renderFinishBar", 1
        )[0]
        self.assertIn("dedupeSuggestions", blockers)
        self.assertIn('s.kind==="comment"', blockers)


if __name__ == "__main__":
    unittest.main()
