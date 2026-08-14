from __future__ import annotations

import io
import json
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
sys.path.insert(0, str(REPORT_DIR))

import snapshot_finalize  # noqa: E402


class SnapshotFinalizeContract(unittest.TestCase):
    def test_common_finalization_preserves_order_values_and_logging(self):
        calls = []

        def build_buckets(snapshot):
            calls.append("buckets")
            self.assertNotIn("buckets_final", snapshot)
            return {"sentinel": "final buckets"}

        def build_pp(snapshot):
            calls.append("prepurchase")
            self.assertEqual(snapshot["buckets_final"], {"sentinel": "final buckets"})
            return [{"sentinel": "prepurchase"}]

        def attach(snapshot):
            calls.append("seasonality")
            snapshot["seasonality_attached"] = True
            return 3

        modules = {
            "buckets": types.SimpleNamespace(build_buckets=build_buckets),
            "pp": types.SimpleNamespace(build_pp=build_pp),
            "seasonality_llm": types.SimpleNamespace(attach=attach),
        }
        snapshot = {"meta": {"market_slug": "synthetic"}}
        output = io.StringIO()
        with patch.dict(sys.modules, modules), redirect_stdout(output):
            result = snapshot_finalize.finalize_common(snapshot)

        self.assertIs(result, snapshot)
        self.assertEqual(calls, ["buckets", "prepurchase", "seasonality"])
        self.assertEqual(snapshot["buckets_final"], {"sentinel": "final buckets"})
        self.assertEqual(snapshot["prepurchase"], [{"sentinel": "prepurchase"}])
        self.assertTrue(snapshot["seasonality_attached"])
        self.assertEqual(output.getvalue(), "  seasonality tags attached: 3\n")

    def test_common_finalization_preserves_fail_soft_defaults_and_logging(self):
        modules = {
            "buckets": types.SimpleNamespace(build_buckets=lambda snapshot: {"sentinel": "final buckets"}),
            "pp": types.SimpleNamespace(build_pp=lambda snapshot: (_ for _ in ()).throw(RuntimeError("pp failed"))),
            "seasonality_llm": types.SimpleNamespace(
                attach=lambda snapshot: (_ for _ in ()).throw(ValueError("tagging failed"))
            ),
        }
        snapshot = {}
        output = io.StringIO()
        with patch.dict(sys.modules, modules), redirect_stdout(output):
            snapshot_finalize.finalize_common(snapshot)

        self.assertEqual(snapshot["buckets_final"], {"sentinel": "final buckets"})
        self.assertEqual(snapshot["prepurchase"], [])
        self.assertEqual(
            output.getvalue(),
            "  [pp] skipped: pp failed\n"
            "  seasonality_llm.attach skipped (ValueError('tagging failed'))\n",
        )

    def test_review_context_loader_preserves_market_and_global_messages(self):
        with tempfile.TemporaryDirectory(prefix="weekly-finalize-") as tmp:
            path = Path(tmp) / "slack_context_synthetic_2026-08-02.json"
            cards = [{"title": "Synthetic", "body": "No external content"}]
            path.write_text(json.dumps(cards))

            market_snapshot = {"market_review_context": []}
            market_output = io.StringIO()
            with redirect_stdout(market_output):
                snapshot_finalize.load_review_context(
                    market_snapshot,
                    path,
                    success_suffix=f" from {path.name}",
                )
            self.assertEqual(market_snapshot["market_review_context"], cards)
            self.assertEqual(
                market_output.getvalue(),
                f"  [slack] loaded 1 context cards from {path.name}\n",
            )

            global_snapshot = {"market_review_context": []}
            global_output = io.StringIO()
            with redirect_stdout(global_output):
                snapshot_finalize.load_review_context(global_snapshot, path)
            self.assertEqual(global_snapshot["market_review_context"], cards)
            self.assertEqual(global_output.getvalue(), "  [slack] loaded 1 context cards\n")

    def test_review_context_loader_preserves_missing_and_malformed_behavior(self):
        with tempfile.TemporaryDirectory(prefix="weekly-finalize-") as tmp:
            missing = Path(tmp) / "missing.json"
            snapshot = {"market_review_context": ["unchanged"]}
            output = io.StringIO()
            with redirect_stdout(output):
                snapshot_finalize.load_review_context(snapshot, missing)
            self.assertEqual(snapshot["market_review_context"], ["unchanged"])
            self.assertEqual(output.getvalue(), "")

            malformed = Path(tmp) / "malformed.json"
            malformed.write_text("not json")
            output = io.StringIO()
            with redirect_stdout(output):
                snapshot_finalize.load_review_context(snapshot, malformed)
            self.assertEqual(snapshot["market_review_context"], ["unchanged"])
            self.assertIn("  [slack] sidecar load skipped (JSONDecodeError(", output.getvalue())


if __name__ == "__main__":
    unittest.main()
