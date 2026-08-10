#!/usr/bin/env python3
"""
Post the weekly "close-the-loop" follow-ups to each market channel, THREADED under
that market's Monday alert (anchor from posted_ledger.json), via the alert bot.

Reads alert/followup_drafts_<week>.json (produced by followup_actioning.py).

SAFETY: dry-run by default — prints what it WOULD post and validates every anchor.
Pass --live to actually post. Needs REVENUE_ALERT_SLACK_TOKEN in the env for --live.

  # preview (no token needed):
  python3 post_followups.py --week 2026-07-20

  # real post (token in env):
  REVENUE_ALERT_SLACK_TOKEN="xoxb-…" python3 post_followups.py --week 2026-07-20 --live
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent

BOT_USERNAME = "Monthly Market Review"      # same identity as the Monday alerts
BOT_ICON = ":bar_chart:"


def post(token, channel, text, thread_ts):
    import requests
    payload = {
        "channel": channel, "text": text, "thread_ts": thread_ts,
        "username": BOT_USERNAME, "icon_emoji": BOT_ICON,
        "unfurl_links": False, "unfurl_media": False,
    }
    r = requests.post("https://slack.com/api/chat.postMessage",
                      headers={"Authorization": f"Bearer {token}",
                               "Content-Type": "application/json; charset=utf-8"},
                      data=json.dumps(payload), timeout=15)
    return r.json()


def update(token, channel, ts, text):
    import requests
    payload = {"channel": channel, "ts": ts, "text": text,
               "link_names": True, "unfurl_links": False, "unfurl_media": False}
    r = requests.post("https://slack.com/api/chat.update",
                      headers={"Authorization": f"Bearer {token}",
                               "Content-Type": "application/json; charset=utf-8"},
                      data=json.dumps(payload), timeout=15)
    return r.json()


def permalink(token, channel, ts):
    import requests
    try:
        j = requests.get("https://slack.com/api/chat.getPermalink",
                         headers={"Authorization": f"Bearer {token}"},
                         params={"channel": channel, "message_ts": ts}, timeout=10).json()
        return j.get("permalink") if j.get("ok") else None
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default="2026-07-20")
    ap.add_argument("--live", action="store_true", help="actually post (default: dry-run)")
    ap.add_argument("--update", action="store_true",
                    help="edit already-posted messages (from followup_posted_<week>.json) with the current draft text")
    ap.add_argument("--only", help="comma-separated market slugs to limit to")
    args = ap.parse_args()

    data = json.loads((HERE / f"followup_drafts_{args.week}.json").read_text())
    drafts = data["drafts"]
    only = set(s.strip() for s in args.only.split(",")) if args.only else None

    token = os.environ.get("REVENUE_ALERT_SLACK_TOKEN")
    if (args.live or args.update) and not token:
        sys.exit("REVENUE_ALERT_SLACK_TOKEN not set — export it for --live/--update.")

    if args.update:
        posted = json.loads((HERE / f"followup_posted_{args.week}.json").read_text())
        print(f"\n{'='*60}\nUPDATE · week {args.week} · {len(posted)} posted messages\n{'='*60}")
        for p in posted:
            slug = p["market"]
            if only and slug not in only:
                continue
            text = drafts[slug]["text"]
            res = update(token, p["channel"], p["ts"], text)
            mk = drafts[slug]["market"]
            print(f"  {'✓' if res.get('ok') else '✗'} {mk:16s} {'updated' if res.get('ok') else res.get('error')}")
            time.sleep(1.2)
        return

    # pre-flight: every market must have an anchor to thread under
    missing = [s for s, d in drafts.items() if not d.get("thread_ts")]
    if missing:
        print(f"⚠ no Monday anchor for: {missing} — these would post fresh (skipped).")

    mode = "LIVE" if args.live else "DRY-RUN"
    print(f"\n{'='*60}\n{mode} · week {args.week} · {len(drafts)} markets\n{'='*60}")
    posted = []
    for slug, d in drafts.items():
        if only and slug not in only:
            continue
        if not d.get("thread_ts"):
            print(f"  ⏭ {d['market']}: no anchor — SKIP"); continue
        ch, ts, chars = d["channel"], d["thread_ts"], len(d["text"])
        if not args.live:
            print(f"  • {d['market']:16s} → thread {ch}/{ts} · {d['n_ces']} CEs · {chars} chars")
            continue
        res = post(token, ch, d["text"], ts)
        if res.get("ok"):
            link = permalink(token, ch, res["ts"]) or "(no link)"
            print(f"  ✓ {d['market']:16s} posted → {link}")
            posted.append({"market": slug, "ts": res["ts"], "channel": ch, "link": link})
        else:
            print(f"  ✗ {d['market']:16s} FAILED: {res.get('error')}")
        time.sleep(1.2)   # gentle rate limit

    if args.live and posted:
        outp = HERE / f"followup_posted_{args.week}.json"
        outp.write_text(json.dumps(posted, indent=2))
        print(f"\nposted-ledger written -> {outp.name}")
    if not args.live:
        print("\n(dry-run — nothing posted. add --live to send.)")


if __name__ == "__main__":
    main()
