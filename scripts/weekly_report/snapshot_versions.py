"""Read verified corrected prior-week facts without rewriting frozen originals."""
import hashlib
import json
from pathlib import Path

REGISTRY='verified_snapshot_corrections.json'
SCHEMA='weekly-verified-snapshot-corrections/v1'

class CorrectionEvidenceError(RuntimeError):
    pass


def _within(cache, raw):
    path=Path(raw)
    if not path.is_absolute() or '..' in path.parts or cache not in path.parents:
        raise ValueError('Correction evidence must remain inside the weekly cache')
    current=cache
    if cache.is_symlink():raise ValueError('Symlink cache is not correction evidence')
    for part in path.relative_to(cache).parts:
        current=current/part
        if current.is_symlink():raise ValueError('Symlink correction evidence rejected')
    return path


def load_prior(cache, slug, week):
    cache=Path(cache).absolute();name=f'snapshot_{slug}_{week}.json'
    registry=cache/REGISTRY
    record=None
    if registry.exists():
        try:
            if registry.is_symlink():raise ValueError('Symlink registry rejected')
            index=json.loads(registry.read_text())
            if index['schema']!=SCHEMA:raise ValueError('Unknown correction registry')
            record=index['weeks'].get(week,{}).get(slug)
        except Exception as exc:
            raise CorrectionEvidenceError('Invalid verified snapshot correction registry') from exc
    if record is None:
        path=cache/name
        return json.loads(path.read_text()) if path.exists() else None
    try:
        path=_within(cache,record['snapshot']);receipt_path=_within(cache,record['receipt'])
        if path.name!=name or receipt_path.name!='deployment_receipt.json':
            raise ValueError('Unexpected correction evidence identity')
        receipt=json.loads(receipt_path.read_text())
        if (receipt.get('status')!='verified' or receipt.get('week')!=week
                or receipt.get('snapshot_dir')!=str(path.parent)
                or receipt.get('snapshots',{}).get(name)!=record['sha256']):
            raise ValueError('Correction is not bound to a verified release')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=record['sha256']:
            raise ValueError('Corrected snapshot hash differs')
        result=json.loads(data)
        if result['meta']['market_slug']!=slug or result['meta']['week_start']!=week:
            raise ValueError('Corrected snapshot scope/week differs')
        return result
    except Exception as exc:
        # Never silently use the superseded original after a correction exists.
        raise CorrectionEvidenceError(f'Unverified prior snapshot correction: {slug} {week}') from exc
