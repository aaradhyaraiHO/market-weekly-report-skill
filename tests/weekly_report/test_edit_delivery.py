import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'alert/v2'))
import edit_delivery as e
from safe_delivery import digest

def blocks(text):return [{'type':'section','text':{'type':'mrkdwn','text':text}}]

class FakeSlack:
    def __init__(self):
        self.rows=[dict(ts='1',user='bot',blocks=blocks('bad value'),text='old'),
                   dict(ts='2',user='bot',blocks=blocks('other market'),text='old')]
        self.calls=[];self.fail_after_write=False
    def messages(self,channel,week,parent):return copy.deepcopy(self.rows)
    def call(self,method,payload,write=False):
        self.calls.append(method)
        if method=='auth.test':return {'user_id':'bot'}
        assert method=='chat.update'
        row=next(r for r in self.rows if r['ts']==payload['ts'])
        row.update(blocks=payload['blocks'],text=payload['text'])
        if self.fail_after_write:
            self.fail_after_write=False;raise TimeoutError('lost acknowledgement')
        return {'ok':True,'ts':row['ts']}

class CorrectionTests(unittest.TestCase):
    def plan(self):
        return dict(schema='weekly-v2-in-place-correction/v1',operations=[dict(market='headout',week='2026-11-01',
            channel='channel',key='msg1',ts='1',parent=None,actor='bot',
            before=dict(blocks=blocks('bad value'),text='old'),after=dict(blocks=blocks('verified value'),text='new'))])

    def test_dry_run_never_writes_and_real_edit_reads_back_same_timestamp(self):
        slack=FakeSlack()
        with tempfile.TemporaryDirectory() as tmp:
            journal=Path(tmp)/'edit.json'
            e.edit(self.plan(),slack,journal)
            self.assertFalse(slack.calls);self.assertFalse(journal.exists())
            result=e.edit(self.plan(),slack,journal,True)
            self.assertEqual(result['status'],'verified');self.assertEqual(result['new_posts'],0)
            self.assertEqual(slack.calls,['chat.update'])
            e.edit(self.plan(),slack,journal,True)
            self.assertEqual(slack.calls,['chat.update'])

    def test_lost_update_ack_is_reconciled_without_posting_or_duplicate_update(self):
        slack=FakeSlack();slack.fail_after_write=True
        with tempfile.TemporaryDirectory() as tmp:
            journal=Path(tmp)/'edit.json'
            with self.assertRaises(TimeoutError):e.edit(self.plan(),slack,journal,True)
            self.assertEqual(json.loads(journal.read_text())['operations']['headout/msg1']['status'],'updating')
            self.assertEqual(e.edit(self.plan(),slack,journal,True)['status'],'verified')
            self.assertEqual(slack.calls,['chat.update'])

    def test_any_concurrent_edit_or_wrong_author_blocks_every_write(self):
        for changed in (dict(blocks=blocks('human edited')),dict(user='different author')):
            slack=FakeSlack();slack.rows[1].update(changed)
            plan=self.plan();op=copy.deepcopy(plan['operations'][0]);op.update(ts='2',key='msg2')
            op['before']['blocks']=blocks('other market');plan['operations'].append(op)
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):e.edit(plan,slack,Path(tmp)/'j',True)
            self.assertFalse(slack.calls)

    def test_changed_correction_plan_cannot_reuse_an_existing_journal(self):
        slack=FakeSlack()
        with tempfile.TemporaryDirectory() as tmp:
            journal=Path(tmp)/'edit.json';plan=self.plan();e.edit(plan,slack,journal,True)
            plan['operations'][0]['after']['blocks']=blocks('unreviewed value')
            with self.assertRaisesRegex(ValueError,'plan changed'):e.edit(plan,slack,journal,True)

    def test_multiple_updates_have_bounded_spacing(self):
        slack=FakeSlack();plan=self.plan();op=copy.deepcopy(plan['operations'][0])
        op.update(ts='2',key='msg2');op['before']['blocks']=blocks('other market')
        plan['operations'].append(op);waits=[]
        with tempfile.TemporaryDirectory() as tmp:
            e.edit(plan,slack,Path(tmp)/'j',True,clock=lambda:0,sleep=waits.append)
        self.assertEqual(waits,[2]);self.assertEqual(slack.calls,['chat.update','chat.update'])

    def test_new_reply_slots_fail_closed_instead_of_posting(self):
        market=dict(slug='headout',week='2026-11-01',channel='channel',operations=[dict(key='msg1',anchor=None,blocks=blocks('bad value'))])
        old=dict(week='2026-11-01',markets=[market],sha256='old')
        new=copy.deepcopy(old);new['markets'][0]['operations'].append(dict(key='msg2',anchor=None,blocks=blocks('new')))
        slack=FakeSlack()
        with tempfile.TemporaryDirectory() as tmp,patch.object(e,'validate_bundle'):
            path=Path(tmp)/'2026-11-01_headout.json'
            path.write_text(json.dumps(dict(status='verified',plan_hash=digest(market))))
            with self.assertRaisesRegex(ValueError,'slots changed'):
                e.freeze_plan(old,new,Path(tmp),slack)
        self.assertNotIn('chat.update',slack.calls)

if __name__=='__main__':unittest.main()
