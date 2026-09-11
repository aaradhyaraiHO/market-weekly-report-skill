import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'alert' / 'v2'))
import safe_delivery as delivery


def block(text):
    return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': text}}


def market():
    payload = {'messages': [{'blocks': [block('summary')], 'threads': []},
                            {'blocks': [block('movers')], 'threads': [{'$rca': '12'}]}],
               '_rca': {'week_start': '2026-08-30', 'ce_ids': ['12']}}
    return delivery.compile_market('csee', '2026-08-30', 'C1', payload,
                                   {'12': {'blocks': [block('CE 12 diagnosis')]}})


class FakeSlack:
    def __init__(self):
        self.rows = {None: []}
        self.posts = 0
        self.crash_after_send = False
        self.fail_before_send = False

    def messages(self, channel, week, parent=None):
        return copy.deepcopy(self.rows.get(parent, []))

    def post(self, channel, op, parent=None):
        if self.fail_before_send:
            raise TimeoutError('ambiguous transport failure')
        self.posts += 1
        ts = str(self.posts)
        self.rows.setdefault(parent, []).append({**copy.deepcopy(op), 'ts': ts})
        if self.crash_after_send:
            self.crash_after_send = False
            raise TimeoutError('response lost')
        return ts


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = self.root / 'ledger.json'
        self.state = self.root / 'state'
        self.slack = FakeSlack()
        self.market = market()

    def run_delivery(self, **kwargs):
        return delivery.deliver_market(self.market, self.slack, self.ledger, self.state, **kwargs)

    def test_success_and_retry_are_duplicate_free(self):
        self.assertEqual(self.run_delivery()['status'], 'verified')
        self.run_delivery()
        self.assertEqual(self.slack.posts, 3)
        entry = json.loads(self.ledger.read_text())['2026-08-30']['csee']
        self.assertEqual((entry['msg1_ts'], entry['msg2_ts']), ('1', '2'))

    def test_lost_ack_is_reconciled_without_repost(self):
        self.slack.crash_after_send = True
        with self.assertRaises(TimeoutError):
            self.run_delivery()
        self.run_delivery()
        self.assertEqual(self.slack.posts, 3)

    def test_ambiguous_absence_is_not_permission_to_resend(self):
        self.slack.fail_before_send = True
        with self.assertRaises(TimeoutError):
            self.run_delivery()
        self.slack.fail_before_send = False
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.run_delivery()
        self.assertEqual(self.slack.posts, 0)

    def test_legacy_missing_parent_blocks_before_any_reply(self):
        self.slack.rows[None] = [{**self.market['operations'][0], 'ts': '1'}]
        self.ledger.write_text(json.dumps({'2026-08-30': {'csee': {'channel': 'C1', 'msg1_ts': '1'}}}))
        with self.assertRaisesRegex(ValueError, 'legacy parents'):
            self.run_delivery()
        self.assertEqual(self.slack.posts, 0)

    def test_corrupt_ledger_fails_closed(self):
        self.ledger.write_text('{bad')
        with self.assertRaises(ValueError):
            self.run_delivery()
        self.assertEqual(self.slack.posts, 0)

    def test_frozen_plan_drift_is_blocked(self):
        self.run_delivery()
        self.market['operations'][0]['text'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'plan changed'):
            self.run_delivery()
        self.assertEqual(self.slack.posts, 3)

    def test_deleted_reply_is_not_reposted(self):
        self.run_delivery()
        self.slack.rows['2'] = []
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            self.run_delivery()
        self.assertEqual(self.slack.posts, 3)

    def test_verify_only_never_sends(self):
        with self.assertRaises(ValueError):
            self.run_delivery(verify_only=True)
        self.assertEqual(self.slack.posts, 0)
        self.assertFalse(self.ledger.exists())

    def test_missing_rca_rejected_before_delivery(self):
        payload = {'messages': [{'blocks': [block('a')]}, {'blocks': [block('b')], 'threads': [{'$rca': '12'}]}],
                   '_rca': {'week_start': '2026-08-30', 'ce_ids': ['12']}}
        with self.assertRaisesRegex(ValueError, 'missing/failed RCA'):
            delivery.compile_market('csee', '2026-08-30', 'C1', payload, {})

    def test_other_history_preserved(self):
        old = {'2026-08-23': {'headout': {'msg1_ts': 'old', 'custom': 'keep'}}}
        self.ledger.write_text(json.dumps(old))
        self.run_delivery()
        self.assertEqual(json.loads(self.ledger.read_text())['2026-08-23'], old['2026-08-23'])
