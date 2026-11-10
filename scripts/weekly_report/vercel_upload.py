#!/usr/bin/env python3
"""Transport-only deployment of an already verified, immutable weekly package.

No generation, data queries, rendering, browser-auth bypass or Slack writes.
The narrowly adapted CLI is isolated; the global installation is read-only.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

import report_storage
from release_integrity import atomic_json, files, verify_artifact

ROOT = Path(__file__).resolve().parents[2]
VERSION = '52.0.0'
UPLOAD_FILE = 'dist/chunks/chunk-VPI2ZRPP.js'
UPLOAD_SHA256 = 'a1d6d81a8bf67304f1775956f6e4b25481bc583813d0a90876b1155f0b8f2340'
ADAPTED_SHA256 = 'ed31a4cdb63411711d47aef4f66a64683828f32839142b3c165a82e38128d2b4'
ADAPTER = 'weekly-upload-v1'
TEAM = 'headout'
CANONICAL = 'https://market-notebook.vercel.app'
PROJECT_ID = 'prj_BSPLExXUAkqYlGKYp4LYCH4vAak7'
ORG_ID = 'team_3ITtCVZrgEK9WCoyJE2qN1Dk'
RUNTIME = Path(__file__).with_name('vercel_upload_runtime.cjs')
TOOL_CACHE = ROOT / '.cache/vercel_upload'
# A complete preserved notebook is ~560 MiB compressed. On a slow Mac uplink
# a healthy transfer can exceed 30 minutes. Keep a finite overall budget without
# interrupting it prematurely; retries/identity reconciliation remain unchanged.
UPLOAD_TIMEOUT_SECONDS = 90 * 60


def sha(data):
    return hashlib.sha256(data).hexdigest()


def patched_upload(source):
    """Exact, version/hash-guarded adapter for the vendor upload client only."""
    if sha(source.encode()) != UPLOAD_SHA256:
        raise ValueError('Unreviewed Vercel upload client; stop before generation/deployment')
    stream = '''            const body = new import_stream.Readable();
            const originalRead = body.read.bind(body);
            body.read = function(...args) {
              const chunk = originalRead(...args);
              if (chunk) {
                uploadProgress.bytesUploaded += chunk.length;
                uploadProgress.emit("progress");
              }
              return chunk;
            };
            const chunkSize = 16384;
            for (let i = 0; i < data.length; i += chunkSize) {
              const chunk = data.slice(i, i + chunkSize);
              body.push(chunk);
            }
            body.push(null);'''
    changes = [
        ('return err.message.includes("ETIMEDOUT") ||',
         'return err.message.includes("VERCEL_UPLOAD_5XX") || err.message.includes("EPIPE") || err.message.includes("ETIMEDOUT") ||'),
        ('const semaphore = new import_async_sema.Sema(50, { capacity: 50 });',
         'const semaphore = new import_async_sema.Sema(2, { capacity: 2 });'),
        ('const chunkedTarBuffers = await (0, import_build_utils5.streamToBufferChunks)(tarStream);',
         'const chunkedTarBuffers = await (0, import_build_utils5.streamToBufferChunks)(tarStream, 8 * 1024 * 1024);'),
        ('retries: 5,\n            factor: 6,\n            minTimeout: 10',
         'retries: 3,\n            factor: 2,\n            minTimeout: 1000,\n            maxTimeout: 5000'),
        (stream, '            const body = data;'),
        ('              if (res.status === 200) {\n                debug(',
         '              if (res.status === 200) {\n                uploadProgress.bytesUploaded = data.length;\n                uploadProgress.emit("progress");\n                debug('),
        ('''                debug(`A server error occurred in upload request. Retrying...`);
                const { error } = await res.json();
                throw new import_errors3.DeploymentError(error);''',
         '''                debug(`A server error occurred in upload request. Retrying...`);
                await res.text();
                throw new Error(`VERCEL_UPLOAD_5XX: ${res.status}`);'''),
    ]
    for old, new in changes:
        if source.count(old) != 1:
            raise ValueError('Vercel upload adapter contract changed; refusing an approximate patch')
        source = source.replace(old, new)
    if sha(source.encode()) != ADAPTED_SHA256:
        raise ValueError('Adapted upload client differs from the live-tested transport')
    return source


def toolchain():
    cli = os.environ.get('WEEKLY_VERCEL_CLI') or shutil.which('vercel')
    if not cli:
        raise ValueError(f'Install reviewed Vercel CLI {VERSION} before the run')
    entry = Path(cli).resolve()
    vendor = entry.parent.parent
    package = json.loads((vendor / 'package.json').read_text())
    if package.get('version') != VERSION or entry != vendor / 'dist/vc.js':
        raise ValueError(f'Vercel CLI {VERSION} required; unreviewed versions fail closed')
    patched_upload((vendor / UPLOAD_FILE).read_text())
    candidates = [os.environ.get('WEEKLY_VERCEL_NODE'), '/usr/local/bin/node',
                  '/opt/homebrew/opt/node@24/bin/node', shutil.which('node')]
    for candidate in dict.fromkeys(x for x in candidates if x):
        try:
            info = subprocess.run([candidate, '-p',
                'JSON.stringify({major:process.versions.node.split(".")[0],hooks:typeof require("node:module").registerHooks})'],
                capture_output=True, text=True, check=True, timeout=10)
            parsed = json.loads(info.stdout)
            if parsed == {'major': '24', 'hooks': 'function'}:
                return Path(candidate).resolve(), vendor
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
    raise ValueError('Node 24 LTS with module hooks is required; no runtime is installed/changed automatically')


def check_project(notebook):
    report_storage.deployable(notebook)
    if any(os.environ.get(k) for k in ('VERCEL_PROJECT_ID', 'VERCEL_ORG_ID')):
        raise ValueError('Vercel project environment overrides must be unset')
    project = json.loads((notebook / '.vercel/project.json').read_text())
    if (project.get('projectId'), project.get('orgId'), project.get('projectName')) != (PROJECT_ID, ORG_ID, 'market-notebook'):
        raise ValueError('Notebook is not linked to the approved Headout market-notebook project')


def prepare_cli(vendor, cache=TOOL_CACHE):
    """Independent tool files only. Never copy/modify the notebook or global CLI."""
    cache = report_storage.no_symlinks(cache)
    expected = {'package.json': (vendor / 'package.json').read_bytes()}
    for path in sorted((vendor / 'dist').rglob('*')):
        if path.is_symlink():
            raise ValueError('Symlink inside vendor CLI distribution')
        if path.is_file():
            expected[path.relative_to(vendor).as_posix()] = path.read_bytes()
    expected[UPLOAD_FILE] = patched_upload(expected[UPLOAD_FILE].decode()).encode()
    manifest = {name: sha(data) for name, data in expected.items()}
    target = cache / f'{VERSION}-{ADAPTER}'
    if target.exists():
        actual = {}
        for path in target.rglob('*'):
            if path.is_symlink():
                raise ValueError('Symlink inside isolated CLI cache')
            if path.is_file():
                actual[path.relative_to(target).as_posix()] = sha(path.read_bytes())
        actual.pop('adapter.json', None)
        if actual != manifest:
            raise ValueError('Isolated CLI cache changed; preserve it and investigate')
        return target
    cache.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.prepare-', dir=cache))
    for name, data in expected.items():
        dest = staging / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    atomic_json(staging / 'adapter.json', {'adapter': ADAPTER, 'version': VERSION,
        'original_upload_sha256': UPLOAD_SHA256, 'files': manifest})
    staging.rename(target)
    return target


def deployment_reference(text):
    """Only a CLI-emitted deployment identity, never its suggested retry command."""
    try:
        value = json.loads(text)
        row = value.get('deployment', value)
        for key in ('id', 'uid', 'url'):
            ref = row.get(key)
            if isinstance(ref, str) and (re.fullmatch(r'dpl_[A-Za-z0-9]+', ref) or
                    re.fullmatch(r'(?:https://)?market-notebook-[a-z0-9]+-headout\.vercel\.app', ref)):
                return ref
    except (ValueError, AttributeError):
        pass
    refs = set(re.findall(r'https://market-notebook-[a-z0-9]+-headout\.vercel\.app\b', text))
    ids = set(re.findall(r'\bdpl_[A-Za-z0-9]+\b', text))
    if len(ids) == 1:
        return next(iter(ids))
    return next(iter(refs)) if not ids and len(refs) == 1 else None


class Client:
    def __init__(self, node, vendor):
        self.node, self.vendor = node, vendor

    def inspect(self, ref):
        for attempt in range(3):
            try:
                result = subprocess.run([str(self.node), str(self.vendor / 'dist/vc.js'), 'inspect', ref,
                    '--scope', TEAM, '--json'], capture_output=True, text=True, timeout=45)
                if result.returncode:
                    if re.search(r'ETIMEDOUT|EPIPE|ECONNRESET|ECONNREFUSED|ENOTFOUND|EAI_AGAIN|socket hang up|\b50[0-4]\b', result.stderr):
                        raise InspectionTransient('Transient Vercel inspection failure')
                    raise ValueError('Vercel inspection failed; check authentication/permissions/configuration')
                row = json.loads(result.stdout)
                if row.get('name') != 'market-notebook' or row.get('target') != 'production' or row.get('contextName') != TEAM:
                    raise ValueError('Unexpected deployment project/team/environment')
                return {key: row.get(key) for key in ('id', 'url', 'readyState')}
            except (subprocess.TimeoutExpired, InspectionTransient, json.JSONDecodeError):
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)

    def upload(self, notebook, manifest_hash, receipt):
        isolated = prepare_cli(self.vendor)
        env = dict(os.environ, WEEKLY_VERCEL_VENDOR_ROOT=str(self.vendor),
                   WEEKLY_VERCEL_ISOLATED_ROOT=str(isolated), NODE_PATH=str(self.vendor.parent))
        command = [str(self.node), '--require', str(RUNTIME), str(isolated / 'dist/vc.js'),
            'deploy', '--prod', '--yes', '--scope', TEAM, '--archive=tgz', '--no-wait', '--format=json',
            '--meta', f'weekly_manifest_sha256={manifest_hash}', '--cwd', str(notebook)]
        out, err = receipt.with_suffix('.stdout.log'), receipt.with_suffix('.stderr.log')
        # Exclusive files and a pre-existing receipt prevent accidental upload replay.
        with out.open('x') as stdout, err.open('x') as stderr:
            try:
                result = subprocess.run(command, env=env, stdout=stdout, stderr=stderr, timeout=UPLOAD_TIMEOUT_SECONDS)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
        reference = deployment_reference(out.read_text()) or deployment_reference(err.read_text())
        return code, reference


class InspectionTransient(RuntimeError):
    pass


def deploy_prepared(notebook, base, manifest_path, receipt_path, client, *, clock=time.monotonic, sleep=time.sleep):
    notebook, base, manifest_path, receipt_path = map(report_storage.no_symlinks, (notebook, base, manifest_path, receipt_path))
    if any(p.is_relative_to(root) for p in (receipt_path, manifest_path) for root in (notebook, base)):
        raise ValueError('Deployment receipts/manifests must remain outside immutable notebooks')
    check_project(notebook)
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if verify_artifact(base, notebook, manifest['week']) != manifest:
        raise ValueError('Prepared notebook differs from its preservation manifest')
    baseline = json.loads((base.parent / 'deployment_receipt.json').read_text())
    if baseline.get('status') != 'verified' or baseline.get('files') != files(base):
        raise ValueError('Base notebook no longer matches its verified complete receipt')
    identity = {'schema': 'weekly-v2-deployment-transport/v1', 'notebook': str(notebook),
                'base_notebook': str(base), 'manifest_sha256': sha(manifest_bytes), 'week': manifest['week'],
                'previous_deployment_id': baseline['deployment_id']}
    existing = receipt_path.exists()
    receipt = json.loads(receipt_path.read_text()) if existing else dict(identity)
    if any(receipt.get(k) != v for k, v in identity.items()):
        raise ValueError('Existing deployment receipt belongs to another artifact; never overwrite it')

    def record(status, **values):
        receipt.update(values, status=status, observed_at=datetime.now(timezone.utc).isoformat())
        atomic_json(receipt_path, receipt)

    canonical = client.inspect(CANONICAL)
    reference = receipt.get('deployment_reference')
    if existing and not reference:
        # The CLI may have created a deployment immediately before interruption.
        # Reconcile its retained acknowledgement, never issue another deploy.
        for suffix in ('.stdout.log', '.stderr.log'):
            log = receipt_path.with_suffix(suffix)
            if log.is_symlink():
                raise ValueError('Deployment log must not be a symlink')
            if log.is_file():
                reference = deployment_reference(log.read_text())
                if reference:
                    record('deployment_reconciled_from_cli_log', deployment_reference=reference)
                    break
        if not reference:
            raise ValueError('Upload outcome uncertain; reconcile the preserved logs before retrying, do not regenerate/redeploy')
    if not existing:
        if canonical['id'] != identity['previous_deployment_id']:
            raise ValueError('Production advanced beyond the verified base; stop without uploading')
        record('upload_started', adapter=ADAPTER, cli_version=VERSION, started_at=datetime.now(timezone.utc).isoformat())
        try:
            code, reference = client.upload(notebook, identity['manifest_sha256'], receipt_path)
        except BaseException:
            record('upload_uncertain')
            raise
        record('deployment_created' if reference else 'upload_uncertain', upload_exit_code=code, deployment_reference=reference)
        if not reference:
            raise RuntimeError('No confirmed deployment identity; preserve logs and reconcile without replaying upload')

    deadline = clock() + 900
    while True:
        try:
            deployment = client.inspect(reference)
            canonical = client.inspect(CANONICAL)
        except (subprocess.TimeoutExpired, InspectionTransient, json.JSONDecodeError):
            record('awaiting_deployment_observation', deployment_reference=reference)
            if clock() >= deadline:
                raise RuntimeError('Deployment inspection timed out; resume this same receipt/ID, never upload again')
            sleep(15)
            continue
        known_id = receipt.get('deployment_id')
        if known_id and deployment['id'] != known_id:
            raise ValueError('Deployment identity changed')
        if canonical['id'] not in (identity['previous_deployment_id'], deployment['id']):
            raise ValueError('Another production release intervened; stop without overwriting it')
        record('observing_deployment', deployment_id=deployment['id'], deployment=deployment)
        if deployment['readyState'] in ('ERROR', 'CANCELED'):
            record('deployment_failed')
            raise RuntimeError('The existing deployment failed; no replacement was created')
        if deployment['readyState'] == 'READY' and canonical['id'] == deployment['id']:
            if verify_artifact(base, notebook, manifest['week']) != manifest:
                raise ValueError('Prepared notebook changed during deployment')
            record('ready_for_browser_verification')
            return receipt
        if clock() >= deadline:
            raise RuntimeError('Existing deployment not ready; resume this receipt/ID, never upload again')
        sleep(15)


def require_parent_lock():
    """A canonical child may share its parent's guard, never silently bypass it."""
    info = json.loads(report_storage.LOCK.read_text())
    if info.get('pid') != os.getppid():
        raise ValueError('Canonical parent does not own the shared writer lock')
    with report_storage.LOCK.open('r+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        raise ValueError('Canonical parent writer lock is not held')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notebook', required=True, type=Path)
    parser.add_argument('--check', action='store_true', help='Read-only preflight; no upload/cache preparation')
    parser.add_argument('--base-notebook', type=Path)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--receipt', type=Path)
    parser.add_argument('--under-release-lock', action='store_true')
    args = parser.parse_args(argv)
    notebook = report_storage.no_symlinks(args.notebook.expanduser())
    node, vendor = toolchain()
    check_project(notebook)
    if args.check:
        print(json.dumps({'status': 'passed', 'cli_version': VERSION, 'node': str(node), 'adapter': ADAPTER}))
        return 0
    if not all((args.base_notebook, args.manifest, args.receipt)):
        parser.error('Deployment requires --base-notebook, --manifest and --receipt')
    base, manifest, receipt = (p.expanduser().absolute() for p in (args.base_notebook, args.manifest, args.receipt))
    if args.under_release_lock:
        require_parent_lock()
    guard = nullcontext() if args.under_release_lock else report_storage.release_guard('weekly-vercel-upload', [base, notebook], baseline=base)
    with guard:
        report_storage.require_space([base, notebook], working_bytes=max(report_storage.MIN_WORKING, report_storage.tree_bytes(base, exclude_build_cache=True) * 3))
        result = deploy_prepared(notebook, base, manifest, receipt, Client(node, vendor))
    print(json.dumps({'status': result['status'], 'deployment_id': result['deployment_id'], 'receipt': str(receipt)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
