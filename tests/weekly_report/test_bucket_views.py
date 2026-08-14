from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
FIXTURE = Path(__file__).parent / "fixtures" / "snapshot_north_america_2026-08-02.json"
sys.path.insert(0, str(REPORT_DIR))

import bucket_views  # noqa: E402


class BucketViewsContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(FIXTURE.read_text())

    def test_current_losing_money_rows_preserve_report_order(self):
        rows = bucket_views.final_losing_money_rows(self.snapshot)
        self.assertEqual([str(row["ce_id"]) for row in rows], ["101"])

    def test_current_fluctuation_directions_are_explicit(self):
        down = bucket_views.final_fluctuation_rows(self.snapshot, "down")
        up = bucket_views.final_fluctuation_rows(self.snapshot, "up")
        self.assertEqual([str(row["ce_id"]) for row in down], ["101"])
        self.assertEqual([str(row["ce_id"]) for row in up], ["202"])
        with self.assertRaises(ValueError):
            bucket_views.final_fluctuation_rows(self.snapshot, "sideways")

    def test_legacy_exporter_groups_remain_separate(self):
        for group in ("bleeders", "eroding", "full_waste", "paused", "tracking_gap"):
            self.assertEqual(bucket_views.legacy_losing_money_rows(self.snapshot, group), [])


if __name__ == "__main__":
    unittest.main()
