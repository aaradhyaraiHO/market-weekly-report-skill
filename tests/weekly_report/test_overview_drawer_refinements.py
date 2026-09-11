"""Regression contracts for platform evidence and the CE drawer comparisons."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest import mock
import datetime as dt

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts' / 'weekly_report'))
import build_snapshot
import fetch
from headline_v2 import _ce_drawer_metrics
from paid_platforms import platform_metrics, snapshot_platforms


class DrawerEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.total = dict(spend=1000., cm1=1400., paid_clicks=1000., paid_conversions=40.,
                          paid_impressions=10000., paid_revenue=1800., coupon_wallet=100.)
        self.google = dict(spend=800., cm1=1000., paid_clicks=800., paid_conversions=24.,
                           paid_impressions=9000., paid_revenue=1200., coupon_wallet=80.,
                           sis_impr=9000., sis_elig=18000.)

    def test_additive_reconciliation_and_platform_ratios(self):
        result = platform_metrics(self.total, self.google)
        g, b = result['google'], result['bing']
        for key in self.total:
            self.assertAlmostEqual(g[key] + b[key], self.total[key])
        self.assertEqual(b['paid_ctr_pct'], 20.)
        self.assertEqual(b['paid_cvr_pct'], 8.)
        self.assertEqual(b['paid_rpc'], 3.)
        self.assertEqual(b['paid_cm2'], 400.)
        self.assertAlmostEqual(b['roi_pct'], 400 / 220 * 100)
        self.assertEqual(b['cm1_per_conv'], 25.)
        self.assertEqual(g['paid_sis_pct'], 50.)
        self.assertIsNone(b['paid_sis_pct'])

    def test_missing_is_not_zero_or_guessed_roi(self):
        self.google['coupon_wallet'] = None
        self.google['paid_revenue'] = None
        result = platform_metrics(self.total, self.google)
        for child in result.values():
            self.assertIsNone(child['roi_pct'])
            self.assertIsNone(child['paid_rpc'])
            self.assertIsNone(child['paid_cm2'])
        self.assertEqual(result['bing']['spend'], 200.)

    def test_zero_denominators_keep_additive_zero(self):
        result = platform_metrics(self.total, {**self.total, 'sis_impr': 0, 'sis_elig': 0})
        self.assertEqual(result['bing']['paid_clicks'], 0)
        self.assertIsNone(result['bing']['paid_ctr_pct'])
        self.assertIsNone(result['bing']['paid_cvr_pct'])
        self.assertIsNone(result['bing']['roi_pct'])
        self.assertIsNone(result['google']['paid_sis_pct'])

    def test_legacy_snapshots_only_expose_existing_operands(self):
        result = snapshot_platforms({'paid_clicks': 100, 'paid_clicks_g': 60, 'spend': 200, 'spend_g': 120})
        self.assertEqual(result['bing']['paid_clicks'], 40)
        self.assertEqual(result['bing']['cpc'], 2)
        self.assertIsNone(result['google']['paid_rpc'])
        self.assertIsNone(result['bing']['roi_pct'])
        self.assertIsNone(snapshot_platforms({})['bing']['spend'])

    def test_drawer_preserves_combined_and_aligns_ly_by_week(self):
        row = {**self.total, 'week': '2026-08-30', 'paid_platforms': platform_metrics(self.total, self.google)}
        prior = {**row, 'week': '2026-08-23', 'spend': 500}
        ly = [{**row, 'spend': 250}, {**prior, 'spend': 999}]
        original = deepcopy([prior, row])
        paid = _ce_drawer_metrics([prior, row], ly)['paid']
        spend = next(metric for metric in paid if metric['key'] == 'spend')
        self.assertEqual((spend['w0'], spend['wm1'], spend['delta_pct'], spend['yoy_pct']), (1000, 500, 100, 300))
        self.assertEqual([child['w0'] for child in spend['breakdown']], [800, 200])
        self.assertEqual([prior, row], original)

    def test_funnel_uses_its_own_ly_and_relative_yoy(self):
        row = {'week': '2026-08-30', 'overall_cvr_pct': 99}
        result = _ce_drawer_metrics([row], [], {'CVR': {'current': 4, 'wm1': 5, 'yoy': 2}})
        cvr = next(m for m in result['overall'] if m['key'] == 'funnel_cvr_pct')
        self.assertEqual(cvr['ly_w0'], 2)
        self.assertEqual(cvr['yoy_pct'], 100)
        self.assertEqual(cvr['series'], [])
        zero = _ce_drawer_metrics([row], [], {'CVR': {'current': 4, 'yoy': 4}})
        self.assertIsNone(next(m for m in zero['overall'] if m['key'] == 'funnel_cvr_pct')['yoy_pct'])

    def test_producer_adds_optional_field_without_changing_parent(self):
        raw = dict(spend=1000, cm1=1400, paid_clicks=1000, conversions=40,
                   paid_impressions=10000, offline_revenue=1800, coupon_wallet=100,
                   spend_g=800, cm1_g=1000, paid_clicks_g=800, conversions_g=24,
                   sis_impr=9000, sis_elig=18000, offline_revenue_g=1200)
        before = build_snapshot._weekly_metrics(None, raw)
        after = build_snapshot._weekly_metrics(None, {**raw, 'coupon_wallet_g': 80})
        self.assertEqual(after.pop('paid_platforms')['bing']['paid_rpc'], 3)
        self.assertEqual(before.pop('paid_platform_missing_fields'), ['coupon_wallet_g'])
        self.assertEqual(after, before)

    def test_query_keeps_search_grain_and_adds_google_coupon_operand(self):
        with mock.patch.object(fetch, 'query_df') as query:
            fetch.ce_weekly_ads('North America', dt.date(2026, 8, 30), dt.date(2026, 9, 5))
        sql = query.call_args.args[0]
        self.assertIn("ad_platform IN ('Google Ads', 'Microsoft Ads')", sql)
        self.assertIn("campaign_advertising_channel_type = 'SEARCH'", sql)
        self.assertIn("sum_coupon_and_wallet_credits, 0)) AS coupon_wallet_g", sql)


if __name__ == '__main__':
    unittest.main()
