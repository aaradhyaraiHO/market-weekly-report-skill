"""Exercise next-run packaging against the real V2 renderer and injector."""
import sys
import gzip
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/weekly_report"))
import publish_weekly
import render_v2
import review_release_preflight


class MiniAuditPackagingTests(unittest.TestCase):
    def test_fresh_v2_package_keeps_audit_routes_and_preserves_v1(self):
        fixture = ROOT / "tests/weekly_report/fixtures/captured/snapshot_sparse_2026-08-02.json.gz"
        with gzip.open(fixture, "rt") as source:
            shell = render_v2.render([json.load(source)])
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory) / "stage"
            baseline = Path(directory) / "baseline"
            stage.mkdir()
            baseline.mkdir()
            (stage / "index.html").write_text("existing notebook home")
            report = "weekly-report-north-america.html"
            (stage / report).write_text(shell)
            (stage / "weekly-report-north-america-2026-08-02.html").write_text(shell)
            (stage / "weekly-report-headout.html").write_text(shell)
            legacy = "weekly-report-france-2026-07-12.html"
            for folder in (stage, baseline):
                (folder / legacy).write_bytes(b'<aside id="drawer">Original history</aside>')
            # Reusing an older deployment must remove its retired import endpoints.
            (stage / "api").mkdir()
            for route in ("granola-link.js", "granola-pull.js", "granola-review.js"):
                (stage / "api" / route).write_text("stale endpoint")
            publish_weekly.stage_v2_proxies(stage)
            publish_weekly.stage_v2_review(stage)
            self.assertEqual(review_release_preflight.verify(stage, report, baseline), [])
            self.assertTrue((stage / "api/review-extract.js").is_file())
            for route in ("granola-link.js", "granola-pull.js", "granola-review.js"):
                self.assertFalse((stage / "api" / route).exists())
            self.assertNotIn("/api/granola-link", (stage / report).read_text())
            self.assertEqual((stage / legacy).read_bytes(), (baseline / legacy).read_bytes())
            for module in ("review_ai_provider.mjs", "review_meeting_import.mjs"):
                self.assertTrue((stage / "lib" / module).is_file())
            before = (stage / report).read_bytes()
            publish_weekly.stage_v2_review(stage)
            self.assertEqual((stage / report).read_bytes(), before)

    def test_broken_v2_mount_stops_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            (stage / "weekly-report-france.html").write_text(
                '<script id="report-data"></script><nav data-report-view="overview"></nav>'
            )
            with self.assertRaisesRegex(RuntimeError, "Mini Audit packaging failed"):
                publish_weekly.stage_v2_review(stage)


if __name__ == "__main__":
    unittest.main()
