from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "weekly_report" / "run_v2_release.py"
SPEC = importlib.util.spec_from_file_location("run_v2_release", MODULE_PATH)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)

PUBLISH_MODULE_PATH = ROOT / "scripts" / "weekly_report" / "publish_weekly.py"
PUBLISH_SPEC = importlib.util.spec_from_file_location("publish_weekly", PUBLISH_MODULE_PATH)
assert PUBLISH_SPEC and PUBLISH_SPEC.loader
publisher = importlib.util.module_from_spec(PUBLISH_SPEC)
sys.modules[PUBLISH_SPEC.name] = publisher
PUBLISH_SPEC.loader.exec_module(publisher)


class RunV2ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.week = "2026-08-09"
        self.notebook = ROOT / ".cache" / "weekly_report" / "test-notebook"

    def test_default_plan_is_complete_and_external_write_free(self) -> None:
        plan = release.build_plan(self.week, self.notebook)
        names = [step.name for step in plan]
        self.assertEqual(
            names,
            [
                "baseline",
                "build-markets",
                "build-headout",
                "build-market-okrs",
                "combined-v2-gate",
                "alert-readiness",
                "stage-notebook",
                "alerts-dry-run",
            ],
        )
        self.assertFalse(any(step.external_write for step in plan))
        self.assertFalse(any("--post" in step.command for step in plan))
        self.assertFalse(any(step.command[0] == "vercel" for step in plan))

    def test_combined_gate_contains_every_market_and_headout_snapshot(self) -> None:
        plan = release.build_plan(self.week, self.notebook)
        gate = next(step for step in plan if step.name == "combined-v2-gate")
        snapshots = [arg for arg in gate.command if "snapshot_" in arg]
        self.assertEqual(len(snapshots), len(release.config.MARKETS) + 1)
        for slug in (*release.config.MARKETS, "headout"):
            self.assertTrue(any(f"snapshot_{slug}_{self.week}.json" in item for item in snapshots))
        self.assertIn("--okr-results", gate.command)

    def test_notebook_stage_never_writes_perf_sheet(self) -> None:
        plan = release.build_plan(self.week, self.notebook)
        stage = next(step for step in plan if step.name == "stage-notebook")
        self.assertIn("--skip-perf-sheet", stage.command)
        self.assertEqual(stage.env, {"MMR_NOTEBOOK_DIR": str(self.notebook)})

    def test_v2_publisher_stages_isolated_review_and_action_proxies(self) -> None:
        notes = ROOT / "scripts" / "weekly_report" / "notes"
        with tempfile.TemporaryDirectory() as directory:
            deploy = Path(directory)
            review_target, actions_target = publisher.stage_v2_proxies(deploy)

            self.assertEqual(review_target, deploy / "api" / "review.js")
            self.assertEqual(actions_target, deploy / "api" / "actions.js")
            self.assertEqual(review_target.read_bytes(), (notes / "review_proxy_api.js").read_bytes())
            self.assertEqual(actions_target.read_bytes(), (notes / "actions_proxy_api.js").read_bytes())

        review_source = (notes / "review_proxy_api.js").read_text()
        actions_source = (notes / "actions_proxy_api.js").read_text()
        self.assertIn("REVIEW_MODE_APPS_SCRIPT_URL", review_source)
        self.assertIn("REVIEW_MODE_PROXY_SECRET", review_source)
        self.assertIn("review action required", review_source)
        self.assertNotIn("ACTIONS_PROXY_SECRET", review_source)
        self.assertIn("ACTIONS_PROXY_SECRET", actions_source)
        self.assertIn('new Set(["action_list", "action_upsert", "action_delete"])', actions_source)
        self.assertNotIn("process.env.REVIEW_MODE_", actions_source)

    def test_live_steps_are_explicit_and_ordered(self) -> None:
        plan = release.build_plan(
            self.week, self.notebook, deploy=True, post_alerts=True
        )
        self.assertEqual([step.name for step in plan][-2:], ["deploy-vercel", "post-alerts"])
        self.assertTrue(all(step.external_write for step in plan[-2:]))
        self.assertIn("--post", plan[-1].command)

    def test_alert_post_requires_deployment(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires --deploy"):
            release.build_plan(self.week, self.notebook, post_alerts=True)

    def test_plan_cli_is_no_write_json(self) -> None:
        result = subprocess.run(
            (
                sys.executable,
                str(MODULE_PATH),
                "--week",
                self.week,
                "--plan",
            ),
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["week"], self.week)
        self.assertEqual(len(payload["markets"]), len(release.config.MARKETS) + 1)
        self.assertEqual(payload["steps"][-1]["name"], "alerts-dry-run")


if __name__ == "__main__":
    unittest.main()
