#!/usr/bin/env python3
"""Weekly run driver — chains the deterministic steps, pausing at the two
human/agent gates (S3 Slack-digest curation, the vercel deploy, the live post).

It does NOT try to be one magic command: S3 (curation) needs agents and the
deploy/post are human-gated. Instead it runs the scriptable glue in three stages,
each ending with the exact next action to take.

    python3 run_weekly.py <market|all> --week YYYY-MM-DD --stage report
      → builds + renders every market (S2). Prints which markets need a Slack
        digest sidecar (S3) before publish.

    # --- S3: fan out one digest agent per market → writes
    #     .cache/weekly_report/slack_context_{slug}_{week}.json ---

    python3 run_weekly.py <market|all> --week YYYY-MM-DD --stage publish
      → for each market with a sidecar, rebuilds the snapshot (loads the digest)
        + re-renders; then stages the Ledger (publish_weekly). Prints the vercel
        deploy command for the USER.

    # --- USER runs: vercel deploy --prod --cwd market-notebook-v2 ---

    python3 run_weekly.py <market|all> --week YYYY-MM-DD --stage alert [--post]
      → per market: weekly_alert → weekly_rca_helper (BigQuery) → post_message.
        Dry-run by default; --post posts to each market's real channel
        (needs REVENUE_ALERT_SLACK_TOKEN).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ALERT = REPO / "alert"
CACHE = REPO / ".cache" / "weekly_report"
REPORTS = REPO / "thoughts" / "shared" / "weekly-report-v1"

sys.path.insert(0, str(HERE))
import config  # noqa: E402


def run(cmd, cwd=None, check=True):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, cwd=cwd)
    if check and r.returncode != 0:
        sys.exit(f"  ✗ command failed ({r.returncode})")
    return r.returncode


def slugs_for(target):
    if target == "all":
        return list(config.MARKETS.keys())
    if target == "headout":
        return ["headout"]
    if target not in config.MARKETS:
        sys.exit(f"unknown market '{target}'. Known: {', '.join(config.MARKETS)}, headout")
    return [target]


def report_path(slug, week):
    return REPORTS / f"report_{slug}_{week}.html"


def sidecar_path(slug, week):
    return CACHE / f"slack_context_{slug}_{week}.json"


# --------------------------------------------------------------------------- #
def stage_report(slugs, week):
    print(f"\n═══ S2 · build + render ({len(slugs)} market(s), week {week}) ═══")
    target = "all" if len(slugs) == len(config.MARKETS) else slugs[0] if len(slugs) == 1 else None
    if target:
        run(["python3", "weekly_market_report.py", target, "--week", week, "--no-open"], cwd=HERE)
    else:
        for s in slugs:
            run(["python3", "weekly_market_report.py", s, "--week", week, "--no-open"], cwd=HERE)
    missing = [s for s in slugs if not sidecar_path(s, week).exists()]
    print("\n── NEXT (S3 · Slack digest, agent step) ──")
    if missing:
        print(f"  Fan out one digest agent per market to curate its sidecar + return the market team:")
        for s in missing:
            print(f"    • {s} → {sidecar_path(s, week).name}")
        print(f"  Each agent reads its market channel + globals for the week window, writes the sidecar")
        print(f"  (card schema in alert/README + SKILL S3), validates ce_id against the snapshot.")
    else:
        print(f"  All {len(slugs)} sidecars already present ✓")
    print(f"\n  Then:  python3 run_weekly.py {'all' if target=='all' else ' '.join(slugs)} --week {week} --stage publish")


def stage_publish(slugs, week):
    print(f"\n═══ S3-reload + S4.5 · rebuild (load digests) + publish ═══")
    for s in slugs:
        if sidecar_path(s, week).exists():
            if s == "headout":
                run(["python3", "build_global.py", "--week", week], cwd=HERE)
            else:
                run(["python3", "build_snapshot.py", "--market", s, "--week", week], cwd=HERE)
        else:
            print(f"  ⚠ {s}: no sidecar — rendering without a digest")
        snap = CACHE / f"snapshot_{s}_{week}.json"
        run(["python3", "render.py", str(snap), "--no-open"], cwd=HERE)
    target = "all" if len(slugs) == len(config.MARKETS) else None
    if target:
        run(["python3", "publish_weekly.py", "all", "--week", week], cwd=HERE)
    else:
        run(["python3", "publish_weekly.py", *slugs, "--week", week], cwd=HERE, check=False)
    print("\n── NEXT (S4.5 deploy · USER runs, interactive auth) ──")
    print("  ! vercel deploy --prod --cwd market-notebook-v2      # from ~/analytics")
    print(f"\n  Then:  python3 run_weekly.py {'all' if target else ' '.join(slugs)} --week {week} --stage alert   # add --post to go live")


def stage_alert(slugs, week, post):
    print(f"\n═══ S5 · Slack alert ({'LIVE POST' if post else 'dry-run'}) ═══")
    channels = json.loads((ALERT / "market_channels.json").read_text()).get("markets", {})
    week_end = _week_end(week)
    for s in slugs:
        rpt = report_path(s, week)
        if not rpt.exists():
            print(f"  ⚠ {s}: no report at {rpt.name} — skipping"); continue
        print(f"\n── {s} ──")
        payload = CACHE / f"_alert_payload_{s}.json"
        rca = CACHE / f"_alert_rca_{s}.json"
        run(["python3", "weekly_alert.py", "--file", str(rpt), "--market-slug", s, "--out", str(payload)], cwd=ALERT)
        ids = ",".join(json.loads(payload.read_text())["_rca"]["ce_ids"])
        run(["python3", "weekly_rca_helper.py", "--ce-ids", ids, "--week-start", week,
             "--week-end", week_end, "--out", str(rca)], cwd=ALERT)
        cmd = ["python3", "post_message.py", "--payload", str(payload), "--rca-blocks", str(rca)]
        if post:
            ch = channels.get(s)
            if not ch:
                print(f"  ⚠ no channel for {s} in market_channels.json — skipping post"); continue
            run([*cmd, "--channel", ch], cwd=ALERT)
        else:
            run([*cmd, "--dry-run"], cwd=ALERT)
    if not post:
        print(f"\n  Reviewed the dry-runs? Re-run with --post to go live (needs REVENUE_ALERT_SLACK_TOKEN).")


def _week_end(week):
    import datetime
    d = datetime.date.fromisoformat(week)
    return (d + datetime.timedelta(days=6)).isoformat()


def main():
    ap = argparse.ArgumentParser(description="Weekly run driver (staged)")
    ap.add_argument("market", help="market slug or 'all'")
    ap.add_argument("--week", required=True, help="W0 week-start = SUNDAY (YYYY-MM-DD); snapped to its Sun–Sat week")
    ap.add_argument("--stage", required=True, choices=["report", "publish", "alert"])
    ap.add_argument("--post", action="store_true", help="(alert stage) post live instead of dry-run")
    args = ap.parse_args()
    import datetime as _dt
    args.week = config.iso(config._week_start(_dt.date.fromisoformat(args.week)))   # ensure Sun-Sat across all stages

    slugs = slugs_for(args.market)
    if args.stage == "report":
        stage_report(slugs, args.week)
    elif args.stage == "publish":
        stage_publish(slugs, args.week)
    elif args.stage == "alert":
        stage_alert(slugs, args.week, args.post)


if __name__ == "__main__":
    main()
