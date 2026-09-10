import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/weekly_report'))
import backfill_platform_history as backfill
from build_snapshot import _weekly_metrics


class PlatformBackfill(unittest.TestCase):
    def setUp(self):
        self.source = dict(spend=100, coupon_wallet=10, cm1=120, conversions=10,
                           paid_impressions=10000, paid_clicks=1000, conv_value_gbv=500,
                           offline_revenue=130, spend_g=80, coupon_wallet_g=8,
                           cm1_g=90, paid_clicks_g=800, conversions_g=8,
                           offline_revenue_g=100, gbv_g=400, sis_impr=8000, sis_elig=16000)
        self.frozen = _weekly_metrics(None, self.source)
        self.frozen.pop('paid_platforms')
        self.frozen['week'] = '2026-08-30'

    def test_reconciled_source_only_adds_missing_operands(self):
        before = copy.deepcopy(self.frozen)
        enriched, state = backfill.enriched_row(self.frozen, self.source)
        self.assertEqual(state, 'reconciled')
        self.assertEqual(enriched['coupon_wallet_g'], 8)
        self.assertEqual(enriched['offline_revenue_g'], 100)
        for key, value in before.items():
            self.assertEqual(enriched[key], value)
        self.assertEqual(self.frozen, before)

    def test_source_drift_rejected_not_rescaled(self):
        enriched, state = backfill.enriched_row(self.frozen, {**self.source, 'cm1': 121})
        self.assertEqual(state, 'source_drift')
        self.assertEqual(enriched, self.frozen)

    def test_missing_source_and_modern_snapshot_preserved(self):
        self.assertEqual(backfill.enriched_row(self.frozen, None)[1], 'source_missing')
        modern = _weekly_metrics(None, self.source)
        self.assertEqual(backfill.enriched_row(modern, self.source), (modern, 'already_stored'))

    def test_fills_only_nulls_and_refuses_parent_drift(self):
        old = dict(paid=[dict(key='paid_revenue', w0=130, series=[], breakdown=[dict(key='google', w0=None, wm1=7)])])
        new = copy.deepcopy(old)
        new['paid'][0]['breakdown'][0].update(w0=100, wm1=8)
        result = backfill.attach_breakdowns(old, new)
        self.assertEqual(result['paid'][0]['breakdown'][0], dict(key='google', w0=100, wm1=7))
        new['paid'][0]['w0'] = 131
        with self.assertRaises(ValueError):
            backfill.attach_breakdowns(old, new)

