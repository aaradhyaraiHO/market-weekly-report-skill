"""Shared weekly/monthly storage safety; no automatic deletion or cloud writes.

The shared writer lock serializes canonical releases and retention operations.
APFS clones are independent copy-on-write files, never mutable hard links.
"""
from contextlib import contextmanager
import ctypes
import errno
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import sys
import time
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
STORAGE_API_VERSION = 1
STATE = ROOT / '.cache' / 'report_storage'
LOCK = STATE / 'writer.lock'
GIB = 1024 ** 3
RESERVE = 30 * GIB
MIN_WORKING = 20 * GIB
RETIRED = '.report-storage-retired.json'


def no_symlinks(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f'Storage path cannot traverse a symlink: {part}')
    return path


def nearest_existing(path):
    path = no_symlinks(path)
    while not path.exists():
        path = path.parent
    return path


def deployable(path):
    path = no_symlinks(path)
    for parent in (path, *path.parents):
        if (parent / RETIRED).exists():
            raise ValueError(f'Retired/incomplete artifact cannot be used: {parent}')


def tree_bytes(root, *, exclude_build_cache=False):
    root = no_symlinks(root)
    if not root.exists():
        return 0
    total = 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        if exclude_build_cache:
            dirs[:] = [n for n in dirs if n not in {'.git', '.vercel', 'node_modules', '__pycache__'} and not n.startswith('.env')]
            names = [n for n in names if not n.startswith('.env')]
        for name in dirs + names:
            path = Path(directory) / name
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                raise ValueError(f'Symlink in storage estimate: {path}')
            if stat.S_ISREG(info.st_mode):
                total += info.st_size
    return total


def preflight(paths, *, working_bytes=MIN_WORKING, reserved_bytes=0, reclaimable_bytes=0):
    for value in (working_bytes, reserved_bytes, reclaimable_bytes):
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Storage estimates must be finite and nonnegative')
    working_bytes = max(MIN_WORKING, int(working_bytes))
    required = working_bytes + int(reserved_bytes) + RESERVE
    volumes = {}
    for path in [*paths, Path(tempfile.gettempdir()).resolve()]:
        existing = nearest_existing(path)
        device = existing.stat().st_dev
        if device not in volumes:
            free = shutil.disk_usage(existing).free
            volumes[device] = {'path': str(existing), 'free_bytes': free,
                               'required_bytes': required, 'reserve_bytes': RESERVE,
                               'working_bytes': working_bytes, 'reserved_bytes': int(reserved_bytes),
                               'estimated_verified_reclaimable_bytes': int(reclaimable_bytes),
                               'reclaimable_basis': 'supplied fresh verified estimate' if reclaimable_bytes else 'not assessed; no space credited',
                               'capacity_pass': free >= required}
    return {'capacity_pass': bool(volumes) and all(v['capacity_pass'] for v in volumes.values()),
            'volumes': list(volumes.values()), 'emergency_deletion': False}


def require_space(paths, *, working_bytes=MIN_WORKING):
    result = preflight(paths, working_bytes=working_bytes)
    if not result['capacity_pass']:
        raise RuntimeError('Disk-space preflight blocked before work; no files pruned. ' + json.dumps(result))
    return result


@contextmanager
def writer_lock(label, lock_path=None):
    path = no_symlinks(lock_path or LOCK)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Shared storage lock is not a regular file')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError('Another weekly/monthly/storage writer is active; stopped without changes') from exc
        # Never unlink the lock: every process must lock the same inode.
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps({'pid': os.getpid(), 'operation': label, 'started_at': time.time()}).encode())
        os.fsync(fd)
        yield
    finally:
        os.close(fd)


@contextmanager
def release_guard(label, paths, *, baseline=None, lock_path=None, audit=False):
    # Do not grant space savings for possible clones: estimate full copies.
    working = max(MIN_WORKING, tree_bytes(baseline, exclude_build_cache=True) * 3 if baseline else 0)
    require_space(paths, working_bytes=working)
    with writer_lock(label, lock_path):
        result = require_space(paths, working_bytes=working)
        if audit:
            result['retention_audit'] = record_retention_audit(label)
        yield result


def record_retention_audit(label):
    """Record a fresh diagnostic under the writer lock; never apply retention."""
    import importlib
    scripts = str(Path(__file__).parent)
    sys.path.insert(0, scripts)
    try:
        retention = importlib.import_module('storage_retention')
    finally:
        sys.path.pop(0)
    if Path(retention.__file__).resolve() != Path(__file__).with_name('storage_retention.py').resolve():
        raise RuntimeError('Retention auditor loaded from an unexpected release')
    payload = retention.audit_policy(STATE / 'retention-audit-policy.json')
    payload['operation'] = label
    payload['observed_at'] = time.time()
    directory = no_symlinks(STATE / 'audits')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (str(time.time_ns()) + '-' + uuid.uuid4().hex + '.json')
    with path.open('x') as stream:
        json.dump(payload, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    summary = {'path': str(path), 'status': payload['status'],
               'candidate_count': len(payload.get('candidates', [])),
               'eligible_count': sum(row.get('safe', False) for row in payload.get('candidates', [])),
               'deletion_enabled': False, 'blockers': payload.get('blockers', [])}
    print('Storage retention dry-run: ' + json.dumps(summary), flush=True)
    return summary


def stream_sha256(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
        digest.update(block)
    return digest.hexdigest()


def sha256(path):
    with open(path, 'rb') as f:
        return stream_sha256(f)


def _clone(source, target):
    if sys.platform != 'darwin':
        return False
    libc = ctypes.CDLL(None, use_errno=True)
    clone = getattr(libc, 'clonefile', None)
    if clone is None:
        return False
    clone.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
    clone.restype = ctypes.c_int
    if clone(os.fsencode(source), os.fsencode(target), 1) == 0:
        return True
    error = ctypes.get_errno()
    if error in (errno.ENOTSUP, errno.EXDEV, errno.ENOSYS, errno.EINVAL):
        return False
    raise OSError(error, os.strerror(error), str(target))


def copy_independent(source, target):
    """Atomic verified CoW copy; independent inode, full-copy fallback.

    Existing target replacement is permitted only because callers explicitly
    publish into their staging notebook. Never use for canonical source mutation.
    """
    source, target = no_symlinks(source), no_symlinks(target)
    if source == target:
        raise ValueError('Source and target must differ')
    before = source.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('Only regular files may be copied')
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name('.storage-copy-' + uuid.uuid4().hex)
    try:
        cloned = _clone(source, temp)
        if not cloned:
            with source.open('rb') as src, temp.open('xb') as dst:
                shutil.copyfileobj(src, dst, 4 * 1024 * 1024)
            shutil.copystat(source, temp, follow_symlinks=False)
        after = source.stat()
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if signature(before) != signature(after) or sha256(source) != sha256(temp):
            raise ValueError('Source changed or copy hash mismatch')
        if (after.st_dev, after.st_ino) == (temp.stat().st_dev, temp.stat().st_ino):
            raise ValueError('Hard-link copy forbidden')
        with temp.open('rb') as f:
            os.fsync(f.fileno())
        os.replace(temp, target)
        directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return 'clone' if cloned else 'copy'
    finally:
        if temp.exists():
            temp.unlink()  # Only our uniquely-created incomplete copy, never source.


def copy_notebook(source, target, *, ignore=None):
    """Fresh, independently writable staging tree; no secret/build-cache copying.

    Call inside the canonical shared release lock. Failure leaves staging for
    recovery; it is never made deployable by this helper alone.
    """
    source, target = no_symlinks(source), no_symlinks(target)
    deployable(source)
    deployable(target)
    if source == target or source in target.parents or target in source.parents:
        raise ValueError('Notebook copies must be separate non-nested paths')
    require_space([source, target], working_bytes=max(MIN_WORKING, tree_bytes(source, exclude_build_cache=True) * 3))
    return shutil.copytree(source, target, ignore=ignore, copy_function=copy_independent)
