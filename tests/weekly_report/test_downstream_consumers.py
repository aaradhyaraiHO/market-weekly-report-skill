from __future__ import annotations

import copy
import csv
import gzip
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_baseline_contracts import ALERT_DIR, REPORT_DIR, ROOT, _json_sha, _load, render

CAPTURED = Path(__file__).parent / "fixtures" / "captured"
COVERAGE_MATRIX = Path(__file__).parent / "COVERAGE_MATRIX.md"
BROWSER_CONTRACT = Path(__file__).parent / "browser_smoke_contract.json"
BROWSER_RESULT = Path(__file__).parent / "golden" / "browser_smoke_result.json"

run_weekly = _load("run_weekly_coverage", REPORT_DIR / "run_weekly.py")
export_flagged = _load("export_flagged_coverage", REPORT_DIR / "export_flagged.py")
export_full_lm = _load("export_full_lm_coverage", REPORT_DIR / "export_full_lm.py")
perf_history = _load("perf_history_coverage", REPORT_DIR / "perf_history.py")
publish_weekly = _load("publish_weekly_coverage", REPORT_DIR / "publish_weekly.py")
post_message = _load("post_message_coverage", ALERT_DIR / "post_message.py")
bucket_diff = _load("bucket_diff_coverage", ALERT_DIR / "bucket_diff.py")
thursday_ping = _load("thursday_ping_coverage", ALERT_DIR / "thursday_actions_ping.py")
update_posts = _load("update_posts_coverage", ALERT_DIR / "update_posts_weekly.py")


def captured(slug: str) -> dict:
    path = CAPTURED / f"snapshot_{slug}_2026-08-02.json.gz"
    return json.loads(gzip.decompress(path.read_bytes()))


def write_snapshot(directory: Path, slug: str) -> Path:
    path = directory / f"snapshot_{slug}_2026-08-02.json"
    path.write_text(json.dumps(captured(slug), separators=(",", ":")))
    return path


class DownstreamConsumerCoverage(unittest.TestCase):
    maxDiff = None

    def test_render_merges_sanitized_slack_and_perf_sidecars(self):
        with tempfile.TemporaryDirectory(prefix="weekly-sidecars-") as tmp:
            tmp = Path(tmp)
            snap_path = write_snapshot(tmp, "sparse")
            snapshot = json.loads(snap_path.read_text())
            first_id = str(snapshot["ces"][0]["ce_id"])
            context = [{"title": "Synthetic context", "body": "No network read"}]
            history = {first_id: [{"week": "2026-08-02", "action": "Hold", "comment": "Synthetic"}]}
            (tmp / "slack_context_sparse_2026-08-02.json").write_text(json.dumps(context))
            (tmp / "perf_hist_2026-08-02.json").write_text(json.dumps(history))
            market = render.load_markets([str(snap_path)])[0]
            self.assertEqual(market["market_review_context"], context)
            ce = next(row for row in market["ces"] if str(row["ce_id"]) == first_id)
            self.assertEqual(ce["perf_action_hist"], history[first_id])

    def test_run_weekly_report_and_publish_command_wiring(self):
        calls = []

        def record(cmd, cwd=None, check=True):
            calls.append(([str(part) for part in cmd], cwd, check))
            return 0

        with tempfile.TemporaryDirectory(prefix="weekly-run-") as tmp:
            missing = Path(tmp) / "missing.json"
            with patch.object(run_weekly, "run", side_effect=record), patch.object(
                run_weekly, "sidecar_path", return_value=missing
            ):
                run_weekly.stage_report(["gcc"], "2026-08-02")
                run_weekly.stage_publish(["gcc"], "2026-08-02")
        commands = [call[0] for call in calls]
        self.assertIn(
            ["python3", "weekly_market_report.py", "gcc", "--week", "2026-08-02", "--no-open"],
            commands,
        )
        self.assertIn(
            ["python3", "render.py", str(run_weekly.CACHE / "snapshot_gcc_2026-08-02.json"), "--no-open"],
            commands,
        )
        self.assertIn(
            ["python3", "publish_weekly.py", "gcc", "--week", "2026-08-02", "--renderer", "v1"],
            commands,
        )
        self.assertEqual(run_weekly.slugs_for("headout"), ["headout"])
        self.assertEqual(run_weekly._week_end("2026-08-02"), "2026-08-08")

    def test_run_weekly_alert_dry_run_command_wiring_without_external_calls(self):
        calls = []
        with tempfile.TemporaryDirectory(prefix="weekly-alert-stage-") as tmp:
            tmp = Path(tmp)
            cache, reports = tmp / "cache", tmp / "reports"
            cache.mkdir(); reports.mkdir()
            (reports / "report_gcc_2026-08-02.html").write_text("captured report placeholder")

            def record(cmd, cwd=None, check=True):
                command = [str(part) for part in cmd]
                calls.append((command, cwd, check))
                if "weekly_alert.py" in command:
                    out = Path(command[command.index("--out") + 1])
                    out.write_text(json.dumps({"_rca": {"ce_ids": ["6004"]}}))
                return 0

            with patch.object(run_weekly, "CACHE", cache), patch.object(
                run_weekly, "REPORTS", reports
            ), patch.object(run_weekly, "run", side_effect=record):
                run_weekly.stage_alert(["gcc"], "2026-08-02", post=False)
        commands = [row[0] for row in calls]
        self.assertEqual([Path(cmd[1]).name for cmd in commands], [
            "weekly_alert.py", "weekly_rca_helper.py", "post_message.py"
        ])
        self.assertIn("--ce-ids", commands[1])
        self.assertIn("6004", commands[1])
        self.assertIn("--dry-run", commands[2])

    def test_run_weekly_alert_v2_dry_run_wires_locked_builder_and_delivery(self):
        calls = []
        with tempfile.TemporaryDirectory(prefix="weekly-alert-v2-stage-") as tmp:
            tmp = Path(tmp)
            cache, reports = tmp / "cache", tmp / "reports"
            cache.mkdir(); reports.mkdir()
            (reports / "report_gcc_2026-08-02.html").write_text("V2 report placeholder")
            bgms = tmp / "market_bgms.json"
            bgms.write_text(json.dumps({"markets": {"gcc": {"slack_user_ids": ["U123ABC"]}}}))

            def record(cmd, cwd=None, check=True):
                command = [str(part) for part in cmd]
                calls.append((command, cwd, check))
                if "build_market_okr_results.py" in command:
                    Path(command[command.index("--out") + 1]).write_text(json.dumps({
                        "week_start": "2026-08-02", "markets": {"gcc": []}
                    }))
                if "weekly_alert_v2.py" in command:
                    Path(command[command.index("--out") + 1]).write_text(json.dumps({
                        "_rca": {"ce_ids": ["6004"]}
                    }))
                return 0

            with patch.object(run_weekly, "CACHE", cache), patch.object(
                run_weekly, "REPORTS_V2", reports
            ), patch.object(run_weekly, "BGM_CONFIG", bgms), patch.object(
                run_weekly, "run", side_effect=record
            ):
                run_weekly.stage_alert_v2(["gcc"], "2026-08-02", post=False)

        commands = [row[0] for row in calls]
        self.assertEqual([Path(cmd[1]).name for cmd in commands], [
            "build_market_okr_results.py", "weekly_alert_v2.py",
            "weekly_rca_helper.py", "post_message.py",
        ])
        self.assertIn("--okr-results", commands[1])
        self.assertIn("--slug", commands[3])
        self.assertIn("--week", commands[3])
        self.assertIn("--dry-run", commands[3])

    def test_run_weekly_alert_v2_preflights_entire_batch_before_queries_or_posts(self):
        calls = []
        with tempfile.TemporaryDirectory(prefix="weekly-alert-v2-preflight-") as tmp:
            tmp = Path(tmp)
            reports = tmp / "reports"
            reports.mkdir()
            (reports / "report_gcc_2026-08-02.html").write_text("V2 report placeholder")
            bgms = tmp / "market_bgms.json"
            bgms.write_text(json.dumps({"markets": {
                "gcc": {"slack_user_ids": ["U123ABC"]},
                "north_africa": {"slack_user_ids": ["U456DEF"]},
            }}))

            with patch.object(run_weekly, "REPORTS_V2", reports), patch.object(
                run_weekly, "BGM_CONFIG", bgms
            ), patch.object(run_weekly, "run", side_effect=lambda *a, **k: calls.append(a)):
                with self.assertRaisesRegex(SystemExit, "live V2 report is missing for north_africa"):
                    run_weekly.stage_alert_v2(
                        ["gcc", "north_africa"], "2026-08-02", post=False
                    )

        self.assertEqual(calls, [])

    def test_csee_and_nordics_remain_adjacent_in_all_market_runs(self):
        slugs = run_weekly.slugs_for("all")
        csee_index = slugs.index("csee")
        self.assertEqual(slugs[csee_index + 1], "nordics")

    def test_run_weekly_alert_v2_live_preflight_requires_token_and_clean_ledger(self):
        with tempfile.TemporaryDirectory(prefix="weekly-alert-v2-live-preflight-") as tmp:
            tmp = Path(tmp)
            reports = tmp / "reports"
            reports.mkdir()
            (reports / "report_gcc_2026-08-02.html").write_text("V2 report placeholder")
            bgms = tmp / "market_bgms.json"
            bgms.write_text(json.dumps({"markets": {
                "gcc": {"slack_user_ids": ["U123ABC"]}
            }}))
            ledger = tmp / "posted_ledger.json"

            with patch.object(run_weekly, "REPORTS_V2", reports), patch.object(
                run_weekly, "BGM_CONFIG", bgms
            ), patch.object(run_weekly, "POSTED_LEDGER", ledger), patch.dict(
                os.environ, {}, clear=True
            ):
                with self.assertRaisesRegex(SystemExit, "SLACK_TOKEN is not set"):
                    run_weekly.stage_alert_v2(["gcc"], "2026-08-02", post=True)

            ledger.write_text(json.dumps({"2026-08-02": {
                "gcc": {"msg1_ts": "123.45", "msg2_ts": "123.46"}
            }}))
            with patch.object(run_weekly, "REPORTS_V2", reports), patch.object(
                run_weekly, "BGM_CONFIG", bgms
            ), patch.object(run_weekly, "POSTED_LEDGER", ledger), patch.dict(
                os.environ, {"REVENUE_ALERT_SLACK_TOKEN": "test-only"}, clear=True
            ):
                with self.assertRaisesRegex(SystemExit, "already posted.*gcc"):
                    run_weekly.stage_alert_v2(["gcc"], "2026-08-02", post=True)

    def test_export_flagged_writes_sanitized_fixture_csv_shapes_in_temp(self):
        with tempfile.TemporaryDirectory(prefix="weekly-flagged-") as tmp:
            tmp = Path(tmp)
            cache = tmp / "cache"
            cache.mkdir()
            write_snapshot(cache, "sparse")
            write_snapshot(cache, "dense")
            with patch.object(export_flagged, "CACHE", cache), patch.object(
                export_flagged, "ROOT", tmp
            ), patch.object(sys, "argv", ["export_flagged.py", "--week", "2026-08-02"]):
                export_flagged.main()
            losing = list(csv.reader((tmp / "flagged_losing_money_2026-08-02.csv").open()))
            fluct = list(csv.reader((tmp / "flagged_fluctuations_2026-08-02.csv").open()))
            self.assertEqual(losing[0], ["market", "status_bucket", "shown_in_report"] + [c for c, _ in export_flagged.LM_COLS])
            self.assertEqual(fluct[0], ["market", "direction"] + [c for c, _ in export_flagged.FX_COLS])
            # Current fixtures populate losing_money.{existing,new}, while this legacy exporter
            # reads bleeders/eroding/full_waste. Freeze the observed header-only LM output so a
            # later migration is deliberate rather than silently changing the contract.
            self.assertEqual(len(losing), 1)
            self.assertGreater(len(fluct), 1)

    def test_export_full_lm_builds_ungated_rows_from_sanitized_fixture(self):
        with tempfile.TemporaryDirectory(prefix="weekly-full-lm-") as tmp:
            tmp = Path(tmp)
            write_snapshot(tmp, "sparse")
            # Map helpers can enrich from external stores. The engine itself is characterized
            # offline with explicit empty maps; live enrichment remains marked untested.
            with patch.object(export_full_lm.buckets, "_prior_proplus_map", return_value={}), patch.object(
                export_full_lm.buckets, "_troas_now_map", return_value={}
            ), patch.object(export_full_lm.buckets, "_launch_map", return_value={}):
                rows = export_full_lm.build_rows("2026-08-02", str(tmp))
            self.assertEqual(len(rows[0]), 55)
            self.assertGreater(len(rows), 1)
            self.assertEqual(rows[0][0:4], ["Market", "CID", "CE Name", "Table"])
            self.assertEqual(_json_sha(rows), "40aa4ce76aad3594b4f36971d091c5955d28307749f5212a09b69b36023107c9")

    def test_perf_history_ingestion_handles_mixed_tabs_without_sheet_access(self):
        current = [
            ["CID", "Perf action", "Perf comment", "Final action"],
            ["101", "Investigate tracking", "Pause", ""],
            ["101", "", "", ""],
            ["202", "Scale cautiously", "", "Increase"],
        ]
        legacy = [
            ["Date Week", "2026-07-20"],
            ["CID", "Actions Took", "Perf Comments"],
            ["101", "Reduced bids", "Demand softened"],
        ]
        tabs = [(perf_history.dt.date(2026, 8, 2), "w/c 2026-08-02"),
                (perf_history.dt.date(2026, 7, 20), "w/c 2026-07-20")]

        def values(rng):
            return current if "2026-08-02" in rng else legacy

        with tempfile.TemporaryDirectory(prefix="weekly-perf-") as tmp, patch.object(
            perf_history, "OUT", Path(tmp)
        ), patch.object(perf_history, "_list_week_tabs", return_value=tabs), patch.object(
            perf_history, "_gws_get", side_effect=values
        ):
            hist = perf_history.build_sidecar("2026-08-02")
            stored = json.loads((Path(tmp) / "perf_hist_2026-08-02.json").read_text())
        self.assertEqual(hist, stored)
        self.assertEqual([row["week"] for row in hist["101"]], ["2026-08-02", "2026-07-20"])
        self.assertEqual(hist["101"][0], {"week": "2026-08-02", "action": "Pause", "comment": "Investigate tracking"})
        self.assertEqual(hist["202"][0]["action"], "Increase")

    def test_publish_market_and_headout_to_temporary_ledger(self):
        with tempfile.TemporaryDirectory(prefix="weekly-publish-") as tmp:
            tmp = Path(tmp)
            cache, reports, deploy = tmp / "cache", tmp / "reports", tmp / "deploy"
            cache.mkdir(); reports.mkdir(); deploy.mkdir()
            for fixture_slug, publish_slug in (("sparse", "gcc"), ("global", "headout")):
                snapshot = captured(fixture_slug)
                (cache / f"snapshot_{publish_slug}_2026-08-02.json").write_text(
                    json.dumps(snapshot, separators=(",", ":"))
                )
                (reports / f"report_{publish_slug}_2026-08-02.html").write_text(
                    render.render([snapshot], render.TEMPLATE)
                )
            with patch.object(publish_weekly, "CACHE_DIR", cache), patch.object(
                publish_weekly, "REPORT_DIR", reports
            ), patch.object(publish_weekly, "notebook_dir", return_value=deploy):
                publish_weekly.main(["gcc", "--week", "2026-08-02"])
                publish_weekly.main(["headout", "--week", "2026-08-02"])
            state = json.loads((deploy / "weekly_state.json").read_text())
            self.assertEqual([market["slug"] for market in state["markets"]], ["gcc"])
            self.assertEqual(state["headout"]["n_markets"], 3)
            for name in (
                "weekly-report-gcc.html", "weekly-report-gcc-2026-08-02.html",
                "weekly-report-headout.html", "weekly-report-headout-2026-08-02.html",
                "weekly.html", "weekly_state.json",
            ):
                self.assertTrue((deploy / name).exists(), name)

    def test_publish_weekly_can_explicitly_stage_v2_without_changing_v1_default(self):
        with tempfile.TemporaryDirectory(prefix="weekly-publish-v2-") as tmp:
            tmp = Path(tmp)
            cache, v1_reports, v2_reports, deploy = (
                tmp / "cache", tmp / "v1", tmp / "v2", tmp / "deploy"
            )
            for path in (cache, v1_reports, v2_reports, deploy):
                path.mkdir()
            snapshot = captured("sparse")
            (cache / "snapshot_gcc_2026-08-02.json").write_text(json.dumps(snapshot))
            (v1_reports / "report_gcc_2026-08-02.html").write_text("V1 artifact")
            (v2_reports / "report_gcc_2026-08-02.html").write_text("V2 artifact")
            with patch.object(publish_weekly, "CACHE_DIR", cache), patch.object(
                publish_weekly, "REPORT_DIR", v1_reports
            ), patch.object(publish_weekly, "REPORT_DIR_V2", v2_reports), patch.object(
                publish_weekly, "notebook_dir", return_value=deploy
            ):
                publish_weekly.main(["gcc", "--week", "2026-08-02", "--renderer", "v2"])
            self.assertEqual((deploy / "weekly-report-gcc.html").read_text(), "V2 artifact")

    def test_bucket_diff_and_action_ping_read_sanitized_outputs(self):
        sparse = captured("sparse")
        same = bucket_diff.diff_market(sparse, copy.deepcopy(sparse))
        self.assertFalse(same["changed"])
        changed = copy.deepcopy(sparse)
        removed = changed["buckets_final"]["defend"]["losing_money"]["existing"].pop()
        diff = bucket_diff.diff_market(sparse, changed)
        self.assertTrue(diff["changed"])
        self.assertEqual(diff["losing_money"]["removed"][0]["ce_id"], str(removed["ce_id"]))
        with tempfile.TemporaryDirectory(prefix="weekly-ping-") as tmp:
            tmp = Path(tmp)
            write_snapshot(tmp, "sparse")
            with patch.object(thursday_ping, "CACHE", tmp):
                rows = thursday_ping.flagged_rows("sparse", "2026-08-02")
        self.assertGreater(len(rows), 0)
        blocks, counts = thursday_ping.build_blocks("sparse", "2026-08-02", rows, {})
        self.assertTrue(blocks)
        self.assertEqual(counts["review"], len(rows))

    def test_delivery_helpers_are_structurally_checked_without_network(self):
        payload = {"parent": [{"type": "section", "text": "hello"}], "threads": []}
        post_message.validate_payload(payload)
        blocks = post_message.expand_blocks(payload["parent"])
        self.assertEqual(blocks[0]["text"]["text"], "hello")
        native_table = {
            "type": "table",
            "rows": [[
                {"type": "raw_text", "text": "KPI"},
                {"type": "raw_text", "text": "Actual"},
            ], [
                {"type": "raw_text", "text": "Revenue"},
                {"type": "raw_text", "text": "$10.0K"},
            ]],
            "column_settings": [
                {"align": "left", "is_wrapped": True},
                {"align": "right", "is_wrapped": True},
            ],
        }
        self.assertEqual(post_message.expand_blocks([native_table]), [native_table])
        malformed = dict(native_table)
        malformed["rows"] = [native_table["rows"][0], native_table["rows"][1][:-1]]
        with self.assertRaisesRegex(ValueError, "consistent width"):
            post_message.expand_blocks([malformed])
        self.assertEqual(update_posts.header_of([{"type": "header", "text": {"text": "Losing Money"}}]), "Losing Money")
        with tempfile.TemporaryDirectory(prefix="weekly-ledger-") as tmp:
            ledger = Path(tmp) / "ledger.json"
            ledger.write_text(json.dumps({"2026-08-02": {"gcc": {"channel": "C1", "msg1_ts": "1", "msg2_ts": "2"}}}))
            with patch.object(update_posts, "LEDGER_PATH", ledger):
                self.assertEqual(update_posts.resolve_from_ledger("gcc", "2026-08-02"), ("C1", "1", "2"))

    def test_coverage_matrix_names_all_required_paths_and_statuses(self):
        text = COVERAGE_MATRIX.read_text()
        for path in (
            "run_weekly.py", "export_flagged.py", "export_full_lm.py", "perf_history.py",
            "publish_weekly.py", "render.py", "weekly_alert.py", "post_message.py",
            "weekly_rca_helper.py", "bucket_diff.py", "thursday_actions_ping.py",
            "update_posts_weekly.py", "run_market_alert_sweep.py",
        ):
            self.assertIn(path, text)
        for status in ("Verified", "Structurally checked", "Untested"):
            self.assertIn(status, text)

    def test_manual_browser_smoke_evidence_is_well_formed(self):
        contract = json.loads(BROWSER_CONTRACT.read_text())
        result = json.loads(BROWSER_RESULT.read_text())
        self.assertEqual(contract["artifact"], "rendered weekly report artifact")
        self.assertEqual(result["execution_mode"], "manual_in_app_browser")
        self.assertFalse(result["sanitized_fixture_rerun"])
        self.assertEqual(set(result["results"]), {row["name"] for row in contract["checks"]})
        self.assertTrue(all(check["passed"] for check in result["results"].values()))
        self.assertEqual(result["results"]["all_ce"]["row_count"], 46)
        self.assertEqual(result["results"]["console"]["error_count"], 0)


if __name__ == "__main__":
    unittest.main()
