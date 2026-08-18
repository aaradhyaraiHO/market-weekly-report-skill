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
GRANOLA_ADAPTER = NOTES / "granola_review_adapter.js"
REVIEW_VIEW = ROOT / "scripts" / "weekly_report" / "review" / "review-view.js"
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
        self.assertIn('var diagnosticMutations=["action_delete","action_upsert"]', self.combined)
        self.assertIn("authenticated Headout identity required", self.combined)
        self.assertIn("return reviewActorEmail(p) ? null", self.combined)
        self.assertIn("reviewActorEmail(p), aNow", self.combined)
        gate = self.combined.split("function reviewMutationGate(action,p){", 1)[1].split(
            "function reviewUpsertBy", 1
        )[0]
        review_mutations = gate.split("var mutations=", 1)[1]
        self.assertNotIn('"action_delete"', review_mutations)
        self.assertNotIn('"action_upsert"', review_mutations)

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
        self.assertIn('request("review_work_delete"', self.client)
        self.assertNotIn("action_delete", self.client)


class ReviewV0UiContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.view = REVIEW_VIEW.read_text()
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

    def test_note_and_slack_share_one_composer(self):
        self.assertEqual(self.view.count('id="rv-note"'), 1)
        for fragment in ('id="rv-save-note"', 'id="rv-start-slack"'):
            self.assert_ui_contract(fragment)
        save_note = self.view.split("function saveNote()", 1)[1].split("function deleteNote()", 1)[0]
        start_slack = self.view.split("function startSlack()", 1)[1].split("function syncThread()", 1)[0]
        self.assertIn('querySelector("#rv-note")', save_note)
        self.assertIn('querySelector("#rv-note")', start_slack)

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
        for fragment in ("CE Memory", "Perf", "Perf history source unavailable"):
            self.assert_ui_contract(fragment)
        memory = self.view.split("function renderMemory(res)", 1)[1].split(
            "function wireMemory", 1
        )[0]
        self.assertNotRegex(memory, r"savePerf|upsertPerf|deletePerf")


if __name__ == "__main__":
    unittest.main()
