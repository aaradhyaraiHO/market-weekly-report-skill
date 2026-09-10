import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ReviewLayoutRuntime(unittest.TestCase):
    def test_mobile_navigation_and_review_controls_have_44px_targets(self):
        css = (ROOT / 'scripts/weekly_report/review/review-view.css').read_text()
        template = (ROOT / 'scripts/weekly_report/template/report_v2_template.html').read_text()
        self.assertIn('@media(max-width:900px){#review-view .rv-btn{min-height:44px}}', css)
        self.assertIn('.nav-item { min-height:44px; }', template)
        self.assertIn('.drawer-close { flex:0 0 44px; width:44px; min-width:44px; min-height:44px; }', template)

    def test_collapse_preserves_drafts_and_header_stays_inside_scrollport(self):
        result = subprocess.run(
            [shutil.which('node'), str(ROOT / 'tests/weekly_report/js/review_layout_runtime.cjs')],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
