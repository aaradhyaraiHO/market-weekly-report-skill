"""Fail-closed, hash/reference-based HTML retention. Dry-run is the default.

Requires an operator-verified registry and explicit plan-hash approval to apply.
Unknown artifacts, metadata and unique contents are never deletion candidates.
No cloud operations, metric changes, or broad directory removal.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import time
import uuid

import report_storage as storage


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def rel(value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('Invalid relative path')
    if Path(value).is_absolute() or any(p in ('', '.', '..') for p in value.split('/')):
        raise ValueError('Unsafe relative path')
    return value


def under(path, prefix):
    return path == prefix or path.startswith(prefix + '/')


@contextmanager
def parent_fd(root, relative):
    relative = rel(relative)
    root = storage.no_symlinks(root)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in relative.split('/')[:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd, relative.split('/')[-1]
    finally:
        os.close(fd)


def fingerprint(root, relative):
    with parent_fd(root, relative) as (directory, leaf):
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        with os.fdopen(fd, 'rb') as f:
            before = os.fstat(f.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError('Candidate/equivalent must be a regular file')
            sha = storage.stream_sha256(f)
            after = os.fstat(f.fileno())
            named = os.stat(leaf, dir_fd=directory, follow_symlinks=False)
    signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if signature(before) != signature(after) or signature(after) != signature(named):
        raise ValueError('File changed during verification')
    return {'sha256': sha, 'size': after.st_size, 'allocated': after.st_blocks * 512,
            'signature': signature(after)}


def verified_json(path, sha):
    path = storage.no_symlinks(path)
    if storage.sha256(path) != sha:
        raise ValueError('Evidence changed: ' + str(path))
    return json.loads(path.read_text())


def validate_registry(registry, now):
    root = storage.no_symlinks(registry['cache_root'])
    if root.name != 'weekly_report' or root.parent.name != '.cache':
        raise ValueError('Retention scope must be the explicit weekly report cache')
    if not registry.get('pins') or not registry.get('references'):
        raise ValueError('Current production, rollback and monthly references are required')
    for value in registry['pins'] + registry['references']:
        rel(value)
        pinned = storage.no_symlinks(root / value)
        if not pinned.exists():
            raise ValueError('Missing protected reference: ' + value)
        storage.deployable(pinned)
    age = now - datetime.fromisoformat(registry['references_verified_at']).timestamp()
    if not 0 <= age <= 3600:
        raise ValueError('Reference observations expired; refresh current production/baseline/recovery checks')
    if not registry.get('reference_evidence'):
        raise ValueError('Missing reference evidence')
    for record in registry['reference_evidence']:
        verified_json(record['path'], record['sha256'])
    backup = registry['backup']
    manifest = verified_json(backup['manifest'], backup['manifest_sha256'])
    receipt = verified_json(backup['restore_receipt'], backup['restore_receipt_sha256'])
    if not receipt.get('archive_sha256_verified') or receipt.get('source_or_production_modified') is not False:
        raise ValueError('Independent restore evidence is incomplete')
    if receipt.get('original_paths_mapped_to_verified_objects') != len(manifest['files']):
        raise ValueError('Backup scope mismatch')
    hashes = {r['sha256'] for r in manifest['files']}
    if receipt.get('all_unique_objects_restored_and_hashed') != len(hashes):
        raise ValueError('Not all backup objects were restored and verified')
    return root, {r['candidate']: r for r in manifest['files']}


def discover(registry):
    """Automatic candidate discovery is bounded by the verified backup manifest.

    Never scan unknown directories into a deletion plan; every candidate still
    passes classification, closure, reference and immediate hash checks in plan.
    """
    _, archived = validate_registry(registry, time.time())
    return list(archived.values())


def audit_policy(path):
    """Read-only diagnostics for each release, including blocked policy inputs.

    Old observations are reported as expired, never refreshed from the clock.
    An audit cannot authorize deletion and never calls apply().
    """
    result = {'schema': 1, 'mode': 'dry_run', 'deletion_enabled': False,
              'status': 'unconfigured', 'blockers': [], 'candidates': []}
    path = storage.no_symlinks(path)
    if not path.exists():
        result['blockers'] = ['No retention audit policy; all artifacts remain protected']
        return result
    registry, rows = {}, []
    try:
        if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('Retention audit policy must be a regular file under 8 MiB')
        policy = json.loads(path.read_text())
        registry, rows = policy['registry'], policy['candidates']
        if not isinstance(rows, list):
            raise ValueError('Retention audit candidates must be a list')
        result['policy_sha256'] = storage.sha256(path)
        checked = plan(registry, rows)
        result.update(status='evaluated', candidates=checked['candidates'],
                      plan_sha256=checked['plan_sha256'],
                      eligible_allocated_bytes=checked['eligible_allocated_bytes'])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        reason = str(exc)
        result.update(status='blocked', blockers=[reason], eligible_allocated_bytes=0)
        backup = {}
        try:
            record = registry['backup']
            manifest = verified_json(record['manifest'], record['manifest_sha256'])
            backup = {r['candidate']: r for r in manifest['files']}
        except (OSError, ValueError, KeyError, TypeError):
            pass
        for item in rows if isinstance(rows, list) else []:
            if not isinstance(item, dict):
                continue
            blockers = [reason]
            name = item.get('candidate', '')
            classification = registry.get('artifacts', {}).get(name.split('/')[0], {})
            if classification.get('kind') != 'duplicate_working' or classification.get('status') != 'closed_verified':
                blockers.append('unknown_or_unfinished_artifact')
            archived = backup.get(name, {})
            if archived.get('sha256') != item.get('sha256') or archived.get('size') != item.get('size'):
                blockers.append('not_in_verified_backup')
            result['candidates'].append({**item, 'reason': 'duplicate candidate requires verified evidence',
                                         'safe': False, 'blockers': blockers})
    return result


def plan(registry, candidates, now=None):
    now = time.time() if now is None else now
    root, backup = validate_registry(registry, now)
    pins = registry['pins'] + registry['references']
    results = []
    seen = set()
    for item in candidates:
        name, keeper = rel(item['candidate']), rel(item['retained_equivalent'])
        blockers = []
        if name in seen:
            raise ValueError('Duplicate candidate path')
        seen.add(name)
        artifact = name.split('/')[0]
        classification = registry.get('artifacts', {}).get(artifact, {})
        if not name.endswith('.html'):
            blockers.append('non_html_protected')
        if any(under(name, p) or under(p, artifact) for p in pins):
            blockers.append('pinned_or_referenced')
        if not any(under(keeper, p) for p in registry['pins']):
            blockers.append('keeper_not_pinned')
        if classification.get('kind') != 'duplicate_working' or classification.get('status') != 'closed_verified':
            blockers.append('unknown_or_unfinished_artifact')
        else:
            closed = datetime.fromisoformat(classification['closed_at']).timestamp()
            if now - closed < 7 * 86400:
                blockers.append('seven_day_retention_not_met')
            if not classification.get('evidence'):
                blockers.append('missing_closure_evidence')
            for evidence in classification.get('evidence', []):
                verified_json(evidence['path'], evidence['sha256'])
        archived = backup.get(name, {})
        if archived.get('sha256') != item['sha256'] or archived.get('size') != item['size']:
            blockers.append('not_in_verified_backup')
        record = {'candidate': name, 'retained_equivalent': keeper, 'sha256': item['sha256'],
                  'size': item['size'], 'reason': 'verified_duplicate_working_html', 'blockers': blockers}
        if not blockers:
            try:
                a, b = fingerprint(root, name), fingerprint(root, keeper)
                if a['sha256'] != item['sha256'] or b['sha256'] != item['sha256'] or a['size'] != item['size'] or b['size'] != item['size']:
                    blockers.append('fresh_hash_mismatch')
                if a['signature'][:2] == b['signature'][:2]:
                    blockers.append('same_inode_not_independent')
                record['allocated_bytes'] = a['allocated']
            except (OSError, ValueError) as exc:
                blockers.append(str(exc))
        record['safe'] = not blockers
        results.append(record)
    # A retained equivalent must never also be on this deletion list.
    if any(row['retained_equivalent'] in seen for row in results):
        raise ValueError('Retained equivalent is itself a candidate')
    payload = {'schema': 1, 'root': str(root), 'registry_sha256': digest(registry),
               'candidates': results, 'soft_target_bytes': 60 * storage.GIB,
               'eligible_allocated_bytes': sum(r.get('allocated_bytes', 0) for r in results if r['safe']),
               'warning': 'Allocated sizes can overstate physical reclaim on APFS; protected history wins over soft target.'}
    payload['plan_sha256'] = digest(payload)
    return payload


def append_record(stream, record):
    stream.write(json.dumps(record, sort_keys=True) + '\n')
    stream.flush()
    os.fsync(stream.fileno())


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def apply(registry, candidates, approval, out, *, lock_path=None, resume=False):
    """Called only for an explicitly approved exact plan; no implicit age cleanup."""
    out = storage.no_symlinks(out)
    root = storage.no_symlinks(registry['cache_root'])
    if root == out or root in out.parents:
        raise ValueError('Deletion journal must live outside the candidate cache')
    with storage.writer_lock('retention', lock_path):
        recovered = set()
        if resume:
            fresh = json.loads((out / 'approved-plan.json').read_text())
            payload = {k: v for k, v in fresh.items() if k != 'plan_sha256'}
            if fresh['plan_sha256'] != approval or digest(payload) != approval or fresh['root'] != str(root):
                raise ValueError('Recovery plan mismatch')
            exact = lambda rows: [(r['candidate'], r['retained_equivalent'], r['size'], r['sha256']) for r in rows]
            if exact(candidates) != exact(fresh['candidates']):
                raise ValueError('Recovery candidates differ from approved scope')
            events = [json.loads(line) for line in (out / 'deletion-journal.jsonl').read_text().splitlines()]
            intents = {r['candidate'] for r in events if r['event'] in ('intent', 'removed')}
            # Refresh references and independent backup proof, including after a
            # long interruption. The original exact scope cannot be expanded.
            _, archived = validate_registry(registry, time.time())
            remaining = []
            for row in candidates:
                path = storage.no_symlinks(root / rel(row['candidate']))
                if not path.exists():
                    if row['candidate'] not in intents or archived.get(row['candidate'], {}).get('sha256') != row['sha256']:
                        raise ValueError('Missing file without journal/backup proof')
                    keeper = row['retained_equivalent']
                    if not any(under(keeper, p) for p in registry['pins']) or fingerprint(root, keeper)['sha256'] != row['sha256']:
                        raise ValueError('Recovery retained equivalent unavailable')
                    recovered.add(row['candidate'])
                else:
                    remaining.append(row)
            checked = plan(registry, remaining)
            if any(not r['safe'] for r in checked['candidates']):
                raise ValueError('Recovery references/hashes changed; stopped')
        else:
            fresh = plan(registry, candidates)
            if approval != fresh['plan_sha256']:
                raise ValueError('Exact plan approval missing or stale')
            if not fresh['candidates'] or any(not r['safe'] for r in fresh['candidates']):
                raise ValueError('Plan contains protected/blocked candidates; nothing removed')
            out.mkdir(parents=True, exist_ok=False)
            with (out / 'approved-plan.json').open('x') as f:
                json.dump(fresh, f, indent=2); f.flush(); os.fsync(f.fileno())
        sync_directory(out)
        sync_directory(out.parent)
        with (out / 'deletion-journal.jsonl').open('a' if resume else 'x') as journal:
            sync_directory(out)
            for artifact in sorted({r['candidate'].split('/')[0] for r in fresh['candidates']}):
                marker = root / artifact / storage.RETIRED
                storage.no_symlinks(marker)
                if resume and marker.exists():
                    if json.loads(marker.read_text()).get('plan_sha256') != approval:
                        raise ValueError('Retirement marker belongs to another plan')
                    continue
                with marker.open('x') as f:
                    json.dump({'status': 'retired_partial_not_deployable', 'plan_sha256': approval,
                               'restore_map': str(out / 'approved-plan.json')}, f)
                    f.flush(); os.fsync(f.fileno())
                sync_directory(marker.parent)
            for row in fresh['candidates']:
                if row['candidate'] in recovered:
                    append_record(journal, {'event': 'reconciled_removed', **row})
                    continue
                # Rehash both sides immediately before unlink; fail on any change.
                current = fingerprint(root, row['candidate'])
                retained = fingerprint(root, row['retained_equivalent'])
                if current['sha256'] != row['sha256'] or retained['sha256'] != row['sha256']:
                    raise ValueError('Candidate/equivalent changed before removal')
                append_record(journal, {'event': 'intent', **row})
                with parent_fd(root, row['candidate']) as (directory, leaf):
                    named = os.stat(leaf, dir_fd=directory, follow_symlinks=False)
                    signature = (named.st_dev, named.st_ino, named.st_size, named.st_mtime_ns, named.st_ctime_ns)
                    if signature != current['signature']:
                        raise ValueError('Candidate changed before unlink')
                    os.unlink(leaf, dir_fd=directory)
                    os.fsync(directory)
                append_record(journal, {'event': 'removed', **row})
            remaining = storage.tree_bytes(root)
            append_record(journal, {'event': 'complete', 'remaining_logical_bytes': remaining,
                                    'over_soft_target': remaining > 60 * storage.GIB,
                                    'protected_data_not_removed_to_meet_target': True})
    return fresh


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--candidates', type=Path, help='Optional exact scope; default discovers only verified-backup entries')
    p.add_argument('--apply-approved-plan', help='Explicit approved SHA-256 of exact dry-run plan')
    p.add_argument('--journal-dir', type=Path)
    p.add_argument('--resume', action='store_true', help='Reconcile the same approved journal after interruption; never expand scope')
    args = p.parse_args()
    registry = json.loads(args.registry.read_text())
    rows = json.loads(args.candidates.read_text()) if args.candidates else discover(registry)
    if args.resume and not args.apply_approved_plan:
        p.error('--resume requires --apply-approved-plan and --journal-dir')
    if args.apply_approved_plan:
        if not args.journal_dir:
            p.error('--journal-dir required for apply')
        result = apply(registry, rows, args.apply_approved_plan, args.journal_dir, resume=args.resume)
    else:
        result = plan(registry, rows)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
