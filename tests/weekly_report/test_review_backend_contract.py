from __future__ import annotations

import re
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "scripts" / "weekly_report" / "notes" / "apps_script.js"
CLIENT = ROOT / "scripts" / "weekly_report" / "notes" / "review_client.js"
INGEST = ROOT / "scripts" / "weekly_report" / "notes" / "ingest_review_sources.py"
TEMPLATE = ROOT / "scripts" / "weekly_report" / "template" / "report_template.html"
RENDER = ROOT / "scripts" / "weekly_report" / "render.py"


def load_ingest():
    spec = importlib.util.spec_from_file_location("review_source_ingest", INGEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReviewBackendContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = BACKEND.read_text()
        cls.client = CLIENT.read_text()

    def test_additive_tables_cover_review_cycle(self):
        for sheet in (
            "review_comments",
            "review_work_items",
            "review_receipts",
            "review_set",
            "ce_threads",
            "review_weekly_commentary",
            "review_source_suggestions",
            "review_source_inbox",
            "bgm_access",
            "review_slack_people",
        ):
            self.assertIn(f'sheet: "{sheet}"', self.backend)

    def test_attribution_and_tombstone_fields_are_durable(self):
        for field in (
            "comment_id",
            "author_name",
            "author_role",
            "source_type",
            "source_author",
            "source_ref",
            "source_url",
            "accepted_by",
            "deleted_at",
        ):
            self.assertIn(f'"{field}"', self.backend)
        self.assertIn("clients render a tombstone", self.backend)

    def test_actions_and_checks_are_one_work_item_contract(self):
        self.assertIn('["action","check"]', self.backend)
        self.assertIn("Owner is deliberately never inferred", self.backend)
        self.assertIn('request("review_work_list"', self.client)
        self.assertIn('request("review_work_upsert"', self.client)
        self.assertNotIn("openWorkLocalStorage", self.client)

    def test_slack_thread_identity_excludes_week(self):
        match = re.search(
            r"function reviewThreadFor\(market, ceId\) \{(?P<body>.*?)\n\}",
            self.backend,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("r.market_slug === market", body)
        self.assertIn("r.ce_id", body)
        self.assertNotIn("week", body)
        self.assertIn("conversations.replies", self.backend)
        self.assertIn("slackUserName", self.backend)

    def test_source_ingestion_requires_ce_identity_and_human_approval(self):
        self.assertIn('["market_slug","week_start","source_type","source_ref","kind","body"]', self.backend)
        self.assertIn('status:"pending"', self.backend)
        self.assertIn('REVIEW_INGEST_SECRET', self.backend)
        self.assertIn('queued_for_reconciliation:true', self.backend)
        self.assertIn('decision must be approved or rejected', self.backend)
        self.assertIn('p.destination === "comment"', self.backend)
        self.assertIn('p.destination === "action"', self.backend)
        self.assertIn('p.destination === "check"', self.backend)

    def test_ai_fails_closed_and_perf_stays_snapshot_only(self):
        self.assertIn('status:"source_unavailable"', self.backend)
        self.assertIn(
            'perf_history_contract:"read ce.perf_action_hist from the report snapshot; no review-store write"',
            self.backend,
        )
        self.assertNotIn("perf_action_upsert", self.backend)

    def test_client_exposes_review_and_ce_drawer_shared_operations(self):
        for method in (
            "saveComment",
            "deleteComment",
            "saveWork",
            "finishReview",
            "saveReviewSetItem",
            "memory",
            "weeklyCommentary",
            "saveWeeklyNote",
            "deleteWeeklyNote",
            "resolveMentions",
            "startSlackDiscussion",
            "syncWeeklyDiscussion",
            "askInSlack",
            "scanSlack",
            "decideSuggestion",
            "sourceInbox",
            "reconcileSource",
        ):
            self.assertRegex(self.client, rf"\b{method}: function")

    def test_weekly_commentary_is_one_ce_week_record_with_idempotent_slack_start(self):
        for field in (
            "weekly_id",
            "bgm_note",
            "slack_post_ts",
            "summary_json",
            "summary_upto_ts",
            "last_post_request_id",
            "note_deleted_at",
        ):
            self.assertIn(f'"{field}"', self.backend)
        self.assertIn("function reviewWeeklyFor(market,ceId,week)", self.backend)
        self.assertIn("current.last_post_request_id===p.request_id", self.backend)
        self.assertIn("payload.client_msg_id=String(p.request_id)", self.backend)
        self.assertIn('next.sync_status="post_failed"', self.backend)

    def test_weekly_slack_sync_aggregates_and_fails_closed(self):
        self.assertIn('mode:"weekly_thread_summary"', self.backend)
        self.assertIn('rec.sync_status="summary_delayed"', self.backend)
        self.assertIn('rec.sync_status="summary_current"', self.backend)
        self.assertIn("reviewSyncActiveThreads", self.backend)
        self.assertIn("everyMinutes(5)", self.backend)
        self.assertIn("reviewSyncSlackPeople", self.backend)
        self.assertIn("ambiguous Slack mentions", self.backend)
        self.assertIn('getProperty("REVIEW_AI_WEBHOOK_SECRET")', self.backend)
        self.assertIn('"X-Review-Secret":secret', self.backend)
        self.assertIn("function installReviewStorage()", self.backend)
        summary_api = (ROOT / "scripts" / "weekly_report" / "notes" / "review_summary_api.js").read_text()
        self.assertIn("process.env.OPENAI_API_KEY", summary_api)
        self.assertIn("https://api.openai.com/v1/chat/completions", summary_api)
        self.assertIn("REVIEW_AI_WEBHOOK_SECRET_V2", summary_api)
        self.assertIn('response_format: { type: "json_object" }', summary_api)
        self.assertIn("var nextCycle=reviewRows(\"weekly\")", self.backend)
        self.assertIn("slackThreadReplies(token,channel,threadTs,oldest,latest)", self.backend)

    def test_slack_directory_refresh_preserves_curated_aliases(self):
        self.assertIn('existing[String(r.slack_user_id)]=r', self.backend)
        self.assertIn('prior.aliases||""', self.backend)
        self.assertIn('prior.market_slug||"*"', self.backend)

    def test_bgm_access_gate_is_server_side_and_opt_in_for_deployment(self):
        self.assertIn("Session.getActiveUser().getEmail()", self.backend)
        self.assertIn('getProperty("REVIEW_ENFORCE_ACCESS")', self.backend)
        self.assertIn('sheet: "bgm_access"', self.backend)
        self.assertIn("BGM is not allowed to change this market", self.backend)
        self.assertIn("reviewMutationGate(action,payload)", self.backend)
        self.assertIn("function reviewTrustedAuthor(p,fallback)", self.backend)
        self.assertIn("next.bgm_author=trustedAuthor", self.backend)

    def test_renderer_embeds_shared_review_client_and_commentary_ui(self):
        template = TEMPLATE.read_text()
        render = RENDER.read_text()
        self.assertIn("__REVIEW_CLIENT_JS__", template)
        self.assertIn('html.replace("__REVIEW_CLIENT_JS__", review_client)', render)
        self.assertIn("This week’s BGM note", template)
        self.assertIn("Thread summary", template)
        self.assertIn("startWeeklySlack", template)

    def test_legacy_note_and_bucket_action_routes_remain(self):
        for route in ('action === "list"', 'action === "upsert"', 'action === "post"',
                      'action === "action_list"', 'action === "action_upsert"'):
            self.assertIn(route, self.backend)

    def test_server_side_ingest_payload_keeps_exact_and_unmatched_items(self):
        ingest = load_ingest()
        items = [
            {"source_ref": "meeting:1:line:4", "kind": "comment", "body": "Exact", "ce_id": "3111"},
            {"source_ref": "meeting:1:line:8", "kind": "action", "body": "Needs matching",
             "match_status": "ambiguous"},
        ]
        payload = ingest.build_payload("granola", "north_america", "2026-08-09", items, "secret")
        self.assertEqual(payload["items"], items)
        self.assertEqual(payload["source_type"], "granola")
        with self.assertRaises(ValueError):
            ingest.build_payload("granola", "north_america", "2026-08-09", items, "")


if __name__ == "__main__":
    unittest.main()
