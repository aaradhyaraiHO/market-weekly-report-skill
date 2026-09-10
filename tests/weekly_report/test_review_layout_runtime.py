import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ReviewLayoutRuntime(unittest.TestCase):
    def test_collapse_preserves_drafts_and_header_stays_inside_scrollport(self):
        result = subprocess.run(
            [shutil.which('node'), str(ROOT / 'tests/weekly_report/js/review_layout_runtime.cjs')],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
