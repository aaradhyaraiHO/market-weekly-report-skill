from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]

class ReviewResourceRetryRuntime(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_independent_resource_recovery(self):
        result = subprocess.run(['node', 'tests/weekly_report/js/review_resource_retry_runtime.cjs'], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('regressions passed', result.stdout)

    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_content_response_transport(self):
        result = subprocess.run(['node', 'tests/weekly_report/js/review_content_runtime.cjs'], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('regressions passed', result.stdout)
