from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
sys.path.insert(0, str(REPORT_DIR))


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


guard = load("v2_action_routing_guard", REPORT_DIR / "verify_v2_action_routing.py")
publisher = load("v2_action_routing_publisher", REPORT_DIR / "publish_weekly.py")


class V2ActionRoutingGuardTests(unittest.TestCase):
    def write_report(self, deploy: Path, name: str, route: str) -> None:
        (deploy / name).write_text(
            f"<script>const ACTIONS_URL = DATA.actions_url || '{route}';</script>"
        )

    def test_clean_v2_package_stages_both_isolated_proxies_and_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            deploy = Path(directory)
            self.write_report(deploy, "weekly-report-france.html", "/api/actions")
            self.write_report(deploy, "weekly-report-france-2026-08-09.html", "/api/actions")
            publisher.stage_v2_proxies(deploy)
            result = guard.audit_v2_deployment(deploy, require_proxies=True)
            self.assertEqual(result, {"reports": 2, "current": 1, "dated": 1})
            self.assertTrue((deploy / "api" / "actions.js").is_file())
            self.assertTrue((deploy / "api" / "review.js").is_file())

    def test_guard_rejects_review_route_in_any_current_or_dated_report(self):
        with tempfile.TemporaryDirectory() as directory:
            deploy = Path(directory)
            self.write_report(deploy, "weekly-report-france.html", "/api/actions")
            self.write_report(deploy, "weekly-report-france-2026-08-09.html", "/api/review")
            with self.assertRaisesRegex(ValueError, "/api/actions only"):
                guard.audit_v2_deployment(deploy, require_proxies=False)

    def test_guard_requires_current_alias_dated_report_and_both_proxies(self):
        with tempfile.TemporaryDirectory() as directory:
            deploy = Path(directory)
            self.write_report(deploy, "weekly-report-france-2026-08-09.html", "/api/actions")
            with self.assertRaisesRegex(ValueError, "current aliases"):
                guard.audit_v2_deployment(deploy, require_proxies=False)

            self.write_report(deploy, "weekly-report-france.html", "/api/actions")
            with self.assertRaisesRegex(ValueError, "proxies missing"):
                guard.audit_v2_deployment(deploy)

    def test_proxy_contracts_are_permanently_cross_route_fail_closed(self):
        actions = (REPORT_DIR / "notes" / "actions_proxy_api.js").read_text()
        review = (REPORT_DIR / "notes" / "review_proxy_api.js").read_text()
        self.assertIn('new Set(["action_list", "action_upsert", "action_delete"])', actions)
        self.assertIn("ACTIONS_PROXY_SECRET", actions)
        self.assertNotIn("process.env.REVIEW_MODE_", actions)
        self.assertIn("REVIEW_MODE_APPS_SCRIPT_URL", review)
        self.assertIn("REVIEW_MODE_PROXY_SECRET", review)
        self.assertIn('error: "review action required"', review)
        self.assertNotIn("ACTIONS_PROXY_SECRET", review)


if __name__ == "__main__":
    unittest.main()
