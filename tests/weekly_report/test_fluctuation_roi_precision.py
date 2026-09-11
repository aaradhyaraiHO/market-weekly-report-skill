"""RPC/CM1 display precision must preserve windows and bucket decisions."""
import copy
import datetime as dt
from pathlib import Path
import sys
import unittest

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/weekly_report'))
import alerts
import headline_v2


class FluctuationRoiPrecision(unittest.TestCase):
    def setUp(self):
        self.market = {'ces': [{'ce_id': '6853', 'weekly': [
            {'week': '2026-08-30', 'spend_g': 384.8132, 'cm1_g': 674.8328,
             'roi_g': 175.37, 'paid_clicks_g': 459, 'conversions_g': 31},
            {'week': '2026-08-23', 'spend_g': 273.6421, 'cm1_g': 785.9147,
             'roi_g': 287.21, 'paid_clicks_g': 255, 'conversions_g': 25}]}]}
        self.row = {'ce_id': '6853', 'signal': 'rpc', 'verdict': 'watch', 'swing_pct': -50.3,
                    'weeks': [
                        {'week': '2026-08-30', 'span_days': 7, 'spend': 385, 'roi': 175,
                         'clicks': 459, 'cm1conv': 21.77, 'cpc': .84},
                        {'week': '2026-08-23', 'span_days': 7, 'spend': 274, 'roi': 287,
                         'clicks': 255, 'cm1conv': 31.44, 'cpc': 1.07}]}

    def result(self):
        return headline_v2._fluctuation_roi_precision(self.market, [self.row])[0]

    def test_frozen_country_music_exact_operands_preserve_all_fields(self):
        before = copy.deepcopy((self.market, self.row))
        result = self.result()
        expected = ((674.8328 / 384.8132) / (785.9147 / 273.6421) - 1) * 100
        self.assertAlmostEqual(result.pop('roi_wow_pct'), expected)
        self.assertEqual(result, self.row)
        self.assertEqual((self.market, self.row), before)

    def test_partial_frozen_window_never_uses_full_week(self):
        for b in self.row['weeks']:
            b['span_days'] = 5
        self.assertIsNone(self.result()['roi_wow_pct'])

    def test_new_partial_blocks_use_producer_operand_not_cache(self):
        for b, raw in zip(self.row['weeks'], (175.49, 286.51)):
            b.update(span_days=5, roi_unrounded=raw)
        self.assertAlmostEqual(self.result()['roi_wow_pct'], (175.49 / 286.51 - 1) * 100)
        self.row['weeks'][0]['roi_unrounded'] = None
        self.assertIsNone(self.result()['roi_wow_pct'])

    def test_mismatched_evidence_and_invalid_values_fail_closed(self):
        original = copy.deepcopy(self.market)
        for key, value in [('spend_g', 400), ('cm1_g', 670), ('paid_clicks_g', 500),
                           ('conversions_g', 20), ('roi_g', None), ('cm1_g', float('nan'))]:
            with self.subTest(key=key):
                self.market = copy.deepcopy(original)
                self.market['ces'][0]['weekly'][0][key] = value
                self.assertIsNone(self.result()['roi_wow_pct'])

    def test_raw_null_zero_baseline_and_window_mismatch(self):
        for b in self.row['weeks']:
            b['roi_unrounded'] = float(b['roi'])
        self.row['weeks'][1].update(roi=0, roi_unrounded=0)
        self.assertIsNone(self.result()['roi_wow_pct'])
        self.row['weeks'][1].update(roi=287, roi_unrounded=287, span_days=6)
        self.assertIsNone(self.result()['roi_wow_pct'])
        self.row['weeks'][1].update(span_days=7, week='2026-08-16')
        self.assertIsNone(self.result()['roi_wow_pct'])

    def test_both_lanes_are_presentation_only(self):
        self.market['buckets_final'] = {'defend': {'seasonality_down': [self.row]},
                                        'compound': {'seasonality_up': [self.row]}}
        before = copy.deepcopy(self.market)
        view = headline_v2._diagnostic_bucket_view(self.market)['fluctuations']
        for lane in ('up', 'down'):
            self.assertIsNotNone(view[lane][0].pop('roi_wow_pct'))
            self.assertEqual(view[lane], [self.row])
        self.assertEqual(self.market, before)

    def test_daily_producer_retains_exact_operand_and_validity_gate(self):
        day = dt.date(2026, 8, 30)
        ads = pd.DataFrame([{'combined_entity_id': '1', 'report_date': day,
                             'spend': 100.1234, 'cm1': 175.3456, 'conversions': 10, 'clicks': 100}])
        funnel = pd.DataFrame(columns=['combined_entity_id', 'report_date'])
        block = alerts._week_blocks(ads, funnel, '1', day, day, n=1)[0]
        self.assertEqual(block['roi'], round(175.3456 / 100.1234 * 100))
        self.assertAlmostEqual(block['roi_unrounded'], 175.3456 / 100.1234 * 100)
        ads.loc[0, 'spend'] = 1
        block = alerts._week_blocks(ads, funnel, '1', day, day, n=1)[0]
        self.assertIsNone(block['roi'])
        self.assertIsNone(block['roi_unrounded'])


if __name__ == '__main__':
    unittest.main()
