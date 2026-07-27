#!/usr/bin/env python3
"""One-shot: update all 10 per-market weekly alerts IN PLACE with the eroders-inclusive
Losing Money table. Parents + 3 bucket tables via chat.update (no new messages).

Pre-staged this session:
  /tmp/market_parents.json     — {slug: {channel, msg1, msg2}} (discovered from each channel)
  /tmp/payload_<slug>.json     — rebuilt payloads from the re-rendered (eroders) reports
Dry-run validated on north_america (parents + 3 tables matched by ts).

Run:  export REVENUE_ALERT_SLACK_TOKEN="xoxb-…"; python3 run_market_alert_sweep.py [--dry-run]
"""
import json, subprocess, os, sys

WEEK = "2026-07-13"
DRY = "--dry-run" in sys.argv
HERE = os.path.dirname(os.path.abspath(__file__))
parents = json.load(open("/tmp/market_parents.json"))
env = os.environ.copy()
if not env.get("REVENUE_ALERT_SLACK_TOKEN") and not DRY:
    sys.exit("export REVENUE_ALERT_SLACK_TOKEN first (or pass --dry-run)")


def _verify_deploy_current(old_dir, new_dir):
    """Gate against report↔alert drift (2026-07-27): before sweeping, confirm the DEPLOYED
    report matches the freshly-rendered one for this week. If any market's §4 buckets differ,
    the live report is stale relative to what we'd push to Slack — abort so the operator
    re-deploys first (make the sweep the FINAL step, sourced from the deployed report)."""
    r = subprocess.run(["python3", os.path.join(HERE, "bucket_diff.py"),
                        "--old-dir", old_dir, "--new-dir", new_dir, "--week", WEEK, "--json"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"verify: bucket_diff failed —\n{r.stderr or r.stdout}")
    diff = json.loads(r.stdout)
    stale = [s for s, d in diff.items() if d.get("changed")]
    if stale:
        sys.exit(f"verify FAILED — deployed report is stale vs fresh render for: "
                 f"{', '.join(stale)}.\nRe-deploy the current report, THEN re-run the sweep.")
    print(f"  verify OK — deployed report == fresh render ({len(diff)} markets)")


# --verify <deployed_dir> <fresh_render_dir> : hard gate before any chat.update
if "--verify" in sys.argv:
    i = sys.argv.index("--verify")
    try:
        _verify_deploy_current(sys.argv[i + 1], sys.argv[i + 2])
    except IndexError:
        sys.exit("--verify needs two dirs: --verify <deployed_dir> <fresh_render_dir>")

for slug, info in parents.items():
    ch, m1, m2 = info["channel"], info["msg1"], info["msg2"]
    payload = f"/tmp/payload_{slug}.json"
    if not (m1 and m2 and os.path.exists(payload)):
        print(f"  {slug:16s} — missing ts/payload, SKIP"); continue
    cmd = ["python3", "update_posts_weekly.py", "--payload", payload,
           "--channel", ch, "--msg1-ts", m1, "--msg2-ts", m2] + (["--dry-run"] if DRY else [])
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    out = "\n".join(l for l in r.stdout.splitlines() if "new_ce_tracker" not in l)
    status = "OK" if (out.count("✅") >= 2 and "⚠️" not in out and "❌" not in out) else "CHECK"
    print(f"  {slug:16s} {status}")
    if status == "CHECK":
        print("    " + out.replace("\n", "\n    "))
print("sweep complete" + (" (dry-run)" if DRY else ""))
