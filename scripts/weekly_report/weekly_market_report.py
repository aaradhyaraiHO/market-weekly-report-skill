"""
Weekly Market Report V1 — one-command orchestrator.

Chains the full pipeline for one or many pilot markets:
    build_snapshot.build_market(slug, week) -> write snapshot json
    -> render.py (ONCE, with every snapshot path) -> one tabbed HTML.

Multi-market runs collapse into a single self-contained HTML with a
market-switcher tab per market (render.py already supports multi-input tabbing).

Usage:
    python weekly_market_report.py north_america
    python weekly_market_report.py all --week 2026-06-29
    python weekly_market_report.py all --validate --no-open
    python weekly_market_report.py italy --week 2026-06-29 --no-open

`--validate` runs the NA reference gate whenever north_america is in the set
(other markets only get a "no reference gate" note — they are spot-checked by
the skill workflow, not gated here).
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

import build_snapshot
import config

HERE = Path(__file__).resolve().parent


def _to_date(s: str) -> dt.date:
    return dt.date.fromisoformat(str(s)[:10])


def _resolve_targets(market_arg: str) -> list[str]:
    """'all' -> every pilot market (config order); else the single slug."""
    if market_arg == "all":
        return list(config.MARKETS)
    if market_arg not in config.MARKETS:
        sys.exit(f"Unknown market '{market_arg}'. Choose from: "
                 f"{', '.join(config.MARKETS)} | all")
    return [market_arg]


def main() -> None:
    ap = argparse.ArgumentParser(description="Weekly Market Report V1 orchestrator")
    ap.add_argument("market", help="market slug or 'all' "
                    f"({', '.join(config.MARKETS)})")
    ap.add_argument("--week", help="W0 Monday (YYYY-MM-DD); "
                    "default = latest complete matured week")
    ap.add_argument("--no-open", dest="open_", action="store_false", default=True,
                    help="do not open the rendered HTML")
    ap.add_argument("--validate", action="store_true",
                    help="run the NA reference gate when north_america is in the set")
    args = ap.parse_args()

    w0 = _to_date(args.week) if args.week else config.latest_complete_week()
    targets = _resolve_targets(args.market)
    print(f"Weekly Market Report V1 | week {config.iso(w0)} | markets: {targets}")

    # ---- build + write a snapshot per market (reuse build_snapshot helpers) ----
    snapshot_paths: list[Path] = []
    for slug in targets:
        snap = build_snapshot.build_market(slug, w0)
        path = build_snapshot._write(snap, slug, w0)
        snapshot_paths.append(path)
        if args.validate:
            if slug == "north_america":
                ok = build_snapshot.validate_na(snap)
                if not ok:
                    sys.exit("NA validation gate FAILED — aborting before render.")
            else:
                print(f"  [{slug}] --validate: no reference gate "
                      f"(spot-check headline vs Omni in the skill workflow)")

    # ---- render ONCE with all snapshots -> one tabbed HTML ----
    cmd = [sys.executable, str(HERE / "render.py"), *[str(p) for p in snapshot_paths]]
    if not args.open_:
        cmd.append("--no-open")
    print(f"\nRendering: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
