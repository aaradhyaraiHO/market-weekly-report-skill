"""
Weekly Market Report — one-command snapshot producer and renderer.

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
    python weekly_market_report.py all --week 2026-06-29 --renderer both --no-open

`--validate` runs the NA reference gate whenever north_america is in the set
(other markets only get a "no reference gate" note — they are spot-checked by
the skill workflow, not gated here).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import build_global
import build_snapshot
import config
import release_v2
import render_v2

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
V2_REPORTS = REPO / "thoughts" / "shared" / "weekly-report-v2"
CACHE = REPO / ".cache" / "weekly_report"


def _to_date(s: str) -> dt.date:
    return dt.date.fromisoformat(str(s)[:10])


def _resolve_targets(market_arg: str) -> list[str]:
    """'all' -> every pilot market (config order); 'headout' -> true-global
    aggregate (all ~69 business_markets, its own build path); else the slug."""
    if market_arg == "all":
        return list(config.MARKETS)
    if market_arg == "headout":
        return ["headout"]
    if market_arg not in config.MARKETS:
        sys.exit(f"Unknown market '{market_arg}'. Choose from: "
                 f"{', '.join(config.MARKETS)} | all | headout")
    return [market_arg]


def main() -> None:
    ap = argparse.ArgumentParser(description="Weekly Market Report orchestrator")
    ap.add_argument("market", help="market slug, 'all', or 'headout' (true-global) "
                    f"({', '.join(config.MARKETS)})")
    ap.add_argument("--week", help="W0 week-start = SUNDAY (YYYY-MM-DD); "
                    "any date is snapped to its Sun–Sat week. default = latest complete Sun–Sat week")
    ap.add_argument("--no-open", dest="open_", action="store_false", default=True,
                    help="do not open the rendered HTML")
    ap.add_argument("--validate", action="store_true",
                    help="run the NA reference gate when north_america is in the set")
    ap.add_argument("--renderer", choices=("v1", "v2", "both"), default="v1",
                    help="render V1 (default), V2, or both from the same snapshots")
    ap.add_argument("--no-v2-goals", action="store_true",
                    help="skip the optional live monthly-target enrichment for V2")
    args = ap.parse_args()

    w0 = config._week_start(_to_date(args.week)) if args.week else config.latest_complete_week()
    targets = _resolve_targets(args.market)
    print(f"Weekly Market Report | week {config.iso(w0)} | markets: {targets} | renderer: {args.renderer}")

    # ---- build + write a snapshot per market (reuse build_snapshot helpers) ----
    snapshot_paths: list[Path] = []
    for slug in targets:
        if slug == "headout":
            # true-global aggregate: its own build path (no market filter)
            snap = build_global.build_global(config.iso(w0))
            path = build_snapshot._write(snap, "headout", w0)
            snapshot_paths.append(path)
            continue
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

    # V1 remains the default and retains its existing one-file tabbed render.
    if args.renderer in ("v1", "both"):
        cmd = [sys.executable, str(HERE / "render.py"), *[str(p) for p in snapshot_paths]]
        if not args.open_:
            cmd.append("--no-open")
        print(f"\nRendering V1: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    # V2 is a presentation/enrichment layer over the exact snapshots above.
    # It renders one artifact per market and emits a no-publish release gate.
    if args.renderer in ("v2", "both"):
        manifest = release_v2.release(
            snapshot_paths,
            V2_REPORTS,
            fetch_goals=not args.no_v2_goals,
        )
        CACHE.mkdir(parents=True, exist_ok=True)
        manifest_path = CACHE / f"v2_release_{config.iso(w0)}.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(f"\nV2 release gate: {manifest['status'].upper()}")
        print(f"V2 manifest: {manifest_path}")
        if manifest["status"] != "pass":
            sys.exit("V2 parity gate FAILED — V1 artifacts are intact; activation blocked.")
        for group_slug, group in config.MARKET_REPORT_GROUPS.items():
            members = tuple(group["markets"])
            if not all(member in targets for member in members):
                continue
            group_markets = [
                render_v2.render_v1.load_markets([str(CACHE / f"snapshot_{member}_{config.iso(w0)}.json")])[0]
                for member in members
            ]
            goals = render_v2.load_goals(V2_REPORTS / "goals_v2.json")
            output = V2_REPORTS / f"report_{group_slug}_{config.iso(w0)}.html"
            output.write_text(render_v2.render(
                group_markets,
                goals=goals,
                report_group={"slug": group_slug, "name": group["name"]},
            ))
            print(f"V2 shared-group report: {output}")


if __name__ == "__main__":
    main()
