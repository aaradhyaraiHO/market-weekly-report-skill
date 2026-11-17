"""Process-scoped reliability rules shared by weekly and monthly generators.

No credential inspection, result serialization, source rewriting, or global SDK
installation changes. Query journals retain identities, never row/note contents.
"""
from __future__ import annotations
import fcntl
import hashlib
import json
import os
from pathlib import Path
import uuid

RUNTIME_API_VERSION = 1
MAX_BYTES = 80 * 1024**3
HTTP_TIMEOUT = (15, 60)
QUERY_TIMEOUT = 900


def bounded_timeout(value):
    if value is None:
        return HTTP_TIMEOUT
    if isinstance(value, tuple):
        return tuple(min(float(v), cap) if v is not None else cap for v, cap in zip(value, HTTP_TIMEOUT))
    return min(float(value), HTTP_TIMEOUT[1])


def harden_http(client):
    """Bound only this BQ client's HTTP requests, retaining its TLS/auth/proxy."""
    from requests.adapters import HTTPAdapter
    class BoundedAdapter(HTTPAdapter):
        def send(self, request, **kwargs):
            kwargs['timeout'] = bounded_timeout(kwargs.get('timeout'))
            return super().send(request, **kwargs)
    if not getattr(client, '_report_http_bounded', False):
        client._http.mount('https://bigquery.googleapis.com/', BoundedAdapter())
        client._report_http_bounded = True
    return client


def cap_config(job_config):
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig.from_api_repr(job_config.to_api_repr()) if job_config is not None else bigquery.QueryJobConfig()
    limit = cfg.maximum_bytes_billed
    if limit is not None and (limit <= 0 or limit > MAX_BYTES):
        raise ValueError('Report query exceeds the unchanged 80 GiB maximum')
    cfg.maximum_bytes_billed = limit or MAX_BYTES
    return cfg


def atomic(path, value):
    import tempfile
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.'+path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, sort_keys=True); handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def submit(client, query, config, original, kwargs):
    """Reuse an acknowledged job only inside this immutable run's journal.

    Unknown submissions stop. No cached rows or automatic resubmission. Fresh
    reconciliation deliberately runs without this producer journal.
    """
    root = os.environ.get('REPORT_QUERY_JOURNAL')
    # Do not change explicit IDs or dry-run behavior of existing source verifiers.
    if not root or config.dry_run or kwargs.get('job_id') or kwargs.get('job_id_prefix'):
        return original(client, query, job_config=config, **kwargs)
    root = Path(root)
    if root.is_symlink(): raise ValueError('Query journal cannot be a symlink')
    root.mkdir(parents=True, exist_ok=True)
    identity = {'sql_sha256': hashlib.sha256(query.encode()).hexdigest(),
                'config': config.to_api_repr(), 'project': kwargs.get('project') or client.project,
                'location': kwargs.get('location') or client.location}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    path = root/(key+'.json')
    if path.is_symlink() or (root/(key+'.lock')).is_symlink(): raise ValueError('Symlink in query journal')
    with (root/(key+'.lock')).open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            row = json.loads(path.read_text())
            if row.get('identity') != identity: raise ValueError('Query journal identity mismatch')
            try:
                job = client.get_job(row['job_id'], project=identity['project'], location=identity['location'], timeout=30)
            except Exception as exc:
                raise RuntimeError('Recorded BigQuery submission requires reconciliation; no query replayed') from exc
            if job.error_result: raise RuntimeError('Recorded BigQuery job failed; preserve journal for review')
            return job
        row = {'identity': identity, 'job_id': 'report_'+uuid.uuid4().hex, 'status': 'submitting'}
        atomic(path, row)
        job = original(client, query, job_config=config, job_id=row['job_id'], job_retry=None, **kwargs)
        row.update(status='acknowledged', job_id=job.job_id)
        atomic(path, row)
        return job


def install():
    """Use only in report processes after normal Python startup."""
    from google.cloud import bigquery
    if getattr(bigquery.Client, '_report_runtime_installed', False): return
    original_query = bigquery.Client.query
    original_result = bigquery.QueryJob.result
    def query(self, query, job_config=None, *args, **kwargs):
        if args: raise ValueError('Use named BigQuery query arguments in report runtime')
        harden_http(self)
        kwargs['timeout'] = bounded_timeout(kwargs.get('timeout'))
        return submit(self, query, cap_config(job_config or self.default_query_job_config), original_query, kwargs)
    def result(self, *args, **kwargs):
        if args: return original_result(self, *args, **kwargs)
        supplied=kwargs.get('timeout')
        kwargs['timeout'] = QUERY_TIMEOUT if supplied is None else min(supplied,QUERY_TIMEOUT)
        return original_result(self, **kwargs)
    bigquery.Client.query = query
    bigquery.QueryJob.result = result
    bigquery.Client._report_runtime_installed = True


def command(command):
    """Wrap script subprocesses; leave Node, CLIs, -m and -c untouched."""
    import sys
    argv = list(command)
    bootstrap = Path(__file__).with_name('report_bootstrap.py')
    if (len(argv) >= 2 and Path(str(argv[0])).name.startswith('python')
            and str(argv[1]).endswith('.py') and Path(argv[1]).resolve() != bootstrap):
        return [argv[0], str(bootstrap), *argv[1:]]
    return argv


def artifact_checkpoint(key, identity, paths, build):
    """Reuse a completed local build only with the same inputs and exact hashes.

    Started/failed builds never qualify as complete. Query jobs inside a retry
    retain their own no-replay identity rules. No deployment or delivery here.
    """
    import re
    root=os.environ.get('REPORT_QUERY_JOURNAL')
    if not root:
        build();return False
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',key):raise ValueError('Invalid checkpoint key')
    checkpoint=Path(root)/'completed_artifacts'/(key+'.json')
    for p in (checkpoint,*paths):
        if any(x.is_symlink() for x in (Path(p),*Path(p).parents)):
            raise ValueError('Symlink in artifact checkpoint')
    def hashes():
        result={}
        for p in paths:
            p=Path(p)
            if not p.is_file():raise ValueError('Required completed artifact missing: '+str(p))
            digest=hashlib.sha256()
            with p.open('rb') as f:
                for chunk in iter(lambda:f.read(1024*1024),b''):digest.update(chunk)
            result[str(p)]=digest.hexdigest()
        return result
    if checkpoint.exists():
        previous=json.loads(checkpoint.read_text())
        if previous.get('identity') != identity:raise ValueError('Build checkpoint inputs changed; preserve for review')
        if previous.get('status')=='complete':
            if previous['files'] != hashes():raise ValueError('Completed artifact changed; no silent regeneration')
            return True
    atomic(checkpoint,{'status':'started','identity':identity})
    build()
    atomic(checkpoint,{'status':'complete','identity':identity,'files':hashes()})
    return False
