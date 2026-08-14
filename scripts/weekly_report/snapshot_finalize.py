"""Shared, behavior-preserving finalization for weekly snapshots.

This module orchestrates existing engines only. It does not calculate metrics,
change bucket criteria, normalize rows, reorder output, or perform publishing.
"""
from __future__ import annotations

import json
from pathlib import Path


def finalize_common(snapshot: dict) -> dict:
    """Attach the final buckets and optional PP/seasonality enrichments in order."""
    import buckets

    snapshot["buckets_final"] = buckets.build_buckets(snapshot)

    try:
        import pp

        snapshot["prepurchase"] = pp.build_pp(snapshot)
    except Exception as exc:
        print(f"  [pp] skipped: {exc}")
        snapshot["prepurchase"] = []

    try:
        import seasonality_llm

        attached = seasonality_llm.attach(snapshot)
        print(f"  seasonality tags attached: {attached}")
    except Exception as exc:
        print(f"  seasonality_llm.attach skipped ({exc!r})")

    return snapshot


def load_review_context(snapshot: dict, path: Path, *, success_suffix: str = "") -> None:
    """Load a review-context sidecar with the engines' existing fail-soft behavior."""
    if not path.exists():
        return
    try:
        snapshot["market_review_context"] = json.loads(path.read_text())
        print(f"  [slack] loaded {len(snapshot['market_review_context'])} context cards{success_suffix}")
    except Exception as exc:
        print(f"  [slack] sidecar load skipped ({exc!r})")
