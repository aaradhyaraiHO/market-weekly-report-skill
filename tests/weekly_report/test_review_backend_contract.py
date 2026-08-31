from __future__ import annotations

import re
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "scripts" / "weekly_report" / "notes" / "review_apps_script.js"
LEGACY_BACKEND = ROOT / "scripts" / "weekly_report" / "notes" / "apps_script.js"
CLIENT = ROOT / "scripts" / "weekly_report" / "notes" / "review_client.js"
INGEST = ROOT / "scripts" / "weekly_report" / "notes" / "ingest_review_sources.py"
TEMPLATE = ROOT / "scripts" / "weekly_report" / "template" / "report_template.html"
RENDER = ROOT / "scripts" / "weekly_report" / "render.py"
PROXY = ROOT / "scripts" / "weekly_report" / "notes" / "review_proxy_api.js"
ACTIONS_PROXY = ROOT / "scripts" / "weekly_report" / "notes" / "actions_proxy_api.js"
GRANOLA_ADAPTER = ROOT / "scripts" / "weekly_report" / "notes" / "granola_review_adapter.js"
GRANOLA_PULL = ROOT / "scripts" / "weekly_report" / "notes" / "granola_pull_api.js"


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
        self.assertIn('post("review_work_upsert"', self.client)
        self.assertNotIn("openWorkLocalStorage", self.client)

    def test_slack_thread_identity_excludes_week(self):
        match = re.search(
            r"function reviewThreadsFor\(market, ceId\) \{(?P<body>.*?)\n\}",
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
        self.assertIn('REVIEW_MODE_INGEST_SECRET', self.backend)
        self.assertIn('queued_for_reconciliation:true', self.backend)
        self.assertIn('decision must be approved or rejected', self.backend)
        self.assertIn('["comment","action","check"].indexOf(p.destination)', self.backend)
        for field in ("decision_destination", "accepted_body", "accepted_owner", "accepted_due_date"):
            self.assertIn(f'"{field}"', self.backend)
        self.assertIn('existing.status !== "pending"', self.backend)

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
            "granolaSuggestions",
            "attachGranolaMeeting",
            "ingestGranolaLink",
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
        self.assertNotIn('if(current && current.slack_post_ts && String(p.thread_operation||"")!=="new_parent")', self.backend)
        self.assertIn('String(current.last_post_request_id||"")===String(p.request_id)', self.backend)
        self.assertIn("payload.client_msg_id=String(p.request_id)", self.backend)
        self.assertIn('next.sync_status="post_failed"', self.backend)

    def test_ce_thread_lifecycle_is_additive_and_stable_id_scoped(self):
        for field in (
            "binding_id", "binding_status", "created_reason", "replaced_reason",
            "predecessor_binding_id", "successor_binding_id", "created_by",
            "weekly_starter_ts", "weekly_starter_week", "last_post_request_id",
        ):
            self.assertIn(f'"{field}"', self.backend)
        lifecycle = self.backend.split("function reviewSlackPostCore(p)", 1)[1].split(
            "function reviewSlackPost(p)", 1
        )[0]
        self.assertIn('operation="new_parent"', lifecycle)
        self.assertIn("replacement reason is required", lifecycle)
        self.assertIn('operation==="continue"', lifecycle)
        self.assertIn("predecessor_binding_id", lifecycle)
        self.assertIn("successor_binding_id", lifecycle)
        self.assertIn('reviewWrite("threads",null,record)', lifecycle)
        self.assertIn('existing.binding_status="replaced"', lifecycle)
        self.assertIn("existing.last_post_request_id", lifecycle)
        self.assertIn("if(existing&&!existing.binding_id)", lifecycle)
        self.assertIn("slack_threads:threads.slice(0,25)", self.backend)

    def test_legacy_outcomes_remain_readable_but_receipts_use_core_primitives(self):
        self.assertIn('sheet: "review_outcomes"', self.backend)
        for field in ("outcome_id", "outcome_type", "decision", "no_discussion", "approved_by", "approved_at"):
            self.assertIn(f'"{field}"', self.backend)
        receipt = self.backend.split("function reviewReceiptUpsert(p)", 1)[1].split(
            "function reviewSetUpsert", 1
        )[0]
        for message in (
            "review treatment is required",
            "Slack discussion or concise no-discussion reason is required",
            "pending suggestions must be triaged before completion",
            "unresolved work needs an owner/date or explicit carry-forward",
        ):
            self.assertIn(message, receipt)
        self.assertNotIn("approved CE outcome is required", receipt)
        self.assertNotIn('reviewFind("outcomes"', receipt)
        self.assertIn("no_discussion_reason", receipt)
        self.assertIn('"review_outcome_list"', self.client)
        self.assertIn('post("review_outcome_upsert"', self.client)
        self.assertIn("ymd(r.week_start)===ymd(p.week_start)", receipt)

    def test_work_contract_adds_carry_forward_and_measured_outcome_fields(self):
        for field in (
            "next_review_date", "latest_update", "expected_effect", "completion_evidence",
            "measured_outcome", "approval_state", "idempotency_key", "duplicate_of",
            "parent_work_id", "carry_forward", "archived_at",
        ):
            self.assertIn(f'"{field}"', self.backend)
        self.assertIn("p.carry_forward===undefined", self.backend)

    def test_timeline_projection_is_stable_ce_scoped_and_history_is_read_only(self):
        self.assertIn('sheet: "review_timeline_events"', self.backend)
        for field in (
            "event_id", "review_week", "event_type", "source_ref", "approval_state",
            "related_review_id", "related_work_id", "supersedes_event_id", "idempotency_key",
        ):
            self.assertIn(f'"{field}"', self.backend)
        timeline = self.backend.split("function reviewTimeline(p)", 1)[1].split(
            "function reviewBacklog", 1
        )[0]
        self.assertIn("ce=String(p.ce_id)", timeline)
        self.assertIn("candidate_created", timeline)
        self.assertIn("slack_discussion", timeline)
        self.assertIn("outcome_approved", timeline)
        self.assertIn("work_completed", timeline)
        self.assertIn("review_finished", timeline)
        self.assertIn("read_only:true", timeline)
        self.assertIn("performance_history", self.backend)
        self.assertIn("historical_comment", self.backend)

    def test_unified_backlog_views_do_not_infer_stale_threshold(self):
        backlog = self.backend.split("function reviewBacklog(p)", 1)[1].split(
            "function reviewWorkDelete", 1
        )[0]
        for view in (
            "needs_approval", "open", "mine", "blocked_overdue", "stale",
            "recently_completed", "archived",
        ):
            self.assertIn(view, backlog)
        self.assertIn('r.status==="stale"', backlog)
        self.assertNotIn("staleDays", backlog)
        self.assertIn('"review_backlog"', self.client)

    def test_nomination_and_metric_events_are_idempotent_human_approved_only(self):
        event = self.backend.split("function reviewTimelineEventUpsert(p)", 1)[1].split(
            "function reviewTimeline(p)", 1
        )[0]
        self.assertIn('"nomination","metric_outcome","completion_evidence"', event)
        self.assertIn("idempotency_key", event)
        self.assertIn('approval_state:"approved"', event)
        self.assertNotIn("reviewSlackPost", event)

    def test_guarded_source_provenance_and_idempotency_are_additive(self):
        for field in ("provider_meeting_id", "access_scope", "content_hash", "idempotency_key"):
            self.assertIn(f'"{field}"', self.backend)
        suggestion = self.backend.split("function reviewSuggestionRecord(p)", 1)[1].split(
            "function reviewSourceIngestRecord", 1
        )[0]
        self.assertIn("stableKey", suggestion)
        self.assertIn("String(r.ce_id)===String(p.ce_id)", suggestion)
        self.assertIn('String(p.match_status)==="exact"', self.backend)
        granola = self.backend.split("function reviewGranolaLinkSubmit(p)", 1)[1].split(
            "function reviewSuggestionDecide", 1
        )[0]
        self.assertNotIn("reviewSlackPost", granola)

    def test_pilot_telemetry_is_idempotent_and_review_scoped(self):
        self.assertIn('sheet: "review_pilot_telemetry"', self.backend)
        telemetry = self.backend.split("function reviewTelemetryRecord(p)", 1)[1].split(
            "function reviewTimeline(p)", 1
        )[0]
        self.assertIn("idempotency_key", telemetry)
        self.assertIn("reviewTrustedAuthor", telemetry)
        self.assertIn('post("review_telemetry_record"', self.client)

    def test_weekly_slack_sync_aggregates_and_fails_closed(self):
        self.assertIn('mode:"weekly_thread_summary"', self.backend)
        self.assertIn('rec.sync_status="summary_delayed"', self.backend)
        self.assertIn('rec.sync_status="summary_pending_approval"', self.backend)
        self.assertIn('rec.summary_status="pending"', self.backend)
        self.assertIn('function reviewSummaryDecide(p)', self.backend)
        self.assertIn("reviewSyncActiveThreads", self.backend)
        self.assertIn("everyMinutes(5)", self.backend)
        self.assertIn("reviewSyncSlackPeople", self.backend)
        self.assertIn("ambiguous Slack mentions", self.backend)
        self.assertIn('getProperty("REVIEW_MODE_AI_WEBHOOK_SECRET")', self.backend)
        self.assertIn('"X-Review-Secret":secret', self.backend)
        self.assertIn("function installReviewStorage()", self.backend)
        summary_api = (ROOT / "scripts" / "weekly_report" / "notes" / "review_summary_api.js").read_text()
        self.assertIn("process.env.ANTHROPIC_API_KEY", summary_api)
        self.assertIn("https://api.anthropic.com/v1/messages", summary_api)
        self.assertIn("REVIEW_MODE_AI_WEBHOOK_SECRET", summary_api)
        self.assertIn('tool_choice: { type: "tool", name: "emit_result"', summary_api)
        self.assertNotIn("strict: true", summary_api)
        self.assertIn("var nextCycle=reviewRows(\"weekly\")", self.backend)
        self.assertIn("slackThreadReplies(token,channel,threadTs,oldest,latest)", self.backend)

    def test_slack_directory_refresh_preserves_curated_aliases(self):
        self.assertIn('existing[String(r.market_slug)+"|"+String(r.slack_user_id)]=r', self.backend)
        self.assertIn('reviewAliasJoin([prior.aliases,', self.backend)
        self.assertIn('existing[market+"|"+id]', self.backend)


    def test_bgm_access_gate_is_server_side_and_opt_in_for_deployment(self):
        self.assertIn("Session.getActiveUser().getEmail()", self.backend)
        self.assertIn('getProperty("REVIEW_ENFORCE_ACCESS")', self.backend)
        self.assertIn('sheet: "bgm_access"', self.backend)
        self.assertIn("BGM is not allowed to change this market", self.backend)
        self.assertIn("reviewMutationGate(action,payload)", self.backend)
        self.assertIn("function reviewTrustedAuthor(p,fallback)", self.backend)
        self.assertIn("next.bgm_author=trustedAuthor", self.backend)

    def test_diagnostic_actions_keep_v1_authenticated_writer_contract(self):
        legacy = LEGACY_BACKEND.read_text()
        self.assertIn('var mutations = ["upsert", "delete", "post", "action_delete", "action_upsert"]', legacy)
        self.assertIn("authenticated BGM identity required", legacy)
        self.assertIn("reviewActorEmail(p), aNow", legacy)
        self.assertNotIn('p.owner || "", aNow', legacy)

    def test_signed_same_origin_proxy_supplies_verified_bgm_identity(self):
        proxy = PROXY.read_text()
        review_view = (ROOT / "scripts" / "weekly_report" / "review" / "review-view.js").read_text()
        self.assertIn('jwtVerify(token', proxy)
        self.assertIn('createHmac("sha256"', proxy)
        self.assertIn('params.set("actor_email", actor.email)', proxy)
        self.assertIn('params.set("actor_sig", signature)', proxy)
        self.assertIn('action") === "whoami"', proxy)
        self.assertIn("function reviewSignedActorEmail(p)", self.backend)
        self.assertIn("computeHmacSha256Signature(reviewActorCanonicalParams(p), secret)", self.backend)
        self.assertIn("if (!email) email = reviewSignedActorEmail(p);", self.backend)
        self.assertIn('global.createWeeklyReviewApi("/api/review")', review_view)

    def test_diagnostic_actions_use_actions_proxy_not_review_proxy(self):
        template = TEMPLATE.read_text()
        actions_proxy = ACTIONS_PROXY.read_text()
        self.assertIn("const ACTIONS_URL = DATA.actions_url || '/api/actions';", template)
        self.assertIn("fetch(ACTIONS_URL+'?'+params.toString()", template)
        self.assertIn("fetch(ACTIONS_URL+'?action=action_list", template)
        self.assertNotRegex(template, r"NOTES_URL\+'\?action=action_list")
        self.assertNotRegex(template, r"NOTES_URL\+'\?'+params\.toString\(\).*action_upsert")
        self.assertIn('const ALLOWED_ACTIONS = new Set(["action_list", "action_upsert", "action_delete"])', actions_proxy)
        self.assertIn('process.env.ACTIONS_PROXY_SECRET', actions_proxy)
        self.assertNotIn("REVIEW_MODE_APPS_SCRIPT_URL", actions_proxy)

    def test_complete_site_injector_embeds_review_client_and_commentary_ui(self):
        injector = (ROOT / "scripts" / "weekly_report" / "inject_review_view.py").read_text()
        review_view = (ROOT / "scripts" / "weekly_report" / "review" / "review-view.js").read_text()
        self.assertIn('client_path = HERE / "notes" / "review_client.js"', injector)
        self.assertIn('data-report-view="review"', injector)
        self.assertIn('id="review-view"', injector)
        self.assertIn("BGM note saved", review_view)
        self.assertIn("Thread summary", review_view)
        self.assertIn("startSlackDiscussion", review_view)
        self.assertIn("Granola meeting", review_view)
        self.assertIn("Add to commentary", review_view)
        self.assertIn("Schedule check", review_view)
        self.assertIn("attachGranolaMeeting", CLIENT.read_text())

    def test_manual_granola_link_is_a_source_inbox_fallback(self):
        self.assertIn("function reviewGranolaLinkSubmit(p)", self.backend)
        self.assertIn('match_status:"awaiting_import"', self.backend)
        self.assertIn('match_confidence:"bgm_attached"', self.backend)
        self.assertIn('action === "review_granola_link_submit"', self.backend)
        self.assertIn("candidate_ce_id", self.backend)
        self.assertIn('return post("review_granola_link_submit", link)', self.client)
        proxy = PROXY.read_text()
        self.assertIn('["GET", "POST"].includes(req.method)', proxy)
        self.assertIn('body: JSON.stringify(Object.fromEntries(params.entries()))', proxy)

    def test_granola_adapter_is_server_side_and_fails_closed(self):
        adapter = GRANOLA_ADAPTER.read_text()
        middleware = (ROOT / "scripts" / "weekly_report" / "notes" / "review_summary_middleware.js").read_text()
        self.assertIn('process.env.GRANOLA_WEBHOOK_SECRET', adapter)
        self.assertIn('process.env.REVIEW_MODE_INGEST_SECRET', adapter)
        self.assertIn('match_status === "exact"', adapter)
        self.assertIn('match_status: "unmatched"', adapter)
        self.assertIn('proposed_owner: ""', adapter)
        self.assertIn("api/granola-review", middleware)

    def test_granola_rest_pull_is_server_side_and_fails_closed(self):
        pull = GRANOLA_PULL.read_text()
        middleware = (ROOT / "scripts" / "weekly_report" / "notes" / "review_summary_middleware.js").read_text()
        self.assertIn('process.env.GRANOLA_API_KEY', pull)
        self.assertIn('https://public-api.granola.ai/v1/notes', pull)
        self.assertIn('process.env.REVIEW_MODE_AI_WEBHOOK_SECRET', pull)
        self.assertIn('process.env.REVIEW_MODE_INGEST_SECRET', pull)
        self.assertIn('match_status: "unmatched"', pull)
        self.assertIn('match_status: "exact"', pull)
        self.assertIn('proposed_owner: ""', pull)
        self.assertIn("api/granola-pull", middleware)

    def test_legacy_note_and_bucket_action_routes_remain(self):
        legacy = LEGACY_BACKEND.read_text()
        for route in ('action === "list"', 'action === "upsert"', 'action === "post"',
                      'action === "action_list"', 'action === "action_upsert"'):
            self.assertIn(route, legacy)

    def test_server_side_ingest_payload_keeps_exact_and_unmatched_items(self):
        ingest = load_ingest()
        items = [
            {"source_ref": "meeting:1:line:4", "kind": "comment", "body": "Exact", "ce_id": "3111",
             "match_status": "exact"},
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
