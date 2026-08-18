#!/usr/bin/env python3
"""Send CE-keyed or reconciliation-bound source suggestions to Review mode.

This is the server-side bridge contract for Granola (or another meeting adapter).
It does not read Granola itself. Feed it a JSON object with `items`, each retaining
its source reference/URL/author. Exact matches include `ce_id`; ambiguous items
omit it and enter the reconciliation inbox.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path


def build_payload(source_type: str, market_slug: str, week_start: str, items: list[dict], secret: str) -> dict:
    if not secret:
        raise ValueError("WR_REVIEW_MODE_INGEST_SECRET is required")
    if source_type not in {"granola", "slack"}:
        raise ValueError("source_type must be granola or slack")
    if not market_slug or not week_start:
        raise ValueError("market_slug and week_start are required")
    return {
        "action": "review_source_ingest",
        "ingest_secret": secret,
        "source_type": source_type,
        "market_slug": market_slug,
        "week_start": week_start,
        "items": items,
    }


def post(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "text/plain;charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "review source ingestion failed"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="JSON file containing an array or {items:[...]}")
    parser.add_argument("--source-type", default="granola", choices=["granola", "slack"])
    parser.add_argument("--market", required=True)
    parser.add_argument("--week", required=True)
    parser.add_argument("--url", default=os.environ.get("WR_REVIEW_MODE_APPS_SCRIPT_URL", ""))
    parser.add_argument("--apply", action="store_true", help="POST to the configured Apps Script")
    args = parser.parse_args()

    raw = json.loads(args.input.read_text())
    items = raw.get("items", []) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise SystemExit("input must be a JSON array or {items:[...]}")
    secret = os.environ.get("WR_REVIEW_MODE_INGEST_SECRET", "")
    payload = build_payload(args.source_type, args.market, args.week, items, secret or "DRY_RUN")
    if not args.apply:
        safe = dict(payload)
        safe["ingest_secret"] = "<redacted>"
        print(json.dumps(safe, indent=2))
        return
    if not args.url:
        raise SystemExit("--url or WR_REVIEW_MODE_APPS_SCRIPT_URL is required")
    if not secret:
        raise SystemExit("WR_REVIEW_MODE_INGEST_SECRET is required with --apply")
    print(json.dumps(post(args.url, payload), indent=2))


if __name__ == "__main__":
    main()
