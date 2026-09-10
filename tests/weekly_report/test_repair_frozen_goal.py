import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/weekly_report'))
import headline_v2
import repair_frozen_goal
from upgrade_frozen_release import DATA


class FrozenGoalRepair(unittest.TestCase):
    def test_only_goal_fields_change_and_latest_alias_is_refused(self):
        fixture = Path(__file__).parent / 'fixtures/snapshot_north_america_2026-08-02.json'
        raw = json.loads(fixture.read_text())
        view = headline_v2.build_headline_view(raw)
        goal = dict(month='2026-08', monthly_goal=1000000, mtd_revenue=200000,
                    forecast_revenue=900000, as_of='2026-08-08')
        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / 'weekly-report-north-america-2026-08-02.html'
            html = '<aside>preserve preview</aside><script id="report-data" type="application/json">' + json.dumps({'headlines': [view]}) + '</script>'
            page.write_text(html)
            receipt = repair_frozen_goal.repair(page, fixture, goal)
            self.assertTrue(receipt['non_goal_payload_preserved'])
            updated = json.loads(DATA.search(page.read_text()).group(1))['headlines'][0]
            self.assertEqual(updated['monthly']['monthly_goal'], 1000000)
            self.assertEqual(updated['revenue'], view['revenue'])
            self.assertEqual(updated['all_ces'], view['all_ces'])
            self.assertTrue(page.read_text().startswith('<aside>preserve preview</aside>'))
            latest = Path(directory) / 'weekly-report-north-america.html'
            latest.write_text(html)
            with self.assertRaises(ValueError):
                repair_frozen_goal.repair(latest, fixture, goal)
