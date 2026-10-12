from copy import deepcopy
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'alert/v2'))
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import weekly_alert_v2 as alert
import headline_v2


class GrowthRecipientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.groups = Path(self.temp.name) / 'groups.json'
        self.observation = Path(self.temp.name) / 'observed.json'
        self.now = datetime(2026, 10, 12, 8, tzinfo=timezone.utc)
        self.config = {'team_id': 'T029AQ5LB', 'markets': {
            'italy': {'id': 'S09EL7MF2DT', 'handle': 'itgrowth'}}}
        self.groups.write_text(json.dumps(self.config))
        self.bgms = {'markets': {'italy': {'slack_user_ids': ['U123ABC']},
                                'france': {'slack_user_ids': ['U456DEF']}}}
        self.evidence = {'schema': 'weekly-slack-group-availability/v1',
                         'team_id': 'T029AQ5LB', 'observed_at': self.now.isoformat(),
                         'groups': [{'id': 'S09EL7MF2DT', 'handle': 'itgrowth', 'disabled': False}]}

    def resolve(self, evidence=True):
        if evidence:
            self.observation.write_text(json.dumps(self.evidence))
        return alert.resolve_growth_recipients(
            self.bgms, self.groups, self.observation, now=self.now)

    def test_fresh_group_and_individuals_are_both_real_mentions(self):
        original = deepcopy(self.bgms)
        resolved, receipt = self.resolve()
        self.assertEqual(alert.bgm_mentions('italy', resolved),
                         ['<@U123ABC>', '<!subteam^S09EL7MF2DT>'])
        self.assertEqual(alert.bgm_mentions('france', resolved), ['<@U456DEF>'])
        self.assertEqual(receipt['markets']['italy']['reason'], 'active_verified_group_plus_individuals')
        self.assertEqual(self.bgms, original)

    def test_missing_observation_keeps_individuals_and_discards_stale_caller_groups(self):
        self.bgms['markets']['italy']['slack_usergroup_ids'] = ['SUNKNOWN']
        resolved, receipt = self.resolve(False)
        self.assertEqual(alert.bgm_mentions('italy', resolved), ['<@U123ABC>'])
        self.assertEqual(receipt['availability'], 'unavailable')

    def test_disabled_missing_or_renamed_groups_fall_back(self):
        for groups in ([], [{'id': 'S09EL7MF2DT', 'handle': 'itgrowth', 'disabled': True}],
                       [{'id': 'S09EL7MF2DT', 'handle': 'itgrowth', 'disabled': False, 'member_count': 0}],
                       [{'id': 'S09EL7MF2DT', 'handle': 'different-team', 'disabled': False}]):
            with self.subTest(groups=groups):
                self.evidence['groups'] = groups
                resolved, _ = self.resolve()
                self.assertEqual(alert.bgm_mentions('italy', resolved), ['<@U123ABC>'])

    def test_stale_future_wrong_workspace_and_invalid_receipts_fall_back(self):
        original = deepcopy(self.evidence)
        cases = [
            {'observed_at': (self.now - timedelta(hours=25)).isoformat()},
            {'observed_at': (self.now + timedelta(seconds=1)).isoformat()},
            {'observed_at': '2026-10-12T08:00:00'},
            {'observed_at': None},
            {'team_id': 'TANOTHER'}, {'schema': 'untrusted'},
            {'groups': ['not-a-group']}, {'groups': original['groups'] * 2},
            {'groups': [{'id': 'S09EL7MF2DT', 'handle': 'itgrowth', 'disabled': None}]},
        ]
        for fields in cases:
            with self.subTest(fields=fields):
                self.evidence = {**original, **fields}
                resolved, receipt = self.resolve()
                self.assertEqual(receipt['availability'], 'unavailable')
                self.assertEqual(alert.bgm_mentions('italy', resolved), ['<@U123ABC>'])

    def test_group_alone_does_not_replace_mandatory_individuals(self):
        self.bgms['markets']['italy']['slack_user_ids'] = []
        resolved, _ = self.resolve()
        self.assertEqual(alert.bgm_mentions('italy', resolved), [])

    def test_invalid_or_injected_ids_fail_closed(self):
        self.config['markets']['italy']['id'] = '<!channel>'
        self.groups.write_text(json.dumps(self.config))
        with self.assertRaises(ValueError):
            self.resolve()
        with self.assertRaises(ValueError):
            alert.bgm_mentions('italy', {'markets': {'italy': {'slack_user_ids': ['@somebody']}}})

    def test_real_config_contains_only_the_five_owner_verified_market_mappings(self):
        actual = json.loads(alert.DEFAULT_GROWTH_GROUPS.read_text())['markets']
        self.assertEqual(set(actual), {'united_kingdom', 'benelux', 'italy', 'iberia', 'south_america'})
        self.assertEqual(actual['united_kingdom'], actual['benelux'])
        self.assertEqual(actual['iberia'], actual['south_america'])
        individuals = json.loads(alert.DEFAULT_BGMS.read_text())['markets']
        self.assertTrue(all(row.get('slack_user_ids') for row in individuals.values()))

    def test_only_greeting_changes_and_frozen_resolution_is_not_reloaded(self):
        fixture = ROOT / 'tests/weekly_report/fixtures/captured/snapshot_dense_2026-08-02.json.gz'
        with gzip.open(fixture, 'rt') as stream:
            headline = headline_v2.build_headline_view(json.load(stream), {
                'month': '2026-08', 'monthly_goal': 2_000_000,
                'mtd_revenue': 600_000, 'forecast_revenue': 1_800_000,
                'as_of': '2026-08-08'})
        headline['market_slug'] = 'italy'
        headline['market'] = 'Italy'
        resolved, _ = self.resolve()
        fallback = deepcopy(resolved)
        fallback['markets']['italy']['slack_usergroup_ids'] = []
        with patch.object(alert, 'resolve_growth_recipients', side_effect=AssertionError('re-resolved frozen input')):
            before = alert.build_payload(headline, fallback)
            after = alert.build_payload(headline, resolved)
        self.assertIn('<!subteam^S09EL7MF2DT>', after['messages'][0]['blocks'][0]['text']['text'])
        self.assertIn('<@U123ABC>', after['messages'][0]['blocks'][0]['text']['text'])
        after['messages'][0]['blocks'][0] = before['messages'][0]['blocks'][0]
        self.assertEqual(after, before)


if __name__ == '__main__':
    unittest.main()
