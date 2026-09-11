"""Future platform history: exact source operands, unchanged core metrics."""
import copy
import datetime as dt
from pathlib import Path
import re
import sys
import unittest
import ast
import subprocess
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import config
import fetch
import build_snapshot
from build_snapshot import _weekly_metrics
from headline_v2 import _ce_drawer_metrics
from paid_platforms import (SOURCE_FIELDS, GOOGLE_SOURCE_FIELDS, source_platforms,
                            attach_aggregate_platforms, missing_source_fields)


class FuturePlatformHistory(unittest.TestCase):
    def setUp(self):
        self.source = dict(spend=200, coupon_wallet=20, cm1=240, conversions=20,
                           paid_impressions=20000, paid_clicks=2000, offline_revenue=260,
                           spend_g=120, coupon_wallet_g=12, cm1_g=150, paid_clicks_g=1200,
                           conversions_g=12, offline_revenue_g=160, sis_impr=12000, sis_elig=24000)

    def test_platform_formulas_use_operands_not_averaged_ratios(self):
        p = source_platforms(self.source)
        for key in SOURCE_FIELDS:
            self.assertAlmostEqual(p['google'][key]+p['bing'][key], self.source[SOURCE_FIELDS[key]])
        g, b = p['google'], p['bing']
        self.assertAlmostEqual(g['roi_pct'], 150/132*100)
        self.assertAlmostEqual(b['roi_pct'], 90/88*100)
        self.assertEqual(g['paid_cvr_pct'], 1)
        self.assertEqual(b['paid_cvr_pct'], 1)
        self.assertEqual(g['cpc'], .1)
        self.assertEqual(b['paid_ctr_pct'], 10)
        self.assertEqual(g['paid_cm2'], 40)
        self.assertEqual(b['paid_cm2'], 20)
        self.assertEqual(g['cm1_per_conv'], 12.5)
        self.assertEqual(g['paid_sis_pct'], 50)
        self.assertIsNone(b['paid_sis_pct'])

    def test_numpy_source_types_and_zero_activity_are_supported(self):
        source = {key: np.float64(value) for key, value in self.source.items()}
        source['paid_clicks_g'] = np.int64(1200)
        self.assertEqual(source_platforms(source)['google']['paid_clicks'], 1200)
        p = source_platforms({key: 0 for key in self.source})
        self.assertEqual(p['bing']['spend'], 0)
        self.assertIsNone(p['bing']['roi_pct'])
        self.assertIsNone(p['google']['paid_cvr_pct'])

    def test_all_twelve_ty_ly_weeks_reach_ce_drawer(self):
        weeks = config.week_starts(dt.date(2026, 9, 6), config.WEEKS_BACK)
        ty = [{**_weekly_metrics(None, self.source), 'week': config.iso(w)} for w in weeks]
        ly_source = {key: value/2 for key, value in self.source.items()}
        ly = [{**_weekly_metrics(None, ly_source), 'week': config.iso(w)} for w in weeks]
        row = next(r for r in _ce_drawer_metrics(ty, ly)['paid'] if r['key'] == 'cm1')
        parts = {r['key']: r for r in row['breakdown']}
        self.assertEqual(len(parts['cm1:google']['series']), 12)
        self.assertEqual(parts['cm1:google']['w0'], 150)
        self.assertEqual(parts['cm1:google']['wm1'], 150)
        self.assertEqual(parts['cm1:google']['ly_w0'], 75)
        self.assertEqual(parts['cm1:bing']['w0'], 90)
        self.assertTrue(all(p['ly'] == 45 for p in parts['cm1:bing']['series']))

    def test_aggregate_attachment_preserves_core_and_missing_constituents(self):
        row = {'revenue': 123, 'roi_pct': 456}
        attach_aggregate_platforms(row, pd.DataFrame([self.source, self.source]))
        self.assertEqual((row['revenue'], row['roi_pct']), (123, 456))
        self.assertEqual(row['paid_platforms']['google']['spend'], 240)
        self.assertAlmostEqual(row['paid_platforms']['google']['roi_pct'], 150/132*100)
        source = {**self.source, 'offline_revenue_g': None}
        row = {}
        attach_aggregate_platforms(row, pd.DataFrame([self.source, source]))
        self.assertIsNone(row['paid_platforms']['google']['paid_revenue'])
        self.assertIn('offline_revenue_g', row['paid_platform_missing_fields'])

    def test_missing_source_fields_remain_null_and_are_flagged(self):
        for field in ('coupon_wallet_g', 'offline_revenue_g', 'sis_impr'):
            source = copy.deepcopy(self.source)
            source[field] = None
            row = _weekly_metrics(None, source)
            self.assertIn(field, row['paid_platform_missing_fields'])
            self.assertIn(field, missing_source_fields(source))
        source = copy.deepcopy(self.source)
        del source['coupon_wallet_g']
        self.assertIn('coupon_wallet_g', _weekly_metrics(None, source)['paid_platform_missing_fields'])

    def test_queries_all_markets_and_global_ty_ly_keep_fields_scope_and_dates(self):
        w0 = dt.date(2026, 9, 6)
        start = config.week_starts(w0, config.WEEKS_BACK)[0]
        end = w0 + dt.timedelta(days=6)
        periods = [(start, end), (start-dt.timedelta(days=config.YOY_LAG_DAYS),
                                  end-dt.timedelta(days=config.YOY_LAG_DAYS)+dt.timedelta(days=28))]
        frame = pd.DataFrame([self.source])
        for market in [*config.MARKETS.values(), None]:
            for lo, hi in periods:
                with self.subTest(market=market, start=lo), patch.object(fetch, 'query_df', return_value=frame) as query:
                    self.assertIs(fetch.ce_weekly_ads(market, lo, hi), frame)
                    sql, label, params = query.call_args.args
                    aliases = set(re.findall(r'\bAS\s+(\w+)', sql, re.I))
                    self.assertTrue((set(SOURCE_FIELDS.values()) | set(GOOGLE_SOURCE_FIELDS.values())) <= aliases)
                    self.assertIn("ad_platform IN ('Google Ads', 'Microsoft Ads')", sql)
                    self.assertIn("campaign_advertising_channel_type = 'SEARCH'", sql)
                    self.assertIn('WEEK(SUNDAY)', sql)
                    self.assertEqual((params['start'], params['end']), (config.iso(lo), config.iso(hi)))
                    self.assertEqual('market' in params, market is not None)
                    self.assertEqual('campaign_target_business_market = @market' in sql, market is not None)

    def test_missing_query_values_are_logged_without_mutation(self):
        frame = pd.DataFrame([{**self.source, 'offline_revenue_g': None}])
        before = frame.copy(deep=True)
        with patch.object(fetch, 'query_df', return_value=frame), self.assertLogs('fetch', level='WARNING') as messages:
            result = fetch.ce_weekly_ads(None, dt.date(2025, 8, 31), dt.date(2025, 9, 6))
        pd.testing.assert_frame_equal(result, before)
        self.assertIn('offline_revenue_g', '\n'.join(messages.output))

    def test_existing_weekly_metrics_identical_to_committed_producer(self):
        old = subprocess.check_output(['git', 'show', 'fdf874c:scripts/weekly_report/build_snapshot.py'],
                                      cwd=ROOT, text=True)
        function = next(n for n in ast.parse(old).body if isinstance(n, ast.FunctionDef) and n.name == '_weekly_metrics')
        namespace = dict(vars(build_snapshot))
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<committed-producer>', 'exec'), namespace)
        for source in (self.source, {k: 0 for k in self.source},
                       {**self.source, 'offline_revenue_g': None}, None):
            with self.subTest(source=source):
                before = namespace['_weekly_metrics'](None, source)
                after = _weekly_metrics(None, source)
                for row in (before, after):
                    row.pop('paid_platforms', None)
                    row.pop('paid_platform_missing_fields', None)
                self.assertEqual(before, after)

    def test_metric_sql_is_unchanged_from_committed_query(self):
        old = subprocess.check_output(['git', 'show', 'fdf874c:scripts/weekly_report/fetch.py'],
                                      cwd=ROOT, text=True)
        function = next(n for n in ast.parse(old).body if isinstance(n, ast.FunctionDef) and n.name == 'ce_weekly_ads')
        namespace = dict(vars(fetch))
        with patch.object(fetch, 'query_df', return_value=pd.DataFrame([self.source])) as query:
            namespace['query_df'] = query
            exec(compile(ast.Module(body=[function], type_ignores=[]), '<committed-query>', 'exec'), namespace)
            args = ('North America', dt.date(2026, 8, 30), dt.date(2026, 9, 5))
            namespace['ce_weekly_ads'](*args)
            before = query.call_args
            fetch.ce_weekly_ads(*args)
            self.assertEqual(query.call_args, before)


if __name__ == '__main__':
    unittest.main()
