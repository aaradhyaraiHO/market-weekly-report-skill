#!/usr/bin/env python3
"""Thursday EOD actions-summary ping — Task 1 of HANDOFF-ping-and-sheet-export.md.

Per pilot market, for the current report week, joins the flagged Losing-Money set
against the actions store and posts to the market channel:
  • ACTIONED — CEs with a recorded action, most-severe first: CE · action · owner · comment
  • REVIEW THESE — flagged CEs with NO action or an empty comment (loud section)

Flagged set source = the producer snapshot `.cache/weekly_report/snapshot_<slug>_<week>.json`
(buckets_final.defend.losing_money.{existing,new}); the same data the report renders.
Actions store = notes Sheet via `?action=action_list&market=&week=` (bucket == 'losing_money').

GUARD: live posting is publish-only-from-main. --dry-run (default) just prints; --post
requires the main checkout (or WR_ALLOW_WORKTREE_POST=1 to override for a test channel).

Usage:
    python3 thursday_actions_ping.py --slug italy --dry-run
    python3 thursday_actions_ping.py --all --dry-run
    python3 thursday_actions_ping.py --all --post            # from main only
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "scripts" / "weekly_report"))
import config  # noqa: E402  (weekly_report/config.py — NOTES_SCRIPT_URL, week helpers)

CACHE = REPO / ".cache" / "weekly_report"
CHANNELS = json.loads((HERE / "market_channels.json").read_text())
LM_BUCKET = "losing_money"
COMMENT_MAX = 140

# action status (template dropdown value) -> human label
ACTION_LABELS = {
    "negative_seasonality": "−ve seasonality",
    "roas_change": "tROAS change",
    "scale_down": "Scale down",
    "pause": "Pause",
    "pause_review": "Pause & review",
    "no_change": "No change",
    "skip": "Skip",
    "intentional": "Intentional",
}


# --------------------------------------------------------------------------- #
# actions store (read) — mirrors notes.fetch_notes but the action_list verb
# --------------------------------------------------------------------------- #
def fetch_actions(market_slug: str, week: str) -> dict[str, dict]:
    """{ce_id: {status, note, owner, updated}} for bucket==losing_money, this market+week.
    Empty dict if the backend is unreachable (fail-soft — the ping still names the flagged set)."""
    base = os.environ.get("WR_NOTES_SCRIPT_URL") or config.NOTES_SCRIPT_URL
    if not base:
        return {}
    q = urllib.parse.urlencode({"action": "action_list", "market": market_slug, "week": week})
    try:
        with urllib.request.urlopen(base + "?" + q, timeout=15) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        print(f"  ! actions fetch failed ({market_slug} {week}): {e}", file=sys.stderr)
        return {}
    out = {}
    for a in data.get("actions", []):
        if a.get("bucket") != LM_BUCKET or not a.get("ce_id"):
            continue
        out[str(a["ce_id"])] = {"status": a.get("status", "") or "", "note": a.get("note", "") or "",
                                "owner": a.get("owner", "") or "", "updated": a.get("updated", "") or ""}
    return out


# --------------------------------------------------------------------------- #
# flagged set (read) — from the producer snapshot
# --------------------------------------------------------------------------- #
def flagged_rows(slug: str, week: str) -> list[dict] | None:
    """Losing-Money flagged CEs (existing + new) for one market-week, worst first.
    None if the snapshot is missing (build/publish hasn't run for this week)."""
    p = CACHE / f"snapshot_{slug}_{week}.json"
    if not p.exists():
        return None
    lm = (((json.loads(p.read_text()).get("buckets_final") or {})
           .get("defend") or {}).get("losing_money") or {})
    rows = (lm.get("existing") or []) + (lm.get("new") or [])
    for r in rows:
        wk0 = (r.get("weeks") or [{}])[0]
        r["_cm2_w0"] = wk0.get("cm2")
        # sort_delta is the worst fired Δ (most negative). Fall back to this week's CM2.
        r["_sev"] = r.get("sort_delta") if r.get("sort_delta") is not None else r.get("_cm2_w0")
    rows.sort(key=lambda r: (r.get("_sev") if r.get("_sev") is not None else 0))
    return rows


# --------------------------------------------------------------------------- #
# message
# --------------------------------------------------------------------------- #
def _money(v):
    if v is None:
        return "—"
    a = abs(v); s = "−" if v < 0 else ""
    return f"{s}${a/1000:.1f}k" if a >= 1000 else f"{s}${round(a)}"


def _trunc(s, n=COMMENT_MAX):
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def build_blocks(slug: str, week: str, rows: list[dict], actions: dict[str, dict]) -> tuple[list[dict], dict]:
    """Returns (slack_blocks, counts). Actioned = a recorded status; review = no action or empty comment."""
    actioned, review = [], []
    for r in rows:
        cid = str(r.get("ce_id"))
        a = actions.get(cid)
        has_action = bool(a and a.get("status"))
        has_comment = bool(a and a.get("note"))
        if has_action and has_comment:
            actioned.append((r, a))
        else:
            review.append((r, a, has_action, has_comment))

    def line_actioned(r, a):
        lab = ACTION_LABELS.get(a["status"], a["status"])
        owner = f" · {a['owner']}" if a.get("owner") else ""
        return (f"• *{r.get('ce_name')}*  {_money(r.get('_cm2_w0'))}/wk  →  *{lab}*{owner}\n"
                f"    _{_trunc(a.get('note'))}_")

    def line_review(r, a, has_action, has_comment):
        why = "no action" if not has_action else "action but *no comment*"
        return f"• *{r.get('ce_name')}*  {_money(r.get('_cm2_w0'))}/wk  — _{why}_"

    blocks = [{"type": "header", "text": {"type": "plain_text",
              "text": "Losing Money — actions this week"}},
              {"type": "context", "elements": [{"type": "mrkdwn",
               "text": f"{slug} · week of {week} · {len(rows)} flagged · "
                       f"{len(actioned)} actioned · {len(review)} to review"}]}]
    if actioned:
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": "*✅ Actioned*\n" + "\n".join(line_actioned(r, a) for r, a in actioned)}})
    if review:
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": "*⚠️ Review these — no action or empty comment*\n"
                               + "\n".join(line_review(*x) for x in review)}})
    return blocks, {"flagged": len(rows), "actioned": len(actioned), "review": len(review)}


def _dry_print(slug, blocks, counts):
    print(f"\n===== {slug}  (flagged {counts['flagged']} · actioned {counts['actioned']} · review {counts['review']}) =====")
    for b in blocks:
        t = b.get("text", {})
        if b["type"] == "divider":
            print("  " + "-" * 40)
        elif "text" in t:
            print("  " + t["text"].replace("\n", "\n  "))
        elif b["type"] == "context":
            print("  " + b["elements"][0]["text"])


def _on_main() -> bool:
    try:
        return subprocess.run(["git", "-C", str(REPO), "rev-parse", "--abbrev-ref", "HEAD"],
                              capture_output=True, text=True).stdout.strip() == "main"
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_argument_group()
    ap.add_argument("--slug", help="single market slug")
    ap.add_argument("--all", action="store_true", help="all markets in market_channels.json")
    ap.add_argument("--week", default=config.iso(config.latest_complete_week()),
                    help="report week start (Sun); default = latest complete week")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--post", dest="dry_run", action="store_false", help="actually post to Slack")
    args = ap.parse_args()

    slugs = ([args.slug] if args.slug
             else [k for k in CHANNELS if not k.startswith("_")] if args.all
             else [])
    if not slugs:
        ap.error("pass --slug <slug> or --all")

    if not args.dry_run and not _on_main() and os.environ.get("WR_ALLOW_WORKTREE_POST") != "1":
        sys.exit("REFUSING to post from a non-main checkout (publish-only-from-main). "
                 "Run from main, or set WR_ALLOW_WORKTREE_POST=1 for a test channel.")

    for slug in slugs:
        rows = flagged_rows(slug, args.week)
        if rows is None:
            print(f"  ! no snapshot for {slug} {args.week} — build/publish first; skipping", file=sys.stderr)
            continue
        if not rows:
            print(f"  · {slug}: 0 flagged CEs — no ping")
            continue
        actions = fetch_actions(slug, args.week)
        blocks, counts = build_blocks(slug, args.week, rows, actions)
        if args.dry_run:
            _dry_print(slug, blocks, counts)
        else:
            # TODO(next): post via post_message.post_message_chunked(token, channel, blocks)
            #   channel = CHANNELS[slug]; token = env REVENUE_ALERT_SLACK_TOKEN. Ledger-guard
            #   against double-posting the same market-week (see alert/posted_ledger.json).
            print(f"  [post path not wired yet] {slug}: would post {counts}", file=sys.stderr)


if __name__ == "__main__":
    main()
