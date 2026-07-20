#!/usr/bin/env python3
"""Edit an already-posted WEEKLY alert IN PLACE via chat.update — parents AND the
3 bucket-table thread replies (Losing Money / RPC Fluctuations ↓ / ↑).

The monthly update_posts.py only touches top-level messages; the weekly format
tweaks (action prompt + prominent link) live in the bucket-table thread replies,
so this also fetches those replies (conversations.replies) and updates each,
matched by header text. RCA thread replies are unchanged and left alone.

Usage:
    export REVENUE_ALERT_SLACK_TOKEN="xoxb-…"
    python3 update_posts_weekly.py --payload payload.json --channel <CID> \
        --msg1-ts <summary_ts> --msg2-ts <movers_ts> [--dry-run]

Blocks in the payload are already Block Kit — passed through as-is.
"""
import argparse, json, os, sys, time, urllib.request, urllib.parse

API = "https://slack.com/api/"


def call(method, token, payload, get=False):
    if get:
        url = API + method + "?" + urllib.parse.urlencode(payload)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    else:
        req = urllib.request.Request(
            API + method, data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def htext(b):
    tx = b.get("text")
    return tx.get("text", "") if isinstance(tx, dict) else (tx or "")


def header_of(blocks):
    return next((htext(b) for b in blocks if b.get("type") == "header"), "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload", required=True)
    ap.add_argument("--channel", required=True)
    ap.add_argument("--msg1-ts", required=True, help="summary (MSG1) parent ts")
    ap.add_argument("--msg2-ts", required=True, help="movers (MSG2) parent ts")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("REVENUE_ALERT_SLACK_TOKEN")
    if not token and not args.dry_run:
        sys.exit("Set REVENUE_ALERT_SLACK_TOKEN (or use --dry-run).")

    p = json.loads(open(args.payload).read())
    m1, m2 = p["messages"][0], p["messages"][1]
    tables = m1.get("threads", [])          # 3 bucket-table replies (Block Kit)

    bot_id = None
    if token:
        a = call("auth.test", token, {}, get=True)
        bot_id = a.get("user_id")

    def upd(ts, blocks, label):
        if args.dry_run:
            print(f"  [dry-run] chat.update {label} ts={ts} ({len(blocks)} blocks)")
            return
        r = call("chat.update", token, {"channel": args.channel, "ts": ts, "blocks": blocks})
        print(f"  {'✅' if r.get('ok') else '❌ '+str(r.get('error'))} {label} ts={ts}")
        time.sleep(1)

    # 1) parents
    upd(args.msg1_ts, m1["blocks"], "MSG1 summary")
    upd(args.msg2_ts, m2["blocks"], "MSG2 movers")

    # 2) the 3 bucket-table thread replies — fetch, match by header, update
    if args.dry_run and not token:
        for t in tables:
            print(f"  [dry-run] would update thread reply: {header_of(t['blocks'])!r}")
        return
    rep = call("conversations.replies", token, {"channel": args.channel, "ts": args.msg1_ts, "limit": 200}, get=True)
    # MSG1's thread contains ONLY the bucket tables, in the order they were posted
    # (Losing Money → Fluctuations ↓ → ↑) — same order as payload tables. Match by
    # index (header text can't be compared: Slack returns :shortcode: vs the
    # payload's unicode emoji).
    replies = [msg for msg in rep.get("messages", [])
               if msg.get("ts") != args.msg1_ts and (bot_id is None or msg.get("user") == bot_id)]
    if len(replies) != len(tables):
        print(f"  ⚠️  {len(replies)} thread replies vs {len(tables)} payload tables — "
              "aborting thread update to avoid mismatched edits.")
        return
    for msg, t in zip(replies, tables):
        h = header_of(t["blocks"])
        upd(msg["ts"], t["blocks"], f"thread: {h}")


if __name__ == "__main__":
    main()
