from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "weekly_report" / "run_v2_release.py"
SPEC = importlib.util.spec_from_file_location("run_v2_release", MODULE_PATH)
assert SPEC and SPEC.loader
release = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release
SPEC.loader.exec_module(release)


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

    def test_notebook_stage_never_writes_perf_sheet(self) -> None:
        plan = release.build_plan(self.week, self.notebook)
        stage = next(step for step in plan if step.name == "stage-notebook")
        self.assertIn("--skip-perf-sheet", stage.command)
        self.assertEqual(stage.env, {"MMR_NOTEBOOK_DIR": str(self.notebook)})

    def test_v2_publisher_stages_authenticated_review_proxy(self) -> None:
        source = (ROOT / "scripts" / "weekly_report" / "publish_weekly.py").read_text()
        self.assertIn('review_proxy_api.js', source)
        self.assertIn('api_dir / "review.js"', source)

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
