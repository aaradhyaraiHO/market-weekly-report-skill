"""Common bounded stage execution; cadence receipts remain authoritative.

Does not skip stages, replay writes, fabricate browser evidence, or post messages.
"""
import os
from pathlib import Path
import subprocess
from report_runtime import command, artifact_checkpoint

RELEASE_API_VERSION = 1
# A slow prepared upload has its own 90-minute inner transport deadline.
STAGE_TIMEOUTS = {'deploy-vercel': 105*60, 'preupload-vercel': 90*60,
                  'build-markets': 3*60*60, 'build-publish-all': 6*60*60}
DEFAULT_STAGE_TIMEOUT = 60*60
PRODUCER_STEPS = frozenset(('build-markets', 'build-headout', 'build-market-okrs',
                           'combined-v2-gate', 'build-publish-all', 'alerts-dry-run'))


def execution(step, package, env):
    env = dict(env)
    # Never allow a producer job cache to weaken a fresh independent source gate.
    env.pop('REPORT_QUERY_JOURNAL', None)
    if step.name in PRODUCER_STEPS:
        env['REPORT_QUERY_JOURNAL'] = str(Path(package)/'query_jobs'/step.name)
    argv = command(step.command)
    # Preserve caller argument shape for commands that do not need a bootstrap.
    if argv == list(step.command): argv = step.command
    return argv, env, STAGE_TIMEOUTS.get(step.name, DEFAULT_STAGE_TIMEOUT)


def notify_failure(cadence, period, stage):
    """Best-effort local Mac notification. Failure never changes release state."""
    print(f'RELEASE BLOCKED: {cadence} {period}; stage {stage}. Recovery state retained.', flush=True)
    if os.environ.get('REPORT_DISABLE_NOTIFICATIONS') == '1': return
    import shutil
    if shutil.which('osascript'):
        try:
            # AppleScript reads literal arguments; no user/error text interpolated as code.
            subprocess.run(['osascript', '-e', 'on run argv', '-e',
                'display notification (item 1 of argv) with title "Report release blocked"',
                '-e', 'end run', f'{cadence} {period}: {stage}. Open Codex for the blocker.'],
                capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.SubprocessError): pass


def run_bounded(argv, *, cwd, env, check=True, timeout):
    """Stop the whole stage process group before releasing the shared lock."""
    import signal
    child = subprocess.Popen(argv, cwd=cwd, env=env, start_new_session=True)
    try:
        code = child.wait(timeout=timeout)
    except BaseException:
        try: os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired: pass
        # A child can exit before its descendants; always clear its process group.
        try: os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        child.wait()
        raise
    if check and code: raise subprocess.CalledProcessError(code, argv)
    return subprocess.CompletedProcess(argv, code)


def source_identity():
    import hashlib
    root=Path(__file__).resolve().parents[2]
    result={}
    for name,path in [('weekly',root),('monthly',Path(os.environ.get('MMR_MONTHLY_REPO',str(Path.home()/'market-monthly-review-skill')))),
                      ('analytics',Path(os.environ.get('MMR_ANALYTICS_REPO',str(Path.home()/'analytics'))))]:
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=path,text=True).strip()
        scopes = {'weekly':['scripts/weekly_report','alert/v2'], 'monthly':['engine','alert'],
                  'analytics':['scripts/ce_buckets','scripts/perf_audit_engine_v6','scripts/ce_health.py']}[name]
        digest = hashlib.sha256()
        for scope in scopes:
            source = path/scope
            candidates = source.rglob('*') if source.is_dir() else [source]
            for file in sorted(candidates):
                if file.is_file() and file.suffix in ('.py','.js','.cjs','.mjs','.json') and '__pycache__' not in file.parts:
                    if file.is_symlink(): raise ValueError('Symlink in report source dependencies')
                    digest.update(file.relative_to(path).as_posix().encode());digest.update(file.read_bytes())
        result[name]={'commit':commit,'source_tree_sha256':digest.hexdigest()}
    return result


def bind_sources(package):
    from report_runtime import atomic
    import json
    path=Path(package)/'runtime_sources.json'
    identity=source_identity()
    if path.exists() and json.loads(path.read_text()) != identity:
        raise ValueError('Release source changed since query/build checkpoints; review before resume')
    if not path.exists():atomic(path,identity)
    return identity
