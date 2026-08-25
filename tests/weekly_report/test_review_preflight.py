"""Contract coverage for the no-write isolated Review preflight."""

from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "weekly_report" / "notes" / "review_preflight.py"


class ReviewPreflightContractTest(unittest.TestCase):
    def test_script_is_non_mutating_and_isolation_named(self):
        text = SCRIPT.read_text()
        self.assertIn("never calls Apps Script,\nSlack, Granola or the legacy", text)
        self.assertIn("REVIEW_MODE_APPS_SCRIPT_URL", text)
        self.assertNotIn('os.environ.get("NOTES_URL")', text)
        self.assertNotIn("action_upsert", text)

    def test_missing_config_fails_closed(self):
        result = subprocess.run([sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, text=True, env={})
        self.assertEqual(result.returncode, 1)
        self.assertIn("Review preflight: BLOCKED", result.stdout)
        self.assertIn("REVIEW_MODE_APPS_SCRIPT_URL is missing", result.stdout)


if __name__ == "__main__":
    unittest.main()
