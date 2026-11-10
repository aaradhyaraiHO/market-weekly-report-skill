"""Independent Omni spend coverage, exercised through the actual SQL producers."""
import datetime as dt
from pathlib import Path
import re
import sqlite3
import sys
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/weekly_report'))
import build_snapshot
import fetch
import seasonality
import source_guard


# Independent expected source contract, verified against Omni on 10 November.
# Do not derive this from a producer's component list: that missed the omission.
OMNI_AD_COLUMNS = (
    'sum_google_ads_spend', 'sum_google_split_ads_spend', 'sum_pmax_ads_spend',
    'sum_travel_ads_spend', 'sum_google_remarketing_ads_spend', 'sum_google_brand_ads_spend',
    'sum_microsoft_ads_spend', 'sum_microsoft_split_ads_spend',
    'sum_microsoft_brand_ads_spend', 'sum_microsoft_remarketing_ads_spend',
    'sum_facebook_ads_spend', 'sum_facebook_split_ads_spend',
    'sum_facebook_remarketing_ads_spend', 'sum_apple_ads_spend',
    'sum_criteo_remarketing_ads_spend',
)


def ad_sum_expression(sql):
    """Extract the balanced SUM expression that starts with Google spend."""
    at = sql.index('sum_google_ads_spend')
    begin = sql.rfind('SUM(', 0, at)
    depth = 0
    for end in range(begin + 3, len(sql)):
        depth += (sql[end] == '(') - (sql[end] == ')')
        if depth == 0:
            return sql[begin:end + 1]
    raise AssertionError('No complete ad-spend SUM')


def execute_cost(expression, brand=25, remarketing=10):
    """Evaluate actual producer arithmetic; NULLs use the real SQL semantics."""
    with sqlite3.connect(':memory:') as db:
        db.execute('CREATE TABLE costs (' + ', '.join(c + ' REAL' for c in OMNI_AD_COLUMNS) + ')')
        current = dict.fromkeys(OMNI_AD_COLUMNS, 0)
        current.update(sum_google_ads_spend=100, sum_microsoft_ads_spend=50,
                       sum_microsoft_brand_ads_spend=brand,
                       sum_microsoft_remarketing_ads_spend=remarketing)
        historical = dict.fromkeys(OMNI_AD_COLUMNS, 0)
        historical.update(sum_google_ads_spend=20, sum_microsoft_ads_spend=30,
                          sum_microsoft_brand_ads_spend=None,
                          sum_microsoft_remarketing_ads_spend=None)
        db.executemany('INSERT INTO costs VALUES (' + ','.join('?' for _ in OMNI_AD_COLUMNS) + ')',
                       [tuple(r[c] for c in OMNI_AD_COLUMNS) for r in (current, historical)])
        return db.execute('SELECT ' + expression + ' FROM costs').fetchone()[0]


class MarketingCostTests(unittest.TestCase):
    def producer_sql(self):
        start, end = dt.date(2026, 11, 1), dt.date(2026, 11, 7)
        queries = []
        for market in (None, 'North America'):
            with patch.object(fetch, 'query_df', return_value=pd.DataFrame()) as q:
                fetch.ce_weekly_business(market, start, end)
            queries.append(q.call_args.args[0])
            params = q.call_args.args[2]
            self.assertEqual(params.get('market'), market)
            self.assertEqual(params['start'], '2026-11-01')
            self.assertEqual(params['end'], '2026-11-07')
        with patch.object(seasonality, 'query_df', return_value=pd.DataFrame()) as q:
            seasonality._fetch_weekly_cm2('North America', ['example'], start, end)
        queries.append(q.call_args.args[0])
        with patch.object(source_guard, 'query_df', return_value=pd.DataFrame()) as q:
            source_guard.read_daily('2026-11-01')
        queries.append(q.call_args.args[0])
        return queries

    def test_all_cost_producers_include_each_omni_platform_exactly_once(self):
        for sql in self.producer_sql():
            expression = ad_sum_expression(sql)
            with self.subTest(expression=expression):
                self.assertCountEqual(re.findall(r'\bsum_\w+_spend\b', expression), OMNI_AD_COLUMNS)
                # Includes brand AND remarketing; historical NULLs must not erase
                # the $50 of other historical spend in the second input row.
                self.assertEqual(execute_cost(expression), 235)
                self.assertEqual(execute_cost(expression, brand=None, remarketing=None), 200)

    def test_corrected_overall_cost_does_not_change_paid_search_metrics(self):
        paid = pd.Series(dict(spend=100, cm1=150, coupon_wallet=5, conversions=10,
                              paid_clicks=200, offline_revenue=170))
        before = pd.Series(dict(revenue=300, orders=10, gbv=1000,
                                ad_spend_total=200, direct_costs=20))
        after = before.copy()
        after['ad_spend_total'] = execute_cost(ad_sum_expression(self.producer_sql()[0]))
        old = build_snapshot._weekly_metrics(before, paid)
        new = build_snapshot._weekly_metrics(after, paid)
        self.assertEqual(new['gross_marketing_cost'], 235)
        self.assertEqual(new['roi1_pct'], round(100 * 280 / 235, 2))
        self.assertEqual(new['revenue'], old['revenue'])
        self.assertEqual(new['cm1_business'], old['cm1_business'])
        for field in ('roi_pct', 'spend', 'paid_clicks', 'paid_cvr_pct', 'paid_rpc', 'paid_cm2'):
            self.assertEqual(new[field], old[field], field)

    def test_guard_rejects_a_snapshot_that_omits_brand_cost_in_any_comparison(self):
        start = dt.date(2026, 11, 1)
        for slug, market in (('headout', 'Headout'), ('north_america', 'North America')):
            rows, weekly, ly = [], [], []
            for offset in (0, -7, -364):
                day = start + dt.timedelta(days=offset)
                rows.append(dict(report_date=day, business_market='North America',
                                 revenue=300, cm1_business=280, gross_marketing_cost=235))
                fact = dict(week=str(start if offset == -364 else day), revenue=300,
                            cm1_business=280, gross_marketing_cost=200, roi1_pct=140)
                (ly if offset == -364 else weekly).append(fact)
            snapshot = dict(meta=dict(market_slug=slug, market=market, week_start=str(start)),
                            market_summary=dict(weekly=weekly, weekly_ly=ly))
            errors, _ = source_guard.reconcile(snapshot, rows)
            for period in ('W0', 'W-1', 'LY'):
                self.assertTrue(any(period + ': gross_marketing_cost' in e for e in errors))
            for fact in weekly + ly:
                fact.update(gross_marketing_cost=235, roi1_pct=round(100 * 280 / 235, 2))
            self.assertFalse(source_guard.reconcile(snapshot, rows)[0])


if __name__ == '__main__':
    unittest.main()
