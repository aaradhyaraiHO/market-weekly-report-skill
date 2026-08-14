from __future__ import annotations

import gzip
import json
import re
import tempfile
import unittest
from pathlib import Path

from test_baseline_contracts import (
    GOLDEN,
    SCHEMA,
    _alert_payload,
    _assert_schema,
    _json,
    _json_sha,
    _sha,
    export_perf_sheet,
    publish_weekly,
    render,
)

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures" / "captured"
SLUGS = ("sparse", "dense", "global")


def load_fixture(name: str) -> tuple[bytes, dict]:
    raw = gzip.decompress((FIXTURES / name).read_bytes())
    return raw, json.loads(raw)


def walk(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key, child
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class SanitizedSnapshotCharacterization(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.fixture_manifest = _json(FIXTURES / "fixture_manifest.json")
        cls.golden = _json(GOLDEN / "captured_manifest.json")
        cls.raw = {}
        cls.snapshots = {}
        for slug in SLUGS:
            name = f"snapshot_{slug}_2026-08-02.json.gz"
            raw, snapshot = load_fixture(name)
            cls.raw[slug] = raw
            cls.snapshots[slug] = snapshot

    def test_fixture_manifest_has_no_source_provenance(self):
        encoded = json.dumps(self.fixture_manifest).lower()
        for forbidden in ("sha256", "captured_from", "source_path", "/users/"):
            self.assertNotIn(forbidden, encoded)
        self.assertEqual(set(self.fixture_manifest["snapshots"]), {
            f"snapshot_{slug}_2026-08-02.json.gz" for slug in SLUGS
        })

    def test_sanitized_shapes_match_snapshot_contract(self):
        schema = _json(SCHEMA)
        for slug, snapshot in self.snapshots.items():
            _assert_schema(self, snapshot, schema, slug)
            self.assertEqual(snapshot["meta"]["market_slug"], slug)
            self.assertEqual(len(snapshot["ces"]), self.golden[slug]["ces"])
            bf = snapshot["buckets_final"]
            lm = bf["defend"]["losing_money"]
            actual = {
                "lm_existing": len(lm.get("existing") or []),
                "lm_new": len(lm.get("new") or []),
                "down": len(bf["defend"].get("seasonality_down") or []),
                "up": len(bf["compound"].get("seasonality_up") or []),
            }
            self.assertEqual(actual, self.golden[slug]["buckets"])
        global_snapshot = self.snapshots["global"]
        self.assertEqual(global_snapshot["meta"]["n_markets"], 3)
        self.assertEqual(global_snapshot["meta"]["ce_cap"]["total"], len(global_snapshot["ces"]))
        self.assertTrue(global_snapshot["meta"]["fluctuation_partial"])
        self.assertEqual(len(global_snapshot["market_breakdown"]), 3)

    def test_sanitized_identifiers_text_and_urls(self):
        email = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
        url = re.compile(r"https?://[^\s\"\\]+")
        narrative_keys = {
            "note", "notes", "action", "recommendation", "reason", "sub_reason",
            "gate_note", "signal", "status_now", "cause", "cause_tag", "verdict",
            "comment", "comments", "description", "message", "text",
        }
        for slug, snapshot in self.snapshots.items():
            text = self.raw[slug].decode()
            self.assertIsNone(email.search(text))
            self.assertNotIn("slack", text.lower())
            self.assertTrue(all(value.startswith("https://example.invalid/") for value in url.findall(text)))
            ids = [str(ce["ce_id"]) for ce in snapshot["ces"]]
            self.assertEqual(sorted(ids), [f"SCE-{index:04d}" for index in range(1, len(ids) + 1)])
            valid_ids = set(ids)
            for key, value in walk(snapshot):
                if key == "ce_id":
                    self.assertIn(str(value), valid_ids)
                if key in narrative_keys and isinstance(value, str):
                    self.assertIn(value, {"Synthetic fixture narrative.", "Synthetic fixture text."})

    def test_sanitized_single_market_and_global_renders_match_golden(self):
        for slug, snapshot in self.snapshots.items():
            html = render.render([snapshot], render.TEMPLATE)
            self.assertEqual(_sha(html), self.golden[slug]["render_sha256"])
            self.assertIn(f'"market_slug":"{slug}"', html)

    def test_sanitized_multi_market_render_order_and_output_match_golden(self):
        markets = [self.snapshots["sparse"], self.snapshots["dense"]]
        html = render.render(markets, render.TEMPLATE)
        self.assertEqual(_sha(html), self.golden["multi_sparse_dense"]["render_sha256"])
        self.assertLess(html.index('"market_slug":"sparse"'), html.index('"market_slug":"dense"'))
        self.assertEqual(Path(render.out_path(markets)).name, "report_multi_2026-08-02.html")

    def test_sanitized_slack_and_sheet_consumers_match_golden(self):
        for slug in ("sparse", "dense"):
            snapshot = self.snapshots[slug]
            payload = _alert_payload(snapshot)
            rows = export_perf_sheet.rows_for_snapshot(snapshot, {}, {})
            expected = self.golden[slug]
            self.assertEqual(_json_sha(payload), expected["alert_payload_sha256"])
            self.assertEqual(payload["_rca"]["ce_ids"], expected["alert_rca_ids"])
            self.assertEqual(_json_sha(rows), expected["sheet_rows_sha256"])
            self.assertEqual(len(rows), expected["sheet_rows"])

    def test_sanitized_ledger_series_and_global_hero_match_golden(self):
        for slug, snapshot in self.snapshots.items():
            series = publish_weekly.weekly_series(snapshot, 6)
            self.assertEqual(_json_sha(series), self.golden[slug]["ledger_series_sha256"])
        global_snapshot = self.snapshots["global"]
        series = publish_weekly.weekly_series(global_snapshot, 6)
        hero = {
            "report_path": "weekly-report-global.html",
            "series": series,
            "spark": publish_weekly._sparkline([row["rev"] for row in series]),
            "n_markets": global_snapshot["meta"]["n_markets"],
        }
        with tempfile.TemporaryDirectory(prefix="weekly-sanitized-") as tmp:
            matrix = publish_weekly.render_matrix(
                {"markets": [], "headout": hero}, "2026-08-02",
                [row["week"] for row in series], Path(tmp),
            )
        self.assertIn(">Headout</div>", matrix)
        self.assertIn("3 markets", matrix)


if __name__ == "__main__":
    unittest.main()
