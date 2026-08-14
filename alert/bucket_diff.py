#!/usr/bin/env python3
"""Bucket-change verifier — diff a market's §4 buckets between two weekly reports.

Given an OLD report (what's currently deployed / what the live Slack alert
reflects) and a NEW report (freshly re-rendered), report what changed in the
three alert buckets so a later in-place alert update (update_posts_weekly.py) is
warranted only where the bucket set actually moved — and can say what moved.

Buckets compared (buckets_final):
  - Losing Money  = defend.losing_money.existing + .new (v2 criteria; keyed by ce_id)
  - Fluctuations ↓ = defend.seasonality_down
  - Fluctuations ↑ = compound.seasonality_up

Per bucket it reports CEs ADDED, REMOVED, and MATERIALLY CHANGED (status flip for
Losing Money; swing_pct / dominant-driver / verdict shift for Fluctuations).

Usage:
    python3 bucket_diff.py --old <old_report.html> --new <new_report.html> [--slug <slug>]
    python3 bucket_diff.py --old ... --new ... --json           # machine-readable
    # loop all markets in the deploy dir vs freshly-rendered thoughts/ copies:
    python3 bucket_diff.py --old-dir <deploy_dir> --new-dir <report_dir> --week 2026-07-13

Exit code 0; prints a summary. `changed` is true in the JSON when any bucket moved.
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORT_DIR = HERE.parent / "scripts" / "weekly_report"
sys.path.insert(0, str(REPORT_DIR))
import bucket_views  # noqa: E402

SWING_EPS = 5.0  # pp — |swing_pct| move below this is noise, not a "material" change


def load_markets(html_path: Path) -> dict:
    """slug → market dict, from a report's embedded report-data JSON."""
    raw = html_path.read_text(encoding="utf-8")
    m = re.search(r'<script[^>]*id="report-data"[^>]*>', raw)
    if not m:
        raise SystemExit(f"no report-data script in {html_path}")
    s = m.end(); e = raw.find("</script>", s)
    data = json.loads(raw[s:e])
    return {mk["meta"].get("market_slug", str(i)): mk for i, mk in enumerate(data["markets"])}


def _losing(mk: dict) -> dict:
    rows = bucket_views.final_losing_money_rows(mk)
    return {str(r.get("ce_id")): {"name": r.get("ce_name"),
                                  "status": r.get("label") or "flagged",
                                  "roi": r.get("roi_wk")}
            for r in rows}


def _fluct(mk: dict, direction: str) -> dict:
    rows = bucket_views.final_fluctuation_rows(mk, direction)
    return {str(r.get("ce_id")): {"name": r.get("ce_name"), "swing_pct": r.get("swing_pct"),
                                  "dominant": r.get("dominant_key"), "verdict": r.get("verdict")}
            for r in rows}


def _diff(old: dict, new: dict, material) -> dict:
    added = [{"ce_id": k, **new[k]} for k in new if k not in old]
    removed = [{"ce_id": k, **old[k]} for k in old if k not in new]
    changed = []
    for k in new:
        if k in old:
            why = material(old[k], new[k])
            if why:
                changed.append({"ce_id": k, "name": new[k].get("name"), "change": why})
    return {"added": added, "removed": removed, "changed": changed,
            "n_added": len(added), "n_removed": len(removed), "n_changed": len(changed)}


def _lm_material(o, n):
    return f"status {o['status']} → {n['status']}" if o.get("status") != n.get("status") else None


def _fl_material(o, n):
    reasons = []
    os_, ns_ = o.get("swing_pct"), n.get("swing_pct")
    if os_ is not None and ns_ is not None and abs(ns_ - os_) >= SWING_EPS:
        reasons.append(f"swing {os_:+.0f}%→{ns_:+.0f}%")
    if o.get("dominant") != n.get("dominant"):
        reasons.append(f"driver {o.get('dominant')}→{n.get('dominant')}")
    if o.get("verdict") != n.get("verdict"):
        reasons.append("verdict changed")
    return "; ".join(reasons) or None


def diff_market(old_mk: dict, new_mk: dict) -> dict:
    lm = _diff(_losing(old_mk), _losing(new_mk), _lm_material)
    dn = _diff(_fluct(old_mk, "down"), _fluct(new_mk, "down"), _fl_material)
    up = _diff(_fluct(old_mk, "up"), _fluct(new_mk, "up"), _fl_material)
    changed = any(b["n_added"] or b["n_removed"] or b["n_changed"] for b in (lm, dn, up))
    return {"changed": changed, "losing_money": lm, "fluct_down": dn, "fluct_up": up}


def _fmt_bucket(title: str, b: dict) -> str:
    if not (b["n_added"] or b["n_removed"] or b["n_changed"]):
        return f"  {title}: no change"
    lines = [f"  {title}: +{b['n_added']} / -{b['n_removed']} / ~{b['n_changed']}"]
    for r in b["added"]:
        lines.append(f"    + [{r['ce_id']}] {r.get('name')}")
    for r in b["removed"]:
        lines.append(f"    - [{r['ce_id']}] {r.get('name')}")
    for r in b["changed"]:
        lines.append(f"    ~ [{r['ce_id']}] {r.get('name')} — {r['change']}")
    return "\n".join(lines)


def print_market(slug: str, d: dict) -> None:
    flag = "CHANGED" if d["changed"] else "unchanged"
    print(f"\n=== {slug} · {flag} ===")
    print(_fmt_bucket("Losing Money", d["losing_money"]))
    print(_fmt_bucket("Fluctuations ↓", d["fluct_down"]))
    print(_fmt_bucket("Fluctuations ↑", d["fluct_up"]))


def main() -> None:
    ap = argparse.ArgumentParser(description="Diff §4 buckets between two weekly reports")
    ap.add_argument("--old", help="old/deployed report HTML")
    ap.add_argument("--new", help="new/re-rendered report HTML")
    ap.add_argument("--slug", default=None, help="market slug (single-market files: optional)")
    ap.add_argument("--old-dir", help="deploy dir (weekly-report-<slug>.html) — loop all markets")
    ap.add_argument("--new-dir", help="report dir (report_<slug>_<week>.html) — loop all markets")
    ap.add_argument("--week", default=None, help="week-Monday, required with --new-dir")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    results: dict[str, dict] = {}

    if args.old_dir and args.new_dir:
        if not args.week:
            ap.error("--week is required with --old-dir/--new-dir")
        old_dir, new_dir = Path(args.old_dir), Path(args.new_dir)
        # ledger slug (deploy file) uses hyphens; producer file uses config slug (underscores).
        for old_f in sorted(old_dir.glob("weekly-report-*.html")):
            ledger_slug = old_f.stem.replace("weekly-report-", "")
            new_f = new_dir / f"report_{ledger_slug.replace('-', '_')}_{args.week}.html"
            if not new_f.exists():
                print(f"  (skip {ledger_slug}: no new render at {new_f.name})")
                continue
            old_mk = next(iter(load_markets(old_f).values()))
            new_mk = next(iter(load_markets(new_f).values()))
            results[ledger_slug] = diff_market(old_mk, new_mk)
    elif args.old and args.new:
        old = load_markets(Path(args.old)); new = load_markets(Path(args.new))
        slug = args.slug or next(iter(new))
        old_mk = old.get(slug) or next(iter(old.values()))
        new_mk = new.get(slug) or next(iter(new.values()))
        results[slug] = diff_market(old_mk, new_mk)
    else:
        ap.error("pass either --old/--new or --old-dir/--new-dir")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        for slug, d in results.items():
            print_market(slug, d)
        changed = [s for s, d in results.items() if d["changed"]]
        print(f"\n{'─'*50}\n{len(changed)}/{len(results)} market(s) changed: "
              f"{', '.join(changed) or 'none'}")


if __name__ == "__main__":
    main()
