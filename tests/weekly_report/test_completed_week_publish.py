import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts' / 'weekly_report'))
from publish_weekly import require_completed_week


class CompletedWeekPublishTest(unittest.TestCase):
    def test_monday_and_midweek_keep_last_finished_week(self):
        for day in (7, 9, 12):
            require_completed_week('2026-08-30', dt.date(2026, 9, day))
            with self.assertRaisesRegex(ValueError, 'not a completed'):
                require_completed_week('2026-09-06', dt.date(2026, 9, day))

    def test_sunday_allows_the_week_that_just_ended(self):
        require_completed_week('2026-09-06', dt.date(2026, 9, 13))
