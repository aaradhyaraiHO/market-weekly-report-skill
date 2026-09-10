from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API_FIXTURES = ("index.html", "api/actions.js", "api/review.js", "api/review-summary.js", "api/review-extract.js")
SCRIPT = ROOT / "scripts" / "weekly_report" / "review_release_preflight.py"
INJECTOR = (ROOT / "scripts" / "weekly_report" / "inject_review_view.py").read_text()


def load_module():
    spec = importlib.util.spec_from_file_location("review_release_preflight", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class ReviewReleasePreflightTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.preflight = load_module()

    def test_rejects_the_partial_report_only_deployment_shape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "weekly-report-north-america.html").write_text('id="review-view" initReviewView')
            failures = self.preflight.verify(root, "weekly-report-north-america.html")
            self.assertIn("missing required full-site artifact: index.html", failures)
            self.assertIn("missing required full-site artifact: api/actions.js", failures)

    def test_injector_explicitly_excludes_headout_current_and_dated_routes(self):
        self.assertIn("HEADOUT_RE", INJECTOR)
        self.assertIn("Review excluded from Headout/global", INJECTOR)
        self.assertIn("remove_review(path)", INJECTOR)

    def test_accepts_a_complete_shell_with_review_bootstrap(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "api").mkdir()
            for path in API_FIXTURES:
                (root / path).write_text("ok")
            (root / "weekly-report-north-america.html").write_text('id="review-view" initReviewView')
            (root / "weekly-report-headout.html").write_text("global report without review")
            (root / "weekly-report-headout-2026-08-16.html").write_text("dated global report without review")
            self.assertEqual(self.preflight.verify(root, "weekly-report-north-america.html"), [])
            (root / "api/granola-link.js").write_text("stale endpoint")
            self.assertEqual(self.preflight.verify(root, "weekly-report-north-america.html"),
                             ["retired meeting import route remains: api/granola-link.js"])

    def test_rejects_review_in_headout_global_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "api").mkdir()
            for path in API_FIXTURES:
                (root / path).write_text("ok")
            (root / "weekly-report-north-america.html").write_text('id="review-view" initReviewView')
            (root / "weekly-report-headout.html").write_text('id="review-view" initReviewView data-report-view="review"')
            failures = self.preflight.verify(root, "weekly-report-north-america.html")
            self.assertIn("weekly-report-headout.html must not contain Review", failures)

    def test_rejects_when_any_market_report_lacks_review(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "api").mkdir()
            for path in API_FIXTURES:
                (root / path).write_text("ok")
            (root / "weekly-report-north-america.html").write_text('id="review-view" initReviewView')
            (root / "weekly-report-france.html").write_text("existing report only")
            failures = self.preflight.verify(root, "weekly-report-north-america.html")
            self.assertIn("weekly-report-france.html has no Review container", failures)
            self.assertIn("weekly-report-france.html has no Review bootstrap", failures)

    def test_rejects_missing_transcript_extraction_route(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "api").mkdir()
            for path in API_FIXTURES:
                if path != "api/review-extract.js":
                    (root / path).write_text("ok")
            (root / "weekly-report-north-america.html").write_text('id="review-view" initReviewView')
            self.assertEqual(self.preflight.verify(root, "weekly-report-north-america.html"),
                             ["missing required full-site artifact: api/review-extract.js"])

    def test_legacy_exemption_requires_unchanged_baseline_and_never_exempts_v2(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "stage"
            baseline = Path(temp) / "baseline"
            (root / "api").mkdir(parents=True)
            baseline.mkdir()
            for path in API_FIXTURES:
                (root / path).write_text("ok")
            report = "weekly-report-north-america.html"
            (root / report).write_text('id="review-view" initReviewView')
            archive = "weekly-report-france-2026-07-12.html"
            for folder in (root, baseline):
                (folder / archive).write_text('<aside id="drawer"></aside><script id="report-data">original V1 archive</script>')
            self.assertEqual(self.preflight.verify(root, report, baseline), [])
            self.assertTrue(self.preflight.verify(root, report))
            (root / archive).write_text('<aside id="drawer"></aside>modified V1 archive')
            self.assertTrue(self.preflight.verify(root, report, baseline))
            for folder in (root, baseline):
                (folder / archive).write_text('id="report-data" data-report-view="overview"')
            self.assertTrue(self.preflight.verify(root, report, baseline))
            for folder in (root, baseline):
                (folder / archive).write_text('<aside id="drawer"></aside>original V1 archive')
                (folder / report).write_text('<aside id="drawer"></aside>requested V1 report')
            self.assertTrue(self.preflight.verify(root, report, baseline))


if __name__ == "__main__":
    unittest.main()
