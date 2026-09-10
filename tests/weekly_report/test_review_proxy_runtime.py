import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ReviewProxyRuntime(unittest.TestCase):
    def test_bounded_reads_never_retry_writes_or_bypass_auth(self):
        result = subprocess.run(
            [shutil.which('node'), str(ROOT / 'tests/weekly_report/js/review_proxy_runtime.cjs')],
            cwd=ROOT, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Review proxy runtime regressions passed', result.stdout)
