import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

class MiniAuditRuntime(unittest.TestCase):
    def test_meeting_import_replay_and_granola_payload(self):
        result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/weekly_report/js/review_import_runtime.mjs')], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_memory_cache_transport_auth_and_immediate_approval(self):
        result = subprocess.run([shutil.which('node'), str(ROOT / 'tests/weekly_report/js/review_fixes_runtime.cjs')], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_openai_provider_rejects_incomplete_results_and_isolates_credentials(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required for audit runtime checks')
        result = subprocess.run([node, str(ROOT / 'tests/weekly_report/js/review_openai_runtime.mjs')], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('runtime regressions passed', result.stdout)

    def test_service_retries_binding_isolation_and_cache_races(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'Node is required for audit runtime checks')
        result = subprocess.run([node, str(ROOT / 'tests/weekly_report/js/mini_audit_runtime.cjs')], cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('runtime regressions passed', result.stdout)

if __name__ == '__main__':
    unittest.main()
