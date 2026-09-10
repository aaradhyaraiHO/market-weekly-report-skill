import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts' / 'weekly_report'))
from upgrade_frozen_release import attach_metrics, attach_frozen_mover_dollars, assert_payload_preserved


class FrozenReleaseTest(unittest.TestCase):
    def test_midweek_movers_keep_published_values_and_missing_ly(self):
        view = {'all_ces': [{'ce_id': '1', 'revenue': 100, 'weekly_ly_revenue': 80},
                           {'ce_id': '2', 'revenue': 20, 'weekly_ly_revenue': None}],
                'movers': {'drops': [{'ce_id': '1', 'revenue': 100, 'yoy_pct': 25},
                                     {'ce_id': '2', 'revenue': 20, 'yoy_pct': None}]}}
        before = deepcopy(view)
        attach_frozen_mover_dollars(view)
        assert_payload_preserved(before, view)
        self.assertEqual(view['movers']['drops'][0]['yoy_abs'], 20)
        self.assertIsNone(view['movers']['drops'][1]['yoy_abs'])
        view['movers']['drops'][0]['revenue'] = 99
        with self.assertRaisesRegex(ValueError, 'changed'):
            assert_payload_preserved(before, view)

    def test_midweek_rejects_missing_record_or_mover_operand_drift(self):
        with self.assertRaisesRegex(ValueError, 'removed'):
            assert_payload_preserved({'notes': ['existing']}, {})
        with self.assertRaisesRegex(ValueError, 'length changed'):
            assert_payload_preserved(['existing'], [])
        with self.assertRaisesRegex(ValueError, 'revenue mismatch'):
            attach_frozen_mover_dollars({'all_ces': [{'ce_id': '1', 'revenue': 100}],
                                        'movers': {'drops': [{'ce_id': '1', 'revenue': 99}]}})

    def test_hidden_single_market_filter_stays_hidden(self):
        template = (Path(__file__).resolve().parents[2] / 'scripts' / 'weekly_report'
                    / 'template' / 'report_v2_template.html').read_text()
        self.assertIn('.filter-field[hidden] { display:none; }', template)

    def test_additions_preserve_frozen_parent_and_input(self):
        old = {'paid': [{'key': 'clicks', 'w0': 10, 'wm1': 8,
                        'delta_abs': 2, 'delta_pct': 25, 'series': [8, 10],
                        'label': 'Existing label'}]}
        before = deepcopy(old)
        new = deepcopy(old)
        new['paid'][0].update(label='New label', ly_w0=5, yoy_pct=100,
                              breakdown=[{'platform': 'google'}])
        result = attach_metrics(old, new)
        self.assertEqual(old, before)
        self.assertEqual(result['paid'][0]['label'], 'Existing label')
        self.assertEqual(result['paid'][0]['w0'], 10)
        self.assertEqual(result['paid'][0]['yoy_pct'], 100)

    def test_drift_rejected_for_each_frozen_operand(self):
        for key in ('w0', 'wm1', 'delta_abs', 'delta_pct', 'series'):
            with self.subTest(key=key):
                old = {'overall': [{'key': 'revenue', key: 1}]}
                new = {'overall': [{'key': 'revenue', key: 2}]}
                with self.assertRaisesRegex(ValueError, 'frozen metric drift'):
                    attach_metrics(old, new)
