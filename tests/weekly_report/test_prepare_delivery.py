import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'alert' / 'v2'))
import prepare_delivery as prepare


class PreparationTests(unittest.TestCase):
    def test_current_bigquery_byte_limit_messages_split(self):
        for error in ('Query exceeded limit for bytes billed: 85899345920. 160755089408 or higher required.',
                      'reason: bytesBilledLimitExceeded', 'maximum_bytes_billed exceeded', 'bytes billed limit exceeded'):
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory:
                def run(cmd, **kwargs):
                    self.assertNotIn('--maximum-bytes-billed', cmd)
                    ids = cmd[cmd.index('--ce-ids') + 1].split(',')
                    if len(ids) > 1:
                        return Mock(returncode=1, stderr=error)
                    Path(cmd[-1]).write_text(json.dumps({ids[0]: {'blocks': ['evidence']}}))
                    return Mock(returncode=0)
                with patch.object(prepare.subprocess, 'run', side_effect=run) as calls:
                    result = prepare.query_rca(['1', '2', '3'], '2026-09-27', '2026-10-03', Path(directory) / 'rca.json')
                self.assertEqual(set(result), {'1', '2', '3'})
                self.assertEqual(calls.call_count, 5)

    def test_current_single_ce_byte_cap_stops_without_retry(self):
        with patch.object(prepare.subprocess, 'run', return_value=Mock(returncode=1, stderr='reason: bytesBilledLimitExceeded')) as calls:
            with self.assertRaisesRegex(RuntimeError, 'no parent alerts'):
                prepare.query_rca(['1'], '2026-09-27', '2026-10-03', Path('/unused'))
        self.assertEqual(calls.call_count, 1)

    def test_byte_cap_splits_without_raising_ceiling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rca.json'
            def run(cmd, **kwargs):
                ids = cmd[cmd.index('--ce-ids') + 1].split(',')
                if len(ids) > 1:
                    return Mock(returncode=1, stderr='maximum bytes billed exceeded')
                Path(cmd[-1]).write_text(json.dumps({ids[0]: {'blocks': ['evidence']}}))
                return Mock(returncode=0)
            with patch.object(prepare.subprocess, 'run', side_effect=run) as calls:
                result = prepare.query_rca(['1', '2'], '2026-08-30', '2026-09-05', path)
            self.assertEqual(set(result), {'1', '2'})
            self.assertEqual(calls.call_count, 3)

    def test_other_query_failures_do_not_retry_or_skip(self):
        with patch.object(prepare.subprocess, 'run', return_value=Mock(returncode=1, stderr='permission denied')) as calls:
            with self.assertRaisesRegex(RuntimeError, 'no parent alerts'):
                prepare.query_rca(['1', '2'], '2026-08-30', '2026-09-05', Path('/unused'))
        self.assertEqual(calls.call_count, 1)

    def test_single_ce_cap_failure_is_explicit(self):
        with patch.object(prepare.subprocess, 'run', return_value=Mock(returncode=1, stderr='maximum bytes billed')):
            with self.assertRaisesRegex(RuntimeError, 'no parent alerts'):
                prepare.query_rca(['1'], '2026-08-30', '2026-09-05', Path('/unused'))

    def test_incomplete_week_fails_before_any_query(self):
        with patch.object(prepare.subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                prepare.prepare('2099-01-04', Path('/unused'), Path('/unused'), Path('/unused'))
        run.assert_not_called()
