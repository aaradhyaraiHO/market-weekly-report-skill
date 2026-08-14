from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
ALERT_DIR = ROOT / "alert"
FIXTURE = Path(__file__).parent / "fixtures" / "snapshot_north_america_2026-08-02.json"
SCHEMA = Path(__file__).parent / "contracts" / "snapshot-v1-baseline.json"
CONSUMERS = Path(__file__).parent / "contracts" / "consumers-v1-baseline.json"
GOLDEN = Path(__file__).parent / "golden"

sys.path.insert(0, str(REPORT_DIR))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


render = _load("weekly_render_baseline", REPORT_DIR / "render.py")
weekly_alert = _load("weekly_alert_baseline", ALERT_DIR / "weekly_alert.py")
post_message = _load("post_message_baseline", ALERT_DIR / "post_message.py")
export_perf_sheet = _load("export_perf_sheet_baseline", REPORT_DIR / "export_perf_sheet.py")
publish_weekly = _load("publish_weekly_baseline", REPORT_DIR / "publish_weekly.py")


def _json(path: Path):
    return json.loads(path.read_text())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _json_sha(value) -> str:
    return _sha(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")))


def _alert_payload(market: dict) -> dict:
    slug = market["meta"]["market_slug"]
    ledger_slug = weekly_alert.LEDGER_SLUG.get(slug, slug.replace("_", "-"))
    report_url = f"https://market-notebook.vercel.app/weekly-report-{ledger_slug}"
    notable, rca_threads, rca_ids = weekly_alert.build_notable(market, report_url)
    return {
        "messages": [
            {
                "fallback": f"{market['meta']['market']} — Weekly Review",
                "blocks": weekly_alert.build_summary_blocks(market, report_url),
                "threads": [
                    {"fallback": "Losing Money", "blocks": weekly_alert.table_losing(market, report_url)},
                    {"fallback": "RPC Fluctuations Down", "blocks": weekly_alert.table_fluct(market, report_url, "down")},
                    {"fallback": "RPC Fluctuations Up", "blocks": weekly_alert.table_fluct(market, report_url, "up")},
                ],
            },
            {
                "fallback": f"Weekly Movers — {market['meta']['market']}",
                "blocks": notable,
                "threads": rca_threads,
            },
        ],
        "_rca": {
            "ce_ids": rca_ids,
            "week_start": market["meta"]["week_start"],
            "week_end": market["meta"]["week_end"],
        },
    }


def _assert_schema(test: unittest.TestCase, value, schema: dict, path: str = "snapshot"):
    expected = schema.get("type")
    types = {"object": dict, "array": list, "string": str}
    if expected in types:
        test.assertIsInstance(value, types[expected], path)
    if "const" in schema:
        test.assertEqual(value, schema["const"], path)
    if isinstance(value, dict):
        for key in schema.get("required", []):
            test.assertIn(key, value, f"{path}.{key}")
        for key, child in schema.get("properties", {}).items():
            if key in value:
                _assert_schema(test, value[key], child, f"{path}.{key}")
    if isinstance(value, list):
        if "minItems" in schema:
            test.assertGreaterEqual(len(value), schema["minItems"], path)
        if "maxItems" in schema:
            test.assertLessEqual(len(value), schema["maxItems"], path)
        for i, item in enumerate(value):
            _assert_schema(test, item, schema.get("items", {}), f"{path}[{i}]")


class WeeklyBaselineContracts(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.snapshot = _json(FIXTURE)
        cls.manifest = _json(GOLDEN / "manifest.json")
        cls.consumers = _json(CONSUMERS)

    def test_snapshot_matches_observed_v1_contract(self):
        _assert_schema(self, self.snapshot, _json(SCHEMA))
        self.assertEqual(self.snapshot["meta"]["weeks"], [w["week"] for w in self.snapshot["market_summary"]["weekly"]])
        for ce in self.snapshot["ces"]:
            self.assertEqual(len(ce["weekly"]), 12)

    def test_renderer_and_embedded_payload_match_golden(self):
        markets = render.load_markets([str(FIXTURE)])
        html = render.render(markets, render.TEMPLATE)
        self.assertEqual(_sha(html), self.manifest["report_html_sha256"])
        match = re.search(r'<script[^>]*id="report-data"[^>]*>(.*?)</script>', html, re.S)
        self.assertIsNotNone(match)
        embedded = json.loads(match.group(1))
        self.assertEqual(embedded["markets"], [self.snapshot])
        self.assertEqual(embedded["schema_version"], 1)
        self.assertEqual(sorted(embedded), self.consumers["renderer"]["payload_keys"])
        self.assertEqual(Path(render.out_path(markets)).name, self.consumers["renderer"]["single_report_name"])
        self.assertIn(f"<title>{self.consumers['renderer']['title']}</title>", html)

    def test_slack_payload_and_blockkit_normalization_match_golden(self):
        payload = _alert_payload(copy.deepcopy(self.snapshot))
        self.assertEqual(_json_sha(payload), self.manifest["slack_payload_sha256"])
        self.assertIn(self.consumers["slack"]["report_url"], json.dumps(payload))
        self.assertEqual(len(payload["messages"]), self.consumers["slack"]["message_count"])
        self.assertEqual(
            [thread["fallback"] for thread in payload["messages"][0]["threads"]],
            self.consumers["slack"]["summary_thread_fallbacks"],
        )
        self.assertEqual(payload["_rca"]["ce_ids"], self.consumers["slack"]["rca_ce_ids"])
        expanded = []
        for message in post_message.normalize_to_messages(copy.deepcopy(payload), None):
            expanded.append({
                "fallback": message["fallback"],
                "blocks": post_message.expand_blocks(message["blocks"]),
                "threads": message.get("threads", []),
            })
        normalized = json.dumps(expanded, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        self.assertEqual(_sha(normalized), self.manifest["slack_normalized_sha256"])

    def test_sheet_rows_and_column_contract_match_golden(self):
        rows = export_perf_sheet.rows_for_snapshot(
            copy.deepcopy(self.snapshot),
            {"101": {"status": "pause_review", "note": "Check tracking before changing bids"}},
            {"101": "Attractions"},
        )
        actual = {"header": export_perf_sheet.HEADER, "rows": rows}
        self.assertEqual(_json_sha(actual), self.manifest["sheet_rows_sha256"])
        self.assertEqual(export_perf_sheet.HEADER, self.consumers["sheet"]["header"])
        self.assertEqual(len(export_perf_sheet.HEADER), self.consumers["sheet"]["column_count"])
        self.assertTrue(all(len(row) == len(export_perf_sheet.HEADER) for row in rows))

    def test_ledger_series_urls_and_matrix_match_golden(self):
        series = publish_weekly.weekly_series(self.snapshot, 6)
        ledger_slug, name, flag, region = publish_weekly.MARKET_META["north_america"]
        entry = {
            "slug": ledger_slug, "name": name, "flag": flag, "region": region,
            "report_path": f"weekly-report-{ledger_slug}.html", "series": series,
            "spark": publish_weekly._sparkline([row["rev"] for row in series]),
        }
        cols = [row["week"] for row in series]
        with tempfile.TemporaryDirectory(prefix="weekly-baseline-") as tmp:
            matrix = publish_weekly.render_matrix({"markets": [entry]}, "2026-08-02", cols, Path(tmp))
        actual = {"entry": entry, "columns": cols, "matrix_sha256": _sha(matrix)}
        self.assertEqual(_json_sha(actual), self.manifest["ledger_output_sha256"])
        self.assertEqual(entry["report_path"], "weekly-report-north-america.html")
        self.assertEqual(entry["report_path"], self.consumers["ledger"]["current_report_path"])
        self.assertEqual(
            f"weekly-report-{ledger_slug}-{self.snapshot['meta']['week_start']}.html",
            self.consumers["ledger"]["archive_report_path"],
        )
        self.assertEqual(len(cols), self.consumers["ledger"]["series_columns"])
        self.assertEqual(
            weekly_alert.LEDGER_SLUG["north_america"],
            publish_weekly.MARKET_META["north_america"][0],
        )

    def test_fixture_bucket_membership_is_frozen(self):
        buckets = self.snapshot["buckets_final"]
        actual = {
            "losing_money_existing": [str(row["ce_id"]) for row in buckets["defend"]["losing_money"]["existing"]],
            "losing_money_new": [str(row["ce_id"]) for row in buckets["defend"]["losing_money"]["new"]],
            "fluctuations_down": [str(row["ce_id"]) for row in buckets["defend"]["seasonality_down"]],
            "fluctuations_up": [str(row["ce_id"]) for row in buckets["compound"]["seasonality_up"]],
        }
        self.assertEqual(actual, self.consumers["fixture_bucket_membership"])

    def test_no_write_end_to_end_path(self):
        with tempfile.TemporaryDirectory(prefix="weekly-baseline-") as tmp:
            report_path = Path(tmp) / "report.html"
            report_path.write_text(render.render(render.load_markets([str(FIXTURE)]), render.TEMPLATE))
            market = weekly_alert.load_market(report_path, "north_america", 0)
            payload = _alert_payload(market)
            post_message.validate_payload(payload)
            rows = export_perf_sheet.rows_for_snapshot(market, {}, {})
            self.assertEqual(len(payload["messages"]), 2)
            self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
