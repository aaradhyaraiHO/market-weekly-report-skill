#!/usr/bin/env python3
"""
Render the Weekly Market Report V1 — inject a data payload into the
self-contained HTML template and write a single interactive report file.

Inputs may be either:
  * the multi-market BUNDLE from make_sample_data.py ({"markets": [...]}), or
  * one or more per-market snapshot files as wt-weekly-data emits
    (each `snapshot_{slug}_{week}.json` following schema v1),

and are normalized to one payload so the report gets market-switcher tabs.

Usage
-----
  python render.py                          # sample_data.json -> report, then --open
  python render.py snapshot_na_2026-06-29.json snapshot_it_2026-06-29.json
  python render.py --glob '.cache/weekly_report/snapshot_*_2026-06-29.json'
  python render.py sample_data.json --out /tmp/report.html --no-open
"""
import argparse
import glob as globmod
import json
import os
import subprocess
import sys

from config import NOTES_SCRIPT_URL, NOTES_SLACK_CHANNELS

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "template", "report_template.html")
DEFAULT_INPUT = os.path.join(HERE, "sample_data.json")
# repo root = two levels up from scripts/weekly_report/
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(REPO_ROOT, "thoughts", "shared", "weekly-report-v1")


def load_markets(paths):
    """Return an ordered, de-duplicated list of per-market snapshot dicts."""
    markets = []
    seen = set()
    for p in paths:
        with open(p) as f:
            obj = json.load(f)
        snaps = obj["markets"] if isinstance(obj, dict) and "markets" in obj else [obj]
        for s in snaps:
            meta = s.get("meta", {})
            slug = meta.get("market_slug") or meta.get("market") or f"market_{len(markets)}"
            key = (slug, meta.get("week_start"))
            if key in seen:
                print(f"  · skip duplicate market snapshot: {slug} {meta.get('week_start')}")
                continue
            seen.add(key)
            _validate(s, p)
            # Robustness: pick up the S3 Slack-signal sidecar at RENDER time when present, so a
            # re-render always reflects the latest digest. build_snapshot's loader only runs at
            # build time — if the snapshot was built before the sidecar was written (S3 runs
            # after the build), a plain re-render would otherwise drop the cards.
            ms, wk = meta.get("market_slug"), meta.get("week_start")
            if ms and wk:
                side = os.path.join(os.path.dirname(os.path.abspath(p)),
                                    f"slack_context_{ms}_{wk}.json")
                if os.path.exists(side):
                    try:
                        s["market_review_context"] = json.load(open(side))
                    except (json.JSONDecodeError, OSError):
                        pass
                # Perf action-history sidecar (per report-week, keyed by CID across ALL markets) →
                # CE-drawer Action log shows PERF's final actions (the decisions of record).
                ph = os.path.join(os.path.dirname(os.path.abspath(p)), f"perf_hist_{wk}.json")
                if os.path.exists(ph):
                    try:
                        _ph = json.load(open(ph))
                        for _ce in s.get("ces", []):
                            _ce["perf_action_hist"] = _ph.get(str(_ce.get("ce_id")), [])
                    except (json.JSONDecodeError, OSError):
                        pass
            markets.append(s)
    if not markets:
        sys.exit("No market snapshots found in the given inputs.")
    return markets


def _validate(snap, src):
    """Light contract sanity checks — surface obvious wiring mistakes early."""
    for key in ("meta", "market_summary", "ces"):
        if key not in snap:
            print(f"  ! WARNING [{os.path.basename(src)}]: missing top-level '{key}'")
    weeks = snap.get("meta", {}).get("weeks", [])
    if weeks and len(weeks) != 12:
        print(f"  ! WARNING [{snap['meta'].get('market')}]: {len(weeks)} weeks "
              f"(V1 expects 12)")
    for ce in snap.get("ces", [])[:1]:
        w = ce.get("weekly", [{}])[-1]
        if "yoy_pct" not in w:
            print(f"  ! WARNING: ces[].weekly missing 'yoy_pct' — Section 3 YoY "
                  f"column will render '—'. (see plan schema amendment)")


def out_path(markets):
    m0 = markets[0]["meta"]
    week = m0.get("week_start", "week")
    if len(markets) == 1:
        slug = m0.get("market_slug") or "market"
        return os.path.join(OUT_DIR, f"report_{slug}_{week}.html")
    return os.path.join(OUT_DIR, f"report_multi_{week}.html")


def render(markets, template_path):
    with open(template_path) as f:
        html = f.read()
    notes_url = os.environ.get("WR_NOTES_SCRIPT_URL") or NOTES_SCRIPT_URL
    payload = {
        "schema_version": markets[0]["meta"].get("schema_version", 1),
        "markets": markets,
        "notes_url": notes_url or None,
        "actions_url": "/api/actions",
        "notes_channels": NOTES_SLACK_CHANNELS,
    }
    # escape '<' so a stray '</script>' in data can never close the tag early
    data_json = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    names = " · ".join(m["meta"].get("market", "?") for m in markets)
    week = markets[0]["meta"].get("week_start", "")
    title = f"Weekly Ledger — {names} — w/c {week}"
    html = html.replace("__REPORT_DATA_JSON__", data_json)
    html = html.replace("__TITLE__", title)
    return html


def main():
    ap = argparse.ArgumentParser(description="Render Weekly Market Report V1")
    ap.add_argument("inputs", nargs="*", help="snapshot / bundle JSON files")
    ap.add_argument("--glob", help="glob pattern for snapshot files")
    ap.add_argument("--out", help="output HTML path (default under thoughts/shared/weekly-report-v1/)")
    ap.add_argument("--open", dest="open_", action="store_true", default=None,
                    help="open the report when done (default: on)")
    ap.add_argument("--no-open", dest="open_", action="store_false")
    args = ap.parse_args()

    paths = list(args.inputs)
    if args.glob:
        paths += sorted(globmod.glob(args.glob))
    if not paths:
        paths = [DEFAULT_INPUT]

    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        sys.exit(f"Input(s) not found: {', '.join(missing)}")

    print(f"Rendering from: {', '.join(os.path.basename(p) for p in paths)}")
    markets = load_markets(paths)
    print(f"  markets: {[m['meta'].get('market') for m in markets]}")

    html = render(markets, TEMPLATE)
    out = args.out or out_path(markets)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        f.write(html)
    print(f"  wrote: {out}  ({len(html)//1024} KB)")

    open_it = True if args.open_ is None else args.open_
    if open_it:
        try:
            if sys.platform == "darwin":
                subprocess.run(["open", out], check=False)
            elif sys.platform.startswith("linux"):
                subprocess.run(["xdg-open", out], check=False)
            print("  opened in default browser")
        except Exception as e:
            print(f"  (could not auto-open: {e})")


if __name__ == "__main__":
    main()
