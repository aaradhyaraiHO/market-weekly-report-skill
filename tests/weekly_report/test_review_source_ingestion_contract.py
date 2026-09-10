from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NOTES = ROOT / "scripts" / "weekly_report" / "notes"


def load_ingest_module():
    spec = importlib.util.spec_from_file_location("review_source_ingest", NOTES / "ingest_review_sources.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReviewSourceIngestionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ingest = load_ingest_module()
        cls.apps_script = (NOTES / "review_apps_script.js").read_text()
        cls.adapter = (NOTES / "granola_review_adapter.js").read_text()
        cls.pull = (NOTES / "granola_pull_api.js").read_text()
        cls.extract = (NOTES / "review_extract_api.js").read_text()
        cls.link = (NOTES / "granola_link_api.js").read_text()

    def test_exact_granola_match_can_be_sent_to_review_only_ingestion(self):
        payload = self.ingest.build_payload(
            "granola", "north_america", "2026-08-10",
            [{"ce_id": "3111", "match_status": "exact", "source_ref": "granola:abc:one",
              "kind": "comment", "body": "Availability is healthy."}], "secret"
        )
        self.assertEqual(payload["action"], "review_source_ingest")
        self.assertEqual(payload["items"][0]["match_status"], "exact")

    def test_granola_candidate_cannot_skip_reconciliation(self):
        with self.assertRaisesRegex(ValueError, "match_status=exact"):
            self.ingest.build_payload(
                "granola", "north_america", "2026-08-10",
                [{"ce_id": "3111", "match_status": "ambiguous", "source_ref": "granola:abc",
                  "kind": "action", "body": "Check availability."}], "secret"
            )

    def test_unmatched_granola_source_is_allowed_only_as_inbox_evidence(self):
        payload = self.ingest.build_payload(
            "granola", "north_america", "2026-08-10",
            [{"match_status": "unmatched", "source_ref": "granola:abc:unprocessed",
              "kind": "comment", "body": "Raw meeting notes."}], "secret"
        )
        self.assertNotIn("ce_id", payload["items"][0])

    def test_apps_script_enforces_the_same_exact_match_boundary(self):
        self.assertIn('String(p.match_status)==="exact"', self.apps_script)
        self.assertIn('source_type must be slack or granola', self.apps_script)
        self.assertNotIn("action_upsert", self.adapter)
        self.assertNotIn("action_upsert", self.pull)
        self.assertNotIn("action_upsert", self.extract)

    def test_retries_use_stable_source_hashes_not_model_position_or_clock(self):
        for source in (self.adapter, self.pull, self.extract):
            self.assertIn('createHash("sha256")', source)
        self.assertNotIn("Date.now()", self.extract)

    def test_adapters_use_review_only_configuration(self):
        for source in (self.adapter, self.pull, self.extract, self.link):
            self.assertIn("REVIEW_MODE_APPS_SCRIPT_URL", source)
            self.assertIn("REVIEW_MODE_INGEST_SECRET", source)
            self.assertNotIn("NOTES_SCRIPT_URL", source)

    def test_pasted_granola_link_is_server_side_and_fails_closed(self):
        self.assertIn("function noteId(sourceUrl)", self.link)
        self.assertIn("GRANOLA_API_KEY", self.link)
        self.assertIn("authenticated BGM identity required", self.link)
        self.assertIn("match_status: \"exact\"", self.link)
        self.assertIn('match_status: "unmatched"', self.link)
        self.assertIn("importMeetingBatch", self.link)
        self.assertIn("queued_for_reconciliation", (NOTES.parent / "lib" / "review_meeting_import.mjs").read_text())
        self.assertIn('createHash("sha256")', self.link)
        native_api = (ROOT / "scripts" / "weekly_report" / "review-app" / "src" / "api.ts").read_text()
        native_view = (ROOT / "scripts" / "weekly_report" / "review-app" / "src" / "review.tsx").read_text()
        self.assertIn('fetch("/api/granola-link"', native_api)
        self.assertIn("api.ingestGranolaLink", native_view)


if __name__ == "__main__":
    unittest.main()
