"""Realtime-source cutover: retain business contracts, not retired columns."""
import ast
import datetime as dt
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import config
import fetch
import verify_lambda_sources as verify_sources


class LambdaSourceContracts(unittest.TestCase):
    windows = (dt.date(2026, 10, 11), dt.date(2026, 10, 17),
               dt.date(2026, 10, 4), dt.date(2026, 10, 10),
               dt.date(2025, 10, 12), dt.date(2025, 10, 18))

    def capture(self, function, *args):
        with patch.object(fetch, 'query_df', return_value=pd.DataFrame()) as query:
            function(*args)
        return query.call_args.args

    def test_only_source_constants_change_not_limits_or_metric_bases(self):
        self.assertTrue(config.FCT_ORDERS.endswith('.fct_orders_lambda`'))
        self.assertTrue(config.FCT_BOOKINGS.endswith('.fct_bookings_lambda`'))
        self.assertEqual(config.MAX_BYTES_BILLED, 80 * 1024 ** 3)
        self.assertEqual(config.REVENUE_COL, 'sum_revenue_predicted')
        self.assertEqual(config.YOY_LAG_DAYS, 364)
        self.assertEqual(config.WEEK_START_DAY, 'SUNDAY')

    def test_all_markets_and_global_preserve_date_and_filter_parameters(self):
        for market in [*config.MARKETS.values(), None]:
            for function in (fetch.ce_tgids, fetch.ce_variants, fetch.ce_leadtime,
                             fetch.ce_countries, fetch.ce_channels):
                with self.subTest(market=market, function=function.__name__):
                    sql, label, params = self.capture(function, market, *self.windows)
                    self.assertEqual(params['w0_s'], '2026-10-11')
                    self.assertEqual(params['wm1_s'], '2026-10-04')
                    self.assertEqual(params['ly_s'], '2025-10-12')
                    self.assertEqual('market' in params, market is not None)
                    self.assertEqual('= @market' in sql, market is not None)
                    self.assertNotIn('.fct_orders`', sql)
                    self.assertNotIn('.fct_bookings`', sql)

    def test_order_queries_change_only_source_identifier(self):
        old = subprocess.check_output(['git', 'show', '5973c1d:scripts/weekly_report/fetch.py'], cwd=ROOT, text=True)
        names = ('ce_weekly_actual_revenue', 'ce_tgids', 'ce_countries',
                 'ce_country_history', 'ce_channels', 'ce_channel_history')
        for name in names:
            function = next(n for n in ast.parse(old).body if isinstance(n, ast.FunctionDef) and n.name == name)
            namespace = dict(vars(fetch))
            with patch.object(fetch, 'query_df', return_value=pd.DataFrame()) as query:
                namespace['query_df'] = query
                exec(compile(ast.Module(body=[function], type_ignores=[]), '<old-query>', 'exec'), namespace)
                args = ('North America', *self.windows)
                if name == 'ce_weekly_actual_revenue':
                    args = ('North America', self.windows[0], self.windows[1])
                elif name.endswith('_history'):
                    args = ('North America', *self.windows[:2], *self.windows[4:], ['CE-1'])
                namespace[name](*args)
                before = query.call_args
                getattr(fetch, name)(*args)
                self.assertEqual(query.call_args, before, name)

    def test_booking_query_math_is_unchanged_after_source_projection(self):
        old = subprocess.check_output(['git', 'show', '5973c1d:scripts/weekly_report/fetch.py'], cwd=ROOT, text=True)
        for name in ('ce_tgid_leadtime', 'ce_leadtime', 'ce_leadtime_history', 'availability_signal'):
            function = next(n for n in ast.parse(old).body if isinstance(n, ast.FunctionDef) and n.name == name)
            namespace = dict(vars(fetch))
            with patch.object(fetch, 'query_df', return_value=pd.DataFrame()) as query:
                namespace['query_df'] = query
                exec(compile(ast.Module(body=[function], type_ignores=[]), '<old-query>', 'exec'), namespace)
                args = ('North America', *self.windows)
                if name == 'ce_tgid_leadtime':
                    args = ('North America', *self.windows[:4])
                elif name == 'ce_leadtime_history':
                    args = ('North America', *self.windows[:2], *self.windows[4:], ['CE-1'])
                elif name == 'availability_signal':
                    args = (['CE-1'], self.windows[2], *self.windows[:2])
                namespace[name](*args)
                before = query.call_args.args
                getattr(fetch, name)(*args)
                sql, label, params = query.call_args.args
                self.assertEqual(sql.replace(fetch._bookings_with_order_dimensions(), config.FCT_BOOKINGS), before[0], name)
                self.assertEqual((label, params), before[1:], name)

    def test_read_only_verifier_covers_all_markets_and_caps_every_query(self):
        rows = verify_sources.queries('2026-10-18')
        self.assertEqual(len(rows), 199)
        self.assertEqual({r['params'].get('market') for r in rows}, {*config.MARKETS.values(), None})
        job = verify_sources.job_config({}, True)
        self.assertTrue(job.dry_run)
        self.assertEqual(job.maximum_bytes_billed, 80 * 1024 ** 3)

    def test_verifier_never_treats_absent_groups_or_null_facts_as_zero(self):
        a = pd.DataFrame([{'ce': 'A', 'rev': 0}, {'ce': 'B', 'rev': None}])
        b = pd.DataFrame([{'ce': 'A', 'rev': 0}])
        result = verify_sources.aggregate_check(a, b, ['ce'], {'rev': 'rev'}, 'missing')
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['mismatch_count'], 1)
        result = verify_sources.aggregate_check(a, a, ['ce'], {'rev': 'rev'}, 'null')
        self.assertEqual(result['status'], 'passed_with_source_gaps')
        self.assertEqual(result['unavailable_count'], 1)
        self.assertNotEqual(result['status'], 'passed')
        nonzero = pd.DataFrame([{'ce': 'B', 'rev': 10}])
        null = pd.DataFrame([{'ce': 'B', 'rev': None}])
        self.assertEqual(verify_sources.aggregate_check(nonzero, null, ['ce'], {'rev': 'rev'}, 'partial')['status'], 'failed')
        zero = pd.DataFrame([{'ce': 'B', 'rev': 0}])
        self.assertEqual(verify_sources.aggregate_check(zero, null, ['ce'], {'rev': 'rev'}, 'legacy_zero')['status'], 'passed_with_source_gaps')

    def test_bookings_use_order_dimensions_without_new_status_or_economic_rules(self):
        sql = fetch._bookings_with_order_dimensions()
        self.assertIn('LEFT JOIN ' + config.FCT_ORDERS + ' o USING (order_id)', sql)
        self.assertIn('o.combined_entity_id, o.business_market, o.experience_id', sql)
        self.assertIn('b.price_net_usd, b.price_payable_usd', sql)
        self.assertIn("DATE(b.created_at, 'America/New_York') AS date_created_at_et", sql)
        self.assertIn("b.booking_status != 'Uncaptured' OR b.booking_status IS NULL", sql)
        self.assertNotIn("'Dummy'", sql)  # Legacy bookings did not exclude Dummy here.
        self.assertNotIn('ROW_NUMBER', sql)
        self.assertNotIn('DISTINCT', sql)

    def test_booking_projection_executes_at_booking_grain_and_preserves_dst_boundary(self):
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.create_function('DATE', 2, lambda value, zone: dt.datetime.fromisoformat(value).astimezone(ZoneInfo(zone)).date().isoformat())
        db.executescript('''
            CREATE TABLE orders(order_id INTEGER PRIMARY KEY, combined_entity_id TEXT, business_market TEXT, experience_id TEXT);
            CREATE TABLE bookings(booking_id INTEGER PRIMARY KEY, order_id INTEGER, tour_id TEXT,
                lead_time_days INTEGER, price_net_usd REAL, price_payable_usd REAL, created_at TEXT, booking_status TEXT);
            INSERT INTO orders VALUES (10, 'CE-1', 'North America', 'TG-1');
            INSERT INTO bookings VALUES
                (1,10,'tour-a',0,20,50,'2026-10-11T03:59:59+00:00','Completed'),
                (2,10,'tour-b',2,30,70,'2026-10-11T04:00:00+00:00','Completed'),
                (3,10,'tour-a',3,40,90,'2026-11-01T03:59:59+00:00','Uncaptured'),
                (4,10,'tour-a',5,50,80,'2026-11-01T04:00:00+00:00',NULL),
                (5,999,'tour-c',7,60,100,'2026-11-02T04:59:59+00:00','Dummy');
        ''')
        with patch.object(config, 'FCT_ORDERS', 'orders'), patch.object(config, 'FCT_BOOKINGS', 'bookings'):
            rows = [dict(r) for r in db.execute('SELECT * FROM ' + fetch._bookings_with_order_dimensions() + ' ORDER BY booking_id')]
        self.assertEqual([r['booking_id'] for r in rows], [1, 2, 4, 5])
        self.assertEqual([r['date_created_at_et'] for r in rows], ['2026-10-10', '2026-10-11', '2026-11-01', '2026-11-01'])
        self.assertEqual(sum(r['price_net_usd'] for r in rows), 160)
        self.assertEqual([r['combined_entity_id'] for r in rows[:3]], ['CE-1'] * 3)
        self.assertIsNone(rows[-1]['combined_entity_id'])  # Missing dimensions are not guessed.
        db.close()

    def test_variants_keep_allocation_and_null_variant_bucket(self):
        sql, _, _ = self.capture(fetch.ce_variants, 'North America', *self.windows)
        self.assertIn("COALESCE(CAST(o.variant_id AS STRING), '__UNATTRIBUTED__')", sql)
        self.assertNotIn('b.variant_id', sql)
        self.assertNotIn('b.variant_name', sql)
        self.assertIn('CAST(b.experience_id AS STRING) = CAST(o.experience_id AS STRING)', sql)
        self.assertIn('FROM ' + config.FCT_ORDERS + ' o', sql)
        self.assertIn('LEFT JOIN ' + config.FCT_BOOKINGS + ' b ON b.order_id = o.order_id', sql)
        self.assertNotIn('booking_id IS NOT NULL', sql)
        self.assertIn('PARTITION BY o.order_id', sql)
        self.assertIn('COALESCE(payable_weight, SAFE_DIVIDE(1, booking_count))', sql)
        self.assertIn('order_credit', sql)
        self.assertIn("b.booking_status != 'Uncaptured' OR b.booking_status IS NULL", sql)

    def test_variant_sql_allocates_once_even_for_combos_zero_weights_and_missing_bookings(self):
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.create_function('SAFE_DIVIDE', 2, lambda a, b: a / b if a is not None and b else None)
        db.create_function('IF', 3, lambda condition, a, b: a if condition else b)
        class AnyValue:
            def __init__(self): self.value = None
            def step(self, value):
                if self.value is None: self.value = value
            def finalize(self): return self.value
        db.create_aggregate('ANY_VALUE', 1, AnyValue)
        db.executescript('''
            CREATE TABLE orders(order_id INTEGER PRIMARY KEY, combined_entity_id TEXT, experience_id TEXT,
                variant_id TEXT, variant_name TEXT, created_at TEXT, business_market TEXT,
                amount_revenue_usd REAL, order_value_usd REAL, order_status TEXT, user_type TEXT);
            CREATE TABLE bookings(booking_id INTEGER PRIMARY KEY, order_id INTEGER, lead_time_days INTEGER,
                price_payable_usd REAL, booking_status TEXT, experience_id TEXT);
            INSERT INTO orders VALUES
                (1,'CE-1','100','201','Combo','2026-10-11','North America',100,300,'Completed','Customer'),
                (2,'CE-1','100','202','Zero weights','2026-10-11','North America',30,60,'Completed','Customer'),
                (3,'CE-1','100','203','No booking','2026-10-11','North America',5,40,'Pending','Customer'),
                (4,'CE-1','100','204','Only uncaptured','2026-10-11','North America',0,58.25,'Cancelled','Customer'),
                (5,'CE-1','100',NULL,NULL,'2026-10-04','North America',10,50,'Completed','Customer'),
                (6,'CE-1','100','206','Last year','2025-10-12','North America',20,80,'Completed','Customer');
            INSERT INTO bookings VALUES
                (11,1,0,50,'Completed','100'), (12,1,2,50,'Completed','100'),
                (13,1,10,500,'Completed','999'),
                (21,2,3,0,'Completed','100'), (22,2,4,0,'Completed','100'),
                (41,4,1,100,'Uncaptured','100'), (51,5,1,50,'Completed','100'), (61,6,2,80,'Completed','100');
        ''')
        with patch.object(config, 'FCT_ORDERS', 'orders'), patch.object(config, 'FCT_BOOKINGS', 'bookings'):
            sql, _, params = self.capture(fetch.ce_variants, 'North America', *self.windows)
        rows = [dict(r) for r in db.execute(sql, params)]
        self.assertAlmostEqual(sum(r['rev'] for r in rows), 135)
        self.assertAlmostEqual(sum(r['gbv'] for r in rows), 458.25)
        self.assertAlmostEqual(sum(r['orders'] for r in rows), 4)
        self.assertAlmostEqual(sum(r['completed_gbv'] for r in rows), 360)
        self.assertAlmostEqual(sum(r['rev_wm1'] for r in rows), 10)
        self.assertAlmostEqual(sum(r['orders_ly'] for r in rows), 1)
        self.assertAlmostEqual(sum(r['rev_ly'] for r in rows), 20)
        by_name = {r['variant_name']: r for r in rows}
        self.assertEqual(by_name['Combo']['lt_0d'], .5)
        self.assertEqual(by_name['Combo']['lt_12d'], .5)
        for name in ('No booking', 'Only uncaptured'):
            self.assertIsNone(by_name[name]['lt_0d'])
            self.assertIsNone(by_name[name]['lt_12d'])
        self.assertIn('Unattributed variant', by_name)
        db.close()

    def test_history_keeps_twelve_week_window_and_364_day_alignment(self):
        start = self.windows[0] - dt.timedelta(weeks=11)
        ly_start = start - dt.timedelta(days=364)
        sql, _, params = self.capture(fetch.ce_leadtime_history, None, start, self.windows[1], ly_start, self.windows[5], ['CE-1'])
        self.assertIn('INTERVAL 364 DAY', sql)
        self.assertIn('WEEK(SUNDAY)', sql)
        self.assertIn("DATE(b.created_at, 'America/New_York')", sql)
        self.assertEqual(params['start'], '2026-07-26')
        self.assertEqual(params['ly_start'], '2025-07-27')
        self.assertEqual(params['ce_ids'], ['CE-1'])

    def test_unused_google_helper_has_no_retired_scd_predicate(self):
        sql, _, _ = self.capture(fetch.ce_daily_orders_google, None, *self.windows[:2])
        self.assertNotIn('valid_to_timestamp', sql)
        self.assertIn(config.FCT_ORDERS, sql)
        self.assertIn("ad_network = 'Google: Search'", sql)

    def test_availability_uses_joined_ce_dimension(self):
        sql, _, params = self.capture(fetch.availability_signal, ['CE-1'], self.windows[2], *self.windows[:2])
        self.assertIn('o.combined_entity_id', sql)
        self.assertIn('LEFT JOIN ' + config.FCT_ORDERS, sql)
        self.assertEqual(params['ce_ids'], ['CE-1'])


if __name__ == '__main__':
    unittest.main()
