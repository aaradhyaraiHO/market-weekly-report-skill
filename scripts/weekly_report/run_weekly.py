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

    python3 run_weekly.py <market|all> --week YYYY-MM-DD --stage alert \
      [--alert-version v1|v2] [--post]
      → per market: weekly_alert → weekly_rca_helper (BigQuery) → post_message.
        V1 remains the default fallback. V2 consumes a live V2 report, builds
        the current market-grain OKR sidecar, then uses the same delivery layer.
        Dry-run by default; --post posts to each market's real channel
        (needs REVENUE_ALERT_SLACK_TOKEN).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ALERT = REPO / "alert"
ALERT_V2 = ALERT / "v2"
CACHE = REPO / ".cache" / "weekly_report"
REPORTS = REPO / "thoughts" / "shared" / "weekly-report-v1"
REPORTS_V2 = REPO / "thoughts" / "shared" / "weekly-report-v2"
BGM_CONFIG = ALERT_V2 / "market_bgms.json"
POSTED_LEDGER = ALERT / "posted_ledger.json"
SHARED_REPORT_MARKETS = {"csee", "nordics"}

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
def stage_report(slugs, week, renderer="v1"):
    print(f"\n═══ S2 · build + render ({len(slugs)} market(s), week {week}) ═══")
    target = "all" if len(slugs) == len(config.MARKETS) else slugs[0] if len(slugs) == 1 else None
    if target:
        command = ["python3", "weekly_market_report.py", target, "--week", week]
        if renderer != "v1":
            command.extend(["--renderer", renderer])
        run([*command, "--no-open"], cwd=HERE)
    else:
        for s in slugs:
            command = ["python3", "weekly_market_report.py", s, "--week", week]
            if renderer != "v1":
                command.extend(["--renderer", renderer])
            run([*command, "--no-open"], cwd=HERE)
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


def stage_publish(slugs, week, renderer="v1"):
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
        if renderer == "v1":
            run(["python3", "render.py", str(snap), "--no-open"], cwd=HERE)
        else:
            run(["python3", "release_v2.py", str(snap),
                 "--fetch-goals",
                 "--out-dir", str(REPO / "thoughts" / "shared" / "weekly-report-v2"),
                 "--manifest", str(CACHE / f"v2_release_{s}_{week}.json")], cwd=HERE)
    target = "all" if len(slugs) == len(config.MARKETS) else None
    if target:
        run(["python3", "publish_weekly.py", "all", "--week", week,
             "--renderer", renderer], cwd=HERE)
    else:
        run(["python3", "publish_weekly.py", *slugs, "--week", week,
             "--renderer", renderer], cwd=HERE, check=False)
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
        rc = run(["python3", "weekly_rca_helper.py", "--ce-ids", ids, "--week-start", week,
                  "--week-end", week_end, "--out", str(rca)], cwd=ALERT, check=False)
        if rc != 0:
            print(f"  ⚠ {s}: RCA query failed (byte cap?) — posting summary WITHOUT RCA threads")
            rca.write_text("{}")   # post_message skips unresolved $rca refs; MSG1 still posts
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


def stage_alert_v2(slugs, week, post):
    """Build and deliver the isolated V2 alert without changing the V1 path."""
    print(f"\n═══ S5 · Slack alert V2 ({'LIVE POST' if post else 'dry-run'}) ═══")
    bgm_config = json.loads(BGM_CONFIG.read_text()).get("markets", {})
    missing_bgms = [slug for slug in slugs if not (bgm_config.get(slug) or {}).get("slack_user_ids")]
    if missing_bgms:
        raise SystemExit(
            "V2 alert blocked: no approved BGM Slack IDs for " + ", ".join(missing_bgms)
        )

    channels = json.loads((ALERT / "market_channels.json").read_text()).get("markets", {})
    missing_channels = [slug for slug in slugs if not channels.get(slug)]
    if missing_channels:
        raise SystemExit(
            "V2 alert blocked: no V1 channel route for " + ", ".join(missing_channels)
        )

    reports = {slug: REPORTS_V2 / f"report_{slug}_{week}.html" for slug in slugs}
    missing_reports = [slug for slug, path in reports.items() if not path.exists()]
    if missing_reports:
        raise SystemExit(
            "V2 alert blocked: live V2 report is missing for " + ", ".join(missing_reports)
        )

    if post:
        if not os.environ.get("REVENUE_ALERT_SLACK_TOKEN"):
            raise SystemExit(
                "V2 alert blocked: REVENUE_ALERT_SLACK_TOKEN is not set in the runtime"
            )
        ledger = {}
        if POSTED_LEDGER.exists():
            try:
                ledger = json.loads(POSTED_LEDGER.read_text()).get(week, {})
            except (json.JSONDecodeError, OSError):
                raise SystemExit(
                    f"V2 alert blocked: cannot safely read duplicate ledger {POSTED_LEDGER}"
                )
        duplicates = [
            slug for slug in slugs
            if (ledger.get(slug) or {}).get("msg1_ts")
            or (ledger.get(slug) or {}).get("msg2_ts")
        ]
        if duplicates:
            raise SystemExit(
                "V2 alert blocked: already posted for this week: " + ", ".join(duplicates)
            )
        raise SystemExit(
            'Direct V2 posting is disabled. Use run_v2_release.py and its verified frozen '
            'delivery bundle; resume with alert/v2/safe_delivery.py after live verification.'
        )

    print(f"  ✓ batch preflight passed for {len(slugs)} market(s); no Slack writes started")
    week_end = _week_end(week)
    okr_results = CACHE / f"_okr_results_v2_{week}.json"
    okr_rc = run(
        ["python3", "build_market_okr_results.py", "--week-start", week, "--out", str(okr_results)],
        cwd=ALERT_V2,
        check=False,
    )
    okr_ready = okr_rc == 0 and okr_results.exists()
    if not okr_ready:
        print("  ⚠ V2 OKR enrichment unavailable — continuing without the optional OKR block")

    for slug in slugs:
        report = reports[slug]
        print(f"\n── {slug} · V2 ──")
        payload = CACHE / f"_alert_payload_v2_{slug}.json"
        rca = CACHE / f"_alert_rca_v2_{slug}.json"
        build_cmd = [
            "python3", "weekly_alert_v2.py", "--file", str(report),
            "--market-slug", slug, "--week-start", week,
            "--bgms", str(BGM_CONFIG), "--out", str(payload),
        ]
        if slug in SHARED_REPORT_MARKETS:
            build_cmd.extend([
                "--report-url",
                f"https://market-notebook.vercel.app/weekly-report-csee-nordics-{week}?market={slug}",
            ])
        if okr_ready:
            build_cmd.extend(["--okr-results", str(okr_results)])
        run(build_cmd, cwd=ALERT_V2)

        handoff = json.loads(payload.read_text()).get("_rca", {})
        ids = ",".join(str(value) for value in handoff.get("ce_ids", []))
        rca_rc = run(
            ["python3", "weekly_rca_helper.py", "--ce-ids", ids,
             "--week-start", week, "--week-end", week_end, "--out", str(rca)],
            cwd=ALERT,
            check=False,
        )
        if rca_rc != 0:
            print(f"  ⚠ {slug}: RCA query failed — V2 parents remain sendable without CE threads")
            rca.write_text("{}")

        post_cmd = [
            "python3", "post_message.py", "--payload", str(payload),
            "--rca-blocks", str(rca), "--slug", slug, "--week", week,
        ]
        if post:
            run([*post_cmd, "--channel", channels[slug]], cwd=ALERT)
        else:
            run([*post_cmd, "--dry-run"], cwd=ALERT)
    if not post:
        print("\n  V2 dry-run complete. Standalone --post is disabled; follow docs/v2/release-workflow.md "
              "for verified frozen delivery through run_v2_release.py.")


def _week_end(week):
    import datetime
    d = datetime.date.fromisoformat(week)
    return (d + datetime.timedelta(days=6)).isoformat()


def main():
    ap = argparse.ArgumentParser(description="Weekly run driver (staged)")
    ap.add_argument("market", help="market slug or 'all'")
    ap.add_argument("--week", required=True, help="W0 week-start = SUNDAY (YYYY-MM-DD); snapped to its Sun–Sat week")
    ap.add_argument("--stage", required=True, choices=["report", "publish", "alert"])
    ap.add_argument("--renderer", choices=["v1", "v2", "both"], default="v1",
                    help="(report stage only) render V1, V2, or both from shared snapshots")
    ap.add_argument("--post", action="store_true", help="(alert stage) post live instead of dry-run")
    ap.add_argument(
        "--alert-version", choices=["v1", "v2"], default="v1",
        help="Alert renderer for --stage alert; V1 stays the default rollback path",
    )
    args = ap.parse_args()
    import datetime as _dt
    args.week = config.iso(config._week_start(_dt.date.fromisoformat(args.week)))   # ensure Sun-Sat across all stages

    slugs = slugs_for(args.market)
    if args.stage == "report":
        stage_report(slugs, args.week, args.renderer)
    elif args.stage == "publish":
        if args.renderer == "both":
            sys.exit("Publish one renderer at a time: choose --renderer v1 or --renderer v2.")
        stage_publish(slugs, args.week, args.renderer)
    elif args.stage == "alert":
        if args.alert_version == "v2":
            stage_alert_v2(slugs, args.week, args.post)
        else:
            stage_alert(slugs, args.week, args.post)


if __name__ == "__main__":
    main()
