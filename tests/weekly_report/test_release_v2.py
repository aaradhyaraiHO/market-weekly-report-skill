from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
sys.path.insert(0, str(REPORT_DIR))

import headline_v2  # noqa: E402
import release_v2  # noqa: E402


FIXTURE = ROOT / "tests" / "weekly_report" / "fixtures" / "snapshot_north_america_2026-08-02.json"


def approved_goal():
    return {
        "month": "2026-08",
        "monthly_goal": 6_800_000.0,
        "mtd_revenue": 536_000.0,
        "forecast_revenue": 6_500_000.0,
        "as_of": "2026-08-08",
        "source": "approved goals view",
    }


class V2ReleaseGateContract(unittest.TestCase):
    def setUp(self):
        self.market = json.loads(FIXTURE.read_text())
        self.view = headline_v2.build_headline_view(self.market)

    def test_shared_v1_contracts_pass(self):
        result = release_v2.verify_market(self.market, self.view)
        self.assertEqual(result["status"], "pass", result["failures"])
        self.assertEqual(result["coverage"]["ces"], len(self.market["ces"]))
        self.assertGreater(result["coverage"]["ce_revenue_coverage_pct"], 0)

    def test_uncapped_partial_ce_revenue_is_explicitly_warned(self):
        changed = copy.deepcopy(self.market)
        changed["market_summary"]["weekly"][-1]["revenue"] *= 2
        changed_view = headline_v2.build_headline_view(changed)
        result = release_v2.verify_market(changed, changed_view)
        self.assertTrue(any("does not fully reconcile" in warning for warning in result["warnings"]))

    def test_capped_headout_reports_revenue_coverage(self):
        changed = copy.deepcopy(self.market)
        changed["meta"]["market"] = "Headout"
        changed["meta"]["market_slug"] = "headout"
        changed["meta"]["ce_cap"] = {"shown": len(changed["ces"]), "total": len(changed["ces"]) + 10}
        changed["market_summary"]["weekly"][-1]["revenue"] *= 1.1
        changed_view = headline_v2.build_headline_view(changed)
        current = changed["market_summary"]["weekly"][-1]["revenue"]
        previous = changed["market_summary"]["weekly"][-2]["revenue"]
        changed_view["revenue"] = current
        changed_view["wow_abs"] = current - previous
        result = release_v2.verify_market(changed, changed_view)
        self.assertEqual(result["status"], "pass", result["failures"])
        self.assertLess(result["coverage"]["ce_revenue_coverage_pct"], 100.0)
        self.assertTrue(any("All-CE view is capped" in warning for warning in result["warnings"]))

    def test_mover_reordering_fails_closed(self):
        changed = copy.deepcopy(self.view)
        changed["movers"]["drops"] = []
        result = release_v2.verify_market(self.market, changed)
        self.assertEqual(result["status"], "fail")
        self.assertIn("drops mover order differs from V1", result["failures"])

    def test_ce_membership_change_fails_closed(self):
        changed = copy.deepcopy(self.view)
        changed["all_ces"].pop()
        result = release_v2.verify_market(self.market, changed)
        self.assertEqual(result["status"], "fail")
        self.assertIn("All-CE membership differs from V1", result["failures"])

    def test_release_writes_html_goals_and_manifest_data_without_publish(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = release_v2.release([FIXTURE], directory, fetch_goals=False)
            self.assertEqual(manifest["status"], "pass")
            self.assertFalse(manifest["published"])
            self.assertTrue(Path(manifest["artifacts"][0]).exists())
            self.assertTrue(Path(manifest["goals_artifact"]).exists())
            self.assertTrue(any(
                "target fetch disabled" in warning
                for warning in manifest["markets"][0]["warnings"]
            ))

    @mock.patch.object(release_v2.build_v2_goals, "build_market_goal")
    def test_release_fetches_goals_by_default(self, build_goal):
        build_goal.return_value = ("north_america", approved_goal())
        with tempfile.TemporaryDirectory() as directory:
            manifest = release_v2.release([FIXTURE], directory)
            stored = json.loads(Path(manifest["goals_artifact"]).read_text())

        build_goal.assert_called_once()
        self.assertEqual(
            manifest["markets"][0]["coverage"]["monthly_goal"], "current"
        )
        self.assertEqual(
            stored["markets"]["north_america"]["monthly_goal"], 6_800_000.0
        )

    def test_partial_release_preserves_unrequested_market_goals(self):
        with tempfile.TemporaryDirectory() as directory:
            goals_path = Path(directory) / "goals_v2.json"
            goals_path.write_text(json.dumps({
                "schema_version": 1,
                "markets": {"france": approved_goal()},
            }))

            release_v2.release([FIXTURE], directory, fetch_goals=False)
            stored = json.loads(goals_path.read_text())

        self.assertIn("france", stored["markets"])
        self.assertNotIn("north_america", stored["markets"])

    def test_damaged_existing_goals_artifact_does_not_block_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            goals_path = Path(directory) / "goals_v2.json"
            goals_path.write_text("not json")

            manifest = release_v2.release(
                [FIXTURE], directory, fetch_goals=False
            )
            stored = json.loads(goals_path.read_text())

        self.assertEqual(manifest["status"], "pass")
        self.assertEqual(stored["markets"], {})


if __name__ == "__main__":
    unittest.main()
