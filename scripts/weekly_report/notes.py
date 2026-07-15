"""
Read/write notes from the Google Sheet backend.

Used by the pipeline to surface prior-week notes in context,
and by the Slack digest step to flag unresolved notes.
"""
from __future__ import annotations

import json
import os
import urllib.request
import urllib.parse
from typing import Any

from config import NOTES_SCRIPT_URL


def _url() -> str | None:
    return os.environ.get("WR_NOTES_SCRIPT_URL") or NOTES_SCRIPT_URL


def fetch_notes(market_slug: str | None = None,
                week_start: str | None = None,
                status: str | None = None) -> list[dict[str, Any]]:
    """Fetch notes from the Sheet. Returns [] if backend is not configured."""
    base = _url()
    if not base:
        return []

    params: dict[str, str] = {"action": "list"}
    if market_slug:
        params["market"] = market_slug
    if week_start:
        params["week"] = week_start
    if status:
        params["status"] = status

    url = base + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return data.get("notes", [])
    except Exception as e:
        print(f"  ! notes fetch failed: {e}")
        return []


def open_notes(market_slug: str) -> list[dict[str, Any]]:
    """All open (unresolved) notes for a market, any week."""
    return fetch_notes(market_slug=market_slug, status="open")


def notes_for_report(market_slug: str, week_start: str) -> dict[str, dict]:
    """CE-keyed dict of notes for a specific market+week, for template injection."""
    notes = fetch_notes(market_slug=market_slug, week_start=week_start)
    return {n["ce_id"]: n for n in notes if n.get("ce_id")}
