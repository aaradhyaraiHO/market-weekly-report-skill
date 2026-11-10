"""Explicitly approved in-place correction of a completed frozen V2 delivery.

No posting/deletion API. Original bundles, ledgers and delivery journals remain
immutable. A separate write-ahead journal retains preimages and exact target TSs.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys

from safe_delivery import Slack, atomic_json, digest, locked, matches, read_json, slack_text, validate_bundle


def message_matches(expected, actual):
    return (matches(expected['blocks'], actual.get('blocks'))
            and slack_text(expected.get('text','')) == slack_text(actual.get('text','')))


def freeze_plan(original, corrected, state_dir, slack):
    validate_bundle(original); validate_bundle(corrected)
    if original['week'] != corrected['week']:
        raise ValueError('Correction week differs')
    actor=slack.call('auth.test',{})['user_id']
    old={m['slug']:m for m in original['markets']}; operations=[]
    for new in corrected['markets']:
        prior=old[new['slug']]
        if prior['channel'] != new['channel']:
            raise ValueError('Correction channel differs')
        journal=read_json(state_dir/f"{new['week']}_{new['slug']}.json",{})
        if journal.get('status')!='verified' or journal.get('plan_hash')!=digest(prior):
            raise ValueError('Original delivery is not complete/verified')
        old_ops={o['key']:o for o in prior['operations']}
        new_ops={o['key']:o for o in new['operations']}
        if old_ops.keys()!=new_ops.keys():
            raise ValueError(f"{new['slug']}: operation slots changed; no new posts or implicit reply remapping")
        if any(old_ops[k]['anchor']!=new_ops[k]['anchor'] for k in old_ops):
            raise ValueError('Correction changed parent/reply anchors')
        cache={};anchors={}
        for op in prior['operations']:
            key=op['key'];state=journal['operations'].get(key,{})
            ts=state.get('ts')
            if not ts or state.get('status')!='acknowledged':
                raise ValueError('Original operation has no acknowledged timestamp')
            parent=anchors.get(op['anchor']) if op['anchor'] else None
            if op['anchor'] and not parent:
                raise ValueError('Unresolved original parent')
            if parent not in cache:
                cache[parent]=slack.messages(prior['channel'],prior['week'],parent)
            found=[m for m in cache[parent] if m.get('ts')==ts]
            if (len(found)!=1 or found[0].get('user')!=actor
                    or not matches(op['blocks'],found[0].get('blocks'))):
                raise ValueError(f"{new['slug']}/{key}: original message changed, missing, or different author")
            anchors[key]=ts
            operations.append(dict(market=new['slug'],week=new['week'],channel=new['channel'],
                key=key,ts=ts,parent=parent,actor=actor,
                before={'blocks':found[0]['blocks'],'text':found[0].get('text','')},
                after={'blocks':new_ops[key]['blocks'],'text':new_ops[key]['text']}))
    return {'schema':'weekly-v2-in-place-correction/v1','week':original['week'],
        'original_sha256':original['sha256'],'corrected_sha256':corrected['sha256'],
        'prepared_at':dt.datetime.now(dt.timezone.utc).isoformat(),'operations':operations}


def edit(plan, slack, journal_path, apply=False):
    plan_hash=digest(plan)
    journal=read_json(journal_path,{'plan_hash':plan_hash,'operations':{}})
    if journal.get('plan_hash')!=plan_hash:
        raise ValueError('Correction plan changed; preserve its journal')
    # Preflight every message before the first edit, including on a partial retry.
    cache={}; observed={}
    for op in plan['operations']:
        anchor=(op['channel'],op['parent'])
        if anchor not in cache:
            cache[anchor]=slack.messages(op['channel'],op['week'],op['parent'])
        found=[m for m in cache[anchor] if m.get('ts')==op['ts']]
        if len(found)!=1 or found[0].get('user')!=op['actor']:
            raise ValueError('Correction target missing/ambiguous/different author')
        current=found[0]
        duplicate_ids=[m for m in cache[anchor] if m.get('client_msg_id')
                       and m.get('client_msg_id')==current.get('client_msg_id')]
        if len(duplicate_ids)>1:
            raise ValueError('Duplicate original message identity; stop correction')
        if not any(message_matches(state,current) for state in (op['before'],op['after'])):
            raise ValueError('Concurrent/unexpected Slack edit; no writes permitted')
        observed[(op['market'],op['key'])]=current
    if not apply:
        return {'status':'ready','messages':len(plan['operations']),'new_posts':0}
    for op in plan['operations']:
        key=op['market']+'/'+op['key']; current=observed[(op['market'],op['key'])]
        if not message_matches(op['after'],current):
            journal['operations'][key]={'status':'updating','ts':op['ts']}
            atomic_json(journal_path,journal)
            # Lost acknowledgement stops. Next invocation reads the exact TS and
            # reconciles before deciding whether an idempotent update is needed.
            slack.call('chat.update',dict(channel=op['channel'],ts=op['ts'],**op['after']),write=True)
        journal['operations'][key]={'status':'acknowledged','ts':op['ts']}
        atomic_json(journal_path,journal)
    cache={}; counts={}
    for op in plan['operations']:
        anchor=(op['channel'],op['parent'])
        if anchor not in cache:
            cache[anchor]=slack.messages(op['channel'],op['week'],op['parent'])
        found=[m for m in cache[anchor] if m.get('ts')==op['ts']]
        if len(found)!=1 or not message_matches(op['after'],found[0]):
            raise ValueError('Final fresh correction read-back failed')
        counts.setdefault(op['market'],{'parents':0,'rca':0})['rca' if op['parent'] else 'parents']+=1
    journal.update(status='verified',verified_at=dt.datetime.now(dt.timezone.utc).isoformat(),
                   markets=counts,new_posts=0)
    atomic_json(journal_path,journal)
    return journal


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original',type=Path,required=True);p.add_argument('--corrected',type=Path,required=True)
    p.add_argument('--original-state',type=Path,required=True);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--journal',type=Path,required=True);p.add_argument('--artifact',type=Path,required=True)
    p.add_argument('--verified-release',type=Path,required=True);p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    old=json.loads(args.original.read_text());new=json.loads(args.corrected.read_text())
    validate_bundle(old);validate_bundle(new)
    artifact=json.loads(args.artifact.read_text());proof=json.loads(args.verified_release.read_text())
    if (proof.get('status')!='verified' or proof.get('week')!=new['week']
            or proof.get('manifest_sha256')!=hashlib.sha256(json.dumps(artifact,sort_keys=True).encode()).hexdigest()):
        raise ValueError('Corrected exact artifact not verified live')
    for m in new['markets']:
        if m.get('headline_sha256')!=artifact['headlines'].get(m['slug']):
            raise ValueError('Corrected alert/report mismatch')
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/weekly_report'))
    from release_integrity import verify_browser
    verify_browser(artifact,proof['observations'])
    token=os.environ.get('REVENUE_ALERT_SLACK_TOKEN')
    if not token:raise ValueError('Bot credential required')
    slack=Slack(token)
    ledger=Path(__file__).resolve().parents[1]/'posted_ledger.json'
    with locked(ledger.with_suffix('.lock')):
        if args.plan.exists():
            plan=json.loads(args.plan.read_text())
            if (plan.get('original_sha256')!=old['sha256'] or plan.get('corrected_sha256')!=new['sha256']):
                raise ValueError('Frozen correction plan/bundles differ')
        else:
            plan=freeze_plan(old,new,args.original_state,slack);atomic_json(args.plan,plan)
        print(json.dumps(edit(plan,slack,args.journal,args.apply)))

if __name__=='__main__':main()
