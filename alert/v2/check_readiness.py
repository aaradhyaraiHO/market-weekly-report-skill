#!/usr/bin/env python3
"""Static V2 alert readiness gate.

Checks the finalized weekly-market universe against the approved BGM roster,
the unchanged V1 channel map, report URL routes, and OKR market configuration.
It performs no network calls and never posts to Slack.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"
ALERT_DIR = ROOT / "alert"
HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(REPORT_DIR))
sys.path.insert(0, str(HERE))

import config  # noqa: E402
from weekly_alert_v2 import LEDGER_SLUG, LOCKED_FORMAT_VERSION  # noqa: E402


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def check(include_headout: bool = False) -> dict:
    markets = list(config.MARKETS)
    if include_headout:
        markets.append("headout")
    bgms = _load(HERE / "market_bgms.json").get("markets", {})
    channels = _load(ALERT_DIR / "market_channels.json").get("markets", {})
    okrs = _load(HERE / "okr_queries.json").get("markets", {})

    missing_bgms = []
    invalid_bgm_ids = []
    for slug in markets:
        ids = (bgms.get(slug) or {}).get("slack_user_ids") or []
        if not ids:
            missing_bgms.append(slug)
        invalid_bgm_ids.extend(
            f"{slug}:{value}" for value in ids
            if not re.fullmatch(r"U[A-Z0-9]+", str(value))
        )

    blockers = {
        "missing_bgm_assignments": missing_bgms,
        "invalid_bgm_slack_ids": invalid_bgm_ids,
        "missing_v1_channel_routes": [slug for slug in markets if not channels.get(slug)],
        "missing_report_url_routes": [slug for slug in markets if slug not in LEDGER_SLUG],
        "missing_okr_market_config": [slug for slug in markets if slug not in okrs],
    }
    return {
        "ready": not any(blockers.values()),
        "format_version": LOCKED_FORMAT_VERSION,
        "markets_checked": markets,
        "blockers": blockers,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Weekly Market Alert V2 send readiness")
    parser.add_argument("--include-headout", action="store_true")
    args = parser.parse_args()
    result = check(args.include_headout)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ready"] else 1)


if __name__ == "__main__":
    main()
