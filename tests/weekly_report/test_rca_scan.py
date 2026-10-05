import datetime as dt
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'alert'))
import rca_scan
import weekly_rca_helper as weekly


class RcaScanTests(unittest.TestCase):
    def test_ordinary_query_unchanged_and_permission_errors_not_retried(self):
        client = Mock()
        client.query.return_value.to_dataframe.return_value = 'frame'
        args = (client, 'original', ['1'], dt.date(2026, 9, 20), dt.date(2026, 10, 3), weekly._query_config, weekly._sql_quote)
        self.assertEqual(rca_scan.bounded_dataframe(*args), 'frame')
        self.assertEqual(client.query.call_count, 1)
        self.assertEqual(client.query.call_args.kwargs['job_config'].maximum_bytes_billed, 80 * 1024**3)
        client.reset_mock()
        client.query.side_effect = PermissionError('permission denied')
        with self.assertRaises(PermissionError):
            rca_scan.bounded_dataframe(*args)
        self.assertEqual(client.query.call_count, 1)

    def test_slices_keep_exact_sql_weekly_distinct_and_cap(self):
        start, end = dt.date(2026, 9, 20), dt.date(2026, 9, 21)
        sql = 'SELECT COUNT(DISTINCT user_id) FROM ' + rca_scan.SOURCE
        calls = []
        def query(text, job_config):
            calls.append((text, job_config))
            self.assertEqual(job_config.maximum_bytes_billed, 80 * 1024**3)
            if text == sql:
                raise RuntimeError('reason: bytesBilledLimitExceeded')
            if job_config.dry_run:
                both = "DATE('2026-09-20') AND DATE('2026-09-21')" in text
                return SimpleNamespace(total_bytes_processed=(81 if both else 40) * 1024**3)
            if text.startswith('SELECT DISTINCT'):
                return Mock(destination=SimpleNamespace(project='headout-analytics', dataset_id='_private', table_id='slice'+str(len(calls))), total_bytes_processed=1234)
            self.assertTrue(text.startswith('SELECT COUNT(DISTINCT user_id) FROM (SELECT * FROM '))
            self.assertIn(' UNION ALL ', text)
            return Mock(to_dataframe=Mock(return_value='combined'))
        result = rca_scan.bounded_dataframe(SimpleNamespace(query=query), sql, ["1049 - Dubai"], start, end, weekly._query_config, weekly._sql_quote)
        self.assertEqual(result, 'combined')
        actual = [text for text, cfg in calls if text.startswith('SELECT DISTINCT') and not cfg.dry_run]
        self.assertEqual(len(actual), 2)
        self.assertIn("DATE('2026-09-20') AND DATE('2026-09-20')", actual[0])
        self.assertIn("DATE('2026-09-21') AND DATE('2026-09-21')", actual[1])
        times = [text.split('FOR SYSTEM_TIME AS OF ')[1].split('\n')[0] for text in actual]
        self.assertEqual(times[0], times[1])
        self.assertIn("advertising_channel_type IS NULL", actual[0])
        self.assertIn("combined_entity_id IN ('1049 - Dubai')", actual[0])

    def test_single_day_above_cap_stops_without_source_execution(self):
        client = Mock()
        client.query.return_value.total_bytes_processed = 81 * 1024**3
        with self.assertRaisesRegex(ValueError, 'single-day source'):
            rca_scan.sliced_dataframe(client, 'SELECT * FROM '+rca_scan.SOURCE, ['1'], dt.date(2026,9,22), dt.date(2026,9,22), weekly._query_config, weekly._sql_quote)
        self.assertTrue(client.query.call_args.kwargs['job_config'].dry_run)
        self.assertEqual(client.query.call_count, 1)

    def test_daily_dedup_preserves_users_shared_across_dates_and_channels(self):
        # Repeated source rows and a user in two days/channels: daily counts
        # would overcount, whereas the retained rows + weekly DISTINCT do not.
        rows = [('20','u1','paid',True),('20','u1','paid',True),
                ('21','u1','organic',False),('21','u2','paid',True),
                ('21',None,'paid',True)]
        slices = [set(row for row in rows if row[0] == day) for day in ('20','21')]
        retained = [row for part in slices for row in part]
        def counts(source):
            return (len({r[1] for r in source if r[1] is not None}),
                    len({r[1] for r in source if r[1] is not None and r[2]=='paid'}),
                    len({r[1] for r in source if r[1] is not None and r[3]}))
        self.assertEqual(counts(rows), counts(retained))
        self.assertEqual(counts(retained), (2,2,2))

    def test_source_template_and_metric_formulas_are_unchanged(self):
        import subprocess
        for name in ('ce_revenue_cvr_drop_ids.sql', 'ce_revenue_cvr_drop_ids_ly_period.sql'):
            path = 'alert/sql/' + name
            root = Path(__file__).resolve().parents[2]
            self.assertEqual((root/path).read_bytes(), subprocess.check_output(['git','show','bb83301:'+path],cwd=root))


if __name__ == '__main__':
    unittest.main()
