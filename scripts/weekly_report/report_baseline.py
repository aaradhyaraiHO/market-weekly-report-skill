"""Retain a common verified-complete production receipt for the next cadence.

A provider acknowledgement alone cannot produce this receipt: exact artifact,
fresh signed-in proof and the current canonical deployment must all agree.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from contextlib import nullcontext
import report_storage
from report_runtime import atomic
from release_integrity import files, verify_browser, verify_artifact
from vercel_upload import Client, toolchain, check_project, require_parent_lock, CANONICAL


def finalize(notebook,base,manifest_path,proof_path,transport_path,client,*,cadence='weekly',validator=None):
    notebook,base,manifest_path,proof_path,transport_path=map(report_storage.no_symlinks,
        (notebook,base,manifest_path,proof_path,transport_path))
    manifest=json.loads(manifest_path.read_text()); proof=json.loads(proof_path.read_text())
    transport=json.loads(transport_path.read_text())
    check_project(notebook)
    if transport.get('status')!='ready_for_browser_verification':raise ValueError('Deployment not observed ready')
    if transport.get('manifest_sha256')!=hashlib.sha256(manifest_path.read_bytes()).hexdigest():raise ValueError('Transport artifact mismatch')
    if transport.get('notebook') != str(notebook) or transport.get('base_notebook') != str(base):
        raise ValueError('Transport notebook identity mismatch')
    if proof.get('status')!='verified' or proof.get('method')!='signed-in-browser':raise ValueError('Fresh signed-in proof required')
    if cadence=='weekly':
        if verify_artifact(base,notebook,manifest['week'])!=manifest:raise ValueError('Weekly artifact changed')
        validated=verify_browser(manifest,proof['observations'])
    else:
        if validator is None:raise ValueError('Monthly exact artifact/proof validator required')
        validated=validator(notebook,base,manifest,proof)
    if validated.get('manifest_sha256') != proof.get('manifest_sha256'):raise ValueError('Browser proof identity mismatch')
    canonical=client.inspect(CANONICAL)
    if canonical.get('id') != transport.get('deployment_id') or canonical.get('readyState')!='READY':
        raise ValueError('Canonical production advanced or is not ready')
    retained=files(notebook)
    receipt_path=report_storage.no_symlinks(notebook.parent/'deployment_receipt.json')
    receipt={'schema':'report-production-baseline/v1','status':'verified',
        'deployment_id':canonical['id'],'deployment_url':canonical.get('url'),
        'notebook':str(notebook),'base_notebook':str(base),'cadence':cadence,
        'period':manifest.get('week',manifest.get('month')),'files':retained,
        'artifact':str(manifest_path),'live_verification':str(proof_path),
        'transport':str(transport_path),'verified_at':dt.datetime.now(dt.timezone.utc).isoformat()}
    if receipt_path.exists():
        existing=json.loads(receipt_path.read_text())
        if existing.get('deployment_id') != receipt['deployment_id'] or existing.get('files') != retained:
            raise ValueError('Conflicting retained baseline receipt; never overwrite')
    atomic(receipt_path,receipt)
    atomic(report_storage.STATE/'current_production.json',{'schema':'report-production-pointer/v1',
        'deployment_id':canonical['id'],'notebook':str(notebook),'receipt':str(receipt_path),
        'verified_at':receipt['verified_at']})
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('notebook','base-notebook','manifest','proof','transport'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--under-release-lock',action='store_true');args=p.parse_args()
    node,vendor=toolchain()
    if args.under_release_lock:require_parent_lock()
    guard=nullcontext() if args.under_release_lock else report_storage.release_guard('retain-verified-baseline',[args.notebook,args.base_notebook],baseline=args.base_notebook)
    with guard:
        receipt=finalize(args.notebook,args.base_notebook,args.manifest,args.proof,args.transport,Client(node,vendor))
    print(json.dumps({'status':receipt['status'],'deployment_id':receipt['deployment_id']}))
if __name__=='__main__':main()
