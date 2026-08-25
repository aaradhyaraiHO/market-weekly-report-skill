#!/usr/bin/env python3
"""
Granola → Review bridge (the upstream trigger for auto-ingest).

Granola does not push, so something must feed meetings to /api/granola-review. This bridge takes a
list of meetings, matches each to a CE using the week's snapshot, and POSTs {meeting, matches} to the
review endpoint. Exact single matches auto-attach as pending suggestions in the CE's Review tab;
ambiguous/none land in the reconciliation inbox (fail-safe — never silently attached to the wrong CE).

Meeting source (Granola's local cache + token are encrypted, so not read here) — feed meetings via:
  1. A Claude scheduled agent that calls the Granola MCP (list_meetings + get_meeting_transcript),
     writes meetings.json, then runs this bridge with --apply.  ← the intended automated loop
  2. Manual: --meetings meetings.json  (or pipe JSON on stdin)
  3. --self-test : a built-in sample meeting (no Granola needed) to prove the chain end-to-end.

meetings.json = [{ "id","title","summary"|"notes","url"?,"author"?,"occurred_at"? }, ...]

Usage:
  python3 granola_bridge.py --market north_america --week 2026-08-09 --self-test           # dry-run
  python3 granola_bridge.py --market all --week 2026-08-09 --meetings meetings.json --apply
Env:
  WR_GRANOLA_WEBHOOK_SECRET   required for --apply (matches Vercel GRANOLA_WEBHOOK_SECRET)
  WR_REVIEW_BASE              default https://market-notebook.vercel.app
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]


def _resolve_cache() -> Path:
    """Snapshots live in the analytics repo's .cache; the skill worktree has none of its own."""
    for cand in (os.environ.get("WR_CACHE_DIR"),
                 REPO_ROOT / ".cache" / "weekly_report",
                 Path(os.path.expanduser("~/analytics/.cache/weekly_report"))):
        if cand and Path(cand).exists() and any(Path(cand).glob("snapshot_*.json")):
            return Path(cand)
    return REPO_ROOT / ".cache" / "weekly_report"


CACHE_DIR = _resolve_cache()
BASE = os.environ.get("WR_REVIEW_BASE", "https://market-notebook.vercel.app")

STOPWORDS = {"tour", "tours", "ticket", "tickets", "the", "and", "of", "de", "la", "el", "experience"}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(text or "").lower())).strip()


def load_ce_index(markets: list[str], week: str) -> dict[str, list[dict]]:
    """market_slug -> [{ce_id, ce_name, norm, tokens}] from the week's snapshot."""
    index: dict[str, list[dict]] = {}
    try:
        import config
        market_list = list(config.MARKETS) if markets == ["all"] else markets
    except Exception:
        market_list = markets
    for slug in market_list:
        snap = CACHE_DIR / f"snapshot_{slug}_{week}.json"
        if not snap.exists():
            print(f"  ! no snapshot for {slug} {week} — skipping that market")
            continue
        data = json.loads(snap.read_text())
        rows = data.get("ces") or data.get("all_ces") or []
        out = []
        for ce in rows:
            name = ce.get("ce_name") or ""
            norm = _norm(name)
            if not norm:
                continue
            tokens = [t for t in norm.split(" ") if len(t) >= 4 and t not in STOPWORDS]
            out.append({"ce_id": str(ce.get("ce_id")), "ce_name": name, "norm": norm, "tokens": tokens})
        index[slug] = out
        print(f"  · {slug}: {len(out)} CEs indexed")
    return index


def match_meeting(meeting: dict, index: dict[str, list[dict]], week: str) -> list[dict]:
    """Return matches[] for a meeting. Conservative: only a single strong name hit is 'exact'."""
    text = _norm((meeting.get("title") or "") + " . " + (meeting.get("summary") or meeting.get("notes") or ""))
    hits: list[dict] = []
    for slug, ces in index.items():
        for ce in ces:
            confidence = ""
            # whole normalized CE name present as a phrase (strongest)
            if len(ce["norm"]) >= 6 and re.search(r"\b" + re.escape(ce["norm"]) + r"\b", text):
                confidence = "high"
            else:
                # else require >=2 distinctive tokens to co-occur
                strong = [t for t in ce["tokens"] if re.search(r"\b" + re.escape(t) + r"\b", text)]
                if len(strong) >= 2:
                    confidence = "medium"
            if confidence:
                hits.append({"market_slug": slug, "week_start": week, "ce_id": ce["ce_id"],
                             "ce_name": ce["ce_name"], "confidence": confidence})
    # dedupe by (market, ce_id)
    seen, uniq = set(), []
    for h in sorted(hits, key=lambda x: 0 if x["confidence"] == "high" else 1):
        key = (h["market_slug"], h["ce_id"])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(h)
    high = [h for h in uniq if h["confidence"] == "high"]
    # A single full-CE-name phrase hit is decisive → exact (auto-attach), even if weaker token
    # matches also fired (e.g. "Space Center Houston" sharing tokens with "Kennedy Space Center").
    if len(high) == 1:
        high[0]["match_status"] = "exact"
        return high
    # 2+ full-name hits, or only weaker token matches → ambiguous → reconciliation inbox (fail-safe).
    for h in uniq:
        h["match_status"] = "ambiguous"
    return uniq


def clean_meeting(m: dict) -> dict:
    mid = str(m.get("id") or m.get("meeting_id") or "").strip()
    body = str(m.get("summary") or m.get("notes") or "").strip()
    if not mid or not body:
        raise ValueError("each meeting needs an id and summary/notes")
    return {"id": mid, "title": str(m.get("title") or "Granola meeting"),
            "summary": body, "url": m.get("url") or f"https://notes.granola.ai/t/{mid}",
            "author": m.get("author") or m.get("note_taker") or "Granola",
            "occurred_at": m.get("occurred_at") or m.get("date") or ""}


def post(meeting: dict, matches: list[dict]) -> tuple[bool, str]:
    secret = os.environ.get("WR_GRANOLA_WEBHOOK_SECRET")
    if not secret:
        return False, "WR_GRANOLA_WEBHOOK_SECRET not set"
    body = json.dumps({"meeting": meeting, "matches": matches}).encode()
    req = urllib.request.Request(f"{BASE}/api/granola-review", data=body, method="POST",
                                 headers={"content-type": "application/json", "x-granola-secret": secret})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, resp.read().decode()
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return False, str(e)


SAMPLE = [{
    "id": "granola-selftest-001", "title": "KSC partnership meeting", "author": "Pari",
    "occurred_at": "2026-08-11",
    "summary": "Kennedy Space Center's new marketing team wants to prioritise three side-letter actions. "
               "B2B reselling is approved but hybrid fulfilment and Galaxy implications remain open. "
               "Action: draft the side-letter recap and connect with Danny. Revisit promo CVR next week.",
}]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Granola → Review bridge (match meetings to CEs, POST to /api/granola-review)")
    ap.add_argument("--market", required=True, help="market slug or 'all'")
    ap.add_argument("--week", required=True, help="week Monday YYYY-MM-DD (matches the snapshot)")
    ap.add_argument("--meetings", help="path to meetings JSON (list); omit to read stdin unless --self-test")
    ap.add_argument("--self-test", action="store_true", help="use a built-in sample meeting")
    ap.add_argument("--apply", action="store_true", help="actually POST (default: dry-run)")
    ap.add_argument("--base", help="review base URL (default $WR_REVIEW_BASE)")
    args = ap.parse_args(argv)
    global BASE
    if args.base:
        BASE = args.base

    if args.self_test:
        meetings = SAMPLE
    elif args.meetings:
        meetings = json.loads(Path(args.meetings).read_text())
    else:
        raw = sys.stdin.read().strip()
        if not raw:
            sys.exit("no meetings: pass --meetings, pipe JSON, or use --self-test")
        meetings = json.loads(raw)
    if isinstance(meetings, dict):
        meetings = [meetings]

    markets = ["all"] if args.market == "all" else [args.market]
    print(f"Granola bridge · week {args.week} · {args.market} · {len(meetings)} meeting(s) · "
          f"{'APPLY' if args.apply else 'DRY-RUN'} · {BASE}")
    index = load_ce_index(markets, args.week)
    if not index:
        sys.exit("no CE index — run the weekly producer first so snapshots exist")

    posted = 0
    for m in meetings:
        try:
            meeting = clean_meeting(m)
        except ValueError as e:
            print(f"  ! skipping meeting: {e}")
            continue
        matches = match_meeting(meeting, index, args.week)
        exact = [x for x in matches if x.get("match_status") == "exact"]
        label = (f"→ EXACT {exact[0]['ce_name']} (CE {exact[0]['ce_id']}, {exact[0]['market_slug']})"
                 if exact else f"→ {len(matches)} ambiguous / inbox" if matches else "→ no CE match (inbox)")
        print(f"\n  “{meeting['title']}” [{meeting['id']}] {label}")
        for x in matches[:6]:
            print(f"      · {x['match_status']:9} {x['confidence']:6} {x['ce_name']} (CE {x['ce_id']}, {x['market_slug']})")
        if args.apply:
            ok, msg = post(meeting, matches)
            print(f"      {'✓ posted' if ok else '✗ ' + msg}")
            posted += 1 if ok else 0
        else:
            print("      (dry-run — add --apply to POST; needs WR_GRANOLA_WEBHOOK_SECRET)")

    if args.apply:
        print(f"\n  posted {posted}/{len(meetings)} meeting(s) to {BASE}/api/granola-review")
    else:
        print(f"\n  dry-run complete. Re-run with --apply once WR_GRANOLA_WEBHOOK_SECRET is set.")


if __name__ == "__main__":
    main()
