"""
Slack Message Poster  (thin delivery layer)
===========================================

Reads a JSON payload authored by Claude (see MESSAGE_SPEC.md) and posts it:
  - the `parent` blocks as a top-level message
  - each `threads[]` entry as a threaded reply, in order

Claude writes the content; this script only delivers it. It:
  - expands the tiny block vocabulary (section/header/context/divider) to Block Kit
  - injects the report link into the parent (from --report-url)
  - auto-splits sections over Slack's ~3000-char limit
  - auto-chunks any message over Slack's 50-block limit
  - handles thread ordering + rate-limit pacing

USAGE:
    export REVENUE_ALERT_SLACK_TOKEN="xoxb-..."

    # From a payload file
    python post_message.py --payload payload.json --report-url "https://…" --dry-run
    python post_message.py --payload payload.json --report-url "https://…"

    # Or pipe the payload in
    cat payload.json | python post_message.py --report-url "https://…"
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests

TEST_CHANNEL_NAME = "#revenue-alert-testing"
TEST_CHANNEL_ID   = "C0B6U94PGJ0"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("post_message")

SECTION_CHAR_LIMIT = 2900   # Slack section text hard limit is 3000; leave headroom
BLOCKS_PER_MESSAGE = 45     # Slack limit is 50; leave headroom
HEADER_CHAR_LIMIT  = 150    # Slack header hard limit


# =============================================================================
# BLOCK EXPANSION  (tiny vocabulary → Block Kit)
# =============================================================================

def _split_text(text: str, limit: int = SECTION_CHAR_LIMIT) -> list[str]:
    """Split a long mrkdwn string on line boundaries into <=limit chunks.
    Never splits inside a ``` code fence (keeps fenced tables intact)."""
    if len(text) <= limit:
        return [text]
    chunks, cur = [], ""
    in_fence = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_fence = not in_fence
        # +1 for the newline we'll rejoin with
        if len(cur) + len(line) + 1 > limit and cur and not in_fence:
            chunks.append(cur.rstrip("\n"))
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur.rstrip("\n"))
    return chunks


def expand_block(b: dict) -> list[dict]:
    """Expand one tiny-vocabulary block into one or more Block Kit blocks.
    Blocks that are ALREADY real Block Kit (e.g. from rca_helper.py, where
    `text` is a dict or the block has `elements`) are passed through as-is."""
    t = b.get("type")

    # Pass-through: already-real Block Kit (helper output)
    if isinstance(b.get("text"), dict) or "elements" in b:
        return [b]

    if t == "divider":
        return [{"type": "divider"}]

    if t == "header":
        text = (b.get("text") or "")[:HEADER_CHAR_LIMIT]
        return [{"type": "header", "text": {"type": "plain_text", "text": text, "emoji": True}}]

    if t == "context":
        return [{"type": "context", "elements": [{"type": "mrkdwn", "text": b.get("text", "")}]}]

    if t == "section":
        out = []
        for chunk in _split_text(b.get("text", "")):
            out.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
        return out

    raise ValueError(f"Unknown block type: {t!r} (allowed: section/header/context/divider)")


def expand_blocks(blocks: list[dict]) -> list[dict]:
    out: list[dict] = []
    for b in blocks:
        out.extend(expand_block(b))
    return out


def chunk_blocks(blocks: list[dict], size: int = BLOCKS_PER_MESSAGE) -> list[list[dict]]:
    """Chunk a block list into <=size-block messages (Slack's per-message cap)."""
    return [blocks[i:i + size] for i in range(0, len(blocks), size)] or [[]]


# =============================================================================
# PAYLOAD VALIDATION
# =============================================================================

def validate_payload(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")
    # Two accepted shapes:
    #   {"parent": [...], "threads": [...]}            — single message + replies
    #   {"messages": [{"blocks": [...], "threads": [...]}, ...]}  — many messages
    if "messages" in payload:
        if not isinstance(payload["messages"], list):
            raise ValueError("'messages' must be a list")
        for i, m in enumerate(payload["messages"]):
            if "blocks" not in m or not isinstance(m["blocks"], list):
                raise ValueError(f"messages[{i}] must have a 'blocks' list")
    elif "parent" in payload:
        if not isinstance(payload["parent"], list):
            raise ValueError("'parent' must be a list of blocks")
    else:
        raise ValueError("Payload must have either 'messages' or 'parent'")


def resolve_threads(threads: list[dict], rca_blocks: dict) -> list[dict]:
    """Resolve any {"$rca": "<ce_id>"} thread entries to the helper's blocks."""
    out = []
    for th in threads or []:
        if "$rca" in th:
            ce_id = str(th["$rca"])
            entry = rca_blocks.get(ce_id)
            if entry is None:
                log.warning("  $rca reference %s not found in --rca-blocks — skipping", ce_id)
                continue
            out.append(entry)
        else:
            out.append(th)
    return out


def resolve_blocks(blocks: list[dict], tables: dict) -> list[dict]:
    """Resolve any {"$table": "<key>"} block refs to the extractor's table block."""
    out = []
    for b in blocks or []:
        if "$table" in b:
            key = str(b["$table"])
            entry = tables.get(key)
            if entry is None:
                log.warning("  $table reference %s not found in --tables — skipping", key)
                continue
            out.append(entry["block"])
        else:
            out.append(b)
    return out


# =============================================================================
# SLACK POSTING
# =============================================================================

def slack_post(token: str, channel: str, blocks: list[dict],
               thread_ts: str | None = None, fallback_text: str = "Market alert") -> dict:
    payload = {
        "channel": channel, "blocks": blocks, "text": fallback_text,
        "username": "Monthly Market Review", "icon_emoji": ":bar_chart:",
    }
    if thread_ts:
        payload["thread_ts"] = thread_ts
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        data=json.dumps(payload), timeout=15,
    )
    body = resp.json()
    if not body.get("ok"):
        log.error("Slack post failed: %s", body)
    return body


def slack_update(token: str, channel: str, ts: str, blocks: list[dict],
                 fallback_text: str = "Market alert") -> dict:
    resp = requests.post(
        "https://slack.com/api/chat.update",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        data=json.dumps({"channel": channel, "ts": ts, "blocks": blocks, "text": fallback_text}),
        timeout=15,
    )
    body = resp.json()
    if not body.get("ok"):
        log.error("Slack update failed: %s", body)
    return body


def get_permalink(token: str, channel: str, ts: str) -> str | None:
    """Fetch a message permalink (for the summary to link to)."""
    try:
        r = requests.get("https://slack.com/api/chat.getPermalink",
                         headers={"Authorization": f"Bearer {token}"},
                         params={"channel": channel, "message_ts": ts}, timeout=10)
        j = r.json()
        return j.get("permalink") if j.get("ok") else None
    except Exception:
        return None


def post_message_chunked(token: str, channel: str, blocks: list[dict],
                         thread_ts: str | None, fallback_text: str) -> str | None:
    """Post a (possibly >50-block) message, chunking as needed. When posting a
    top-level message, returns the ts of the FIRST chunk (the thread anchor)."""
    anchor_ts = thread_ts
    first_ts = None
    for chunk in chunk_blocks(blocks):
        resp = slack_post(token, channel, chunk, thread_ts=anchor_ts, fallback_text=fallback_text)
        if not resp.get("ok"):
            return first_ts
        ts = resp["ts"]
        if first_ts is None:
            first_ts = ts
        # If this was a top-level post, subsequent chunks thread under it
        if anchor_ts is None:
            anchor_ts = ts
        time.sleep(0.4)
    return first_ts


# =============================================================================
# REPORT LINK INJECTION
# =============================================================================

def inject_report_link(parent_blocks: list[dict], report_url: str | None) -> list[dict]:
    """Append a context block with the report link + thread pointer to the parent."""
    pointer = "🧵  _Each bucket detailed in thread_"
    if report_url:
        pointer = f"📎  <{report_url}|Open full report>   ·   {pointer}"
    return parent_blocks + [{"type": "context", "text": pointer}]


# =============================================================================
# DRY-RUN PRINTER
# =============================================================================

def print_expanded(blocks: list[dict], label: str = "") -> None:
    if label:
        print(f"\n{'='*70}\n  {label}\n{'='*70}\n")
    for b in expand_blocks(blocks):
        t = b["type"]
        if t == "header":
            txt = b["text"]["text"]
            print("━" * max(len(txt) + 4, 30)); print(f"  {txt}"); print("━" * max(len(txt) + 4, 30)); print()
        elif t == "section":
            print(b["text"]["text"]); print()
        elif t == "divider":
            print("─" * 60)
        elif t == "context":
            for el in b.get("elements", []):
                print(f"  {el['text']}")
            print()


# =============================================================================
# ENTRY POINT
# =============================================================================

def normalize_to_messages(payload: dict, report_url: str | None) -> list[dict]:
    """Return a uniform list of message-groups: [{fallback, blocks, threads}].
    The {parent, threads} shape becomes a single group (with the report link
    injected into the parent)."""
    if "messages" in payload:
        return payload["messages"]
    parent = inject_report_link(payload["parent"], report_url)
    return [{"fallback": "Monthly Market Review", "blocks": parent,
             "threads": payload.get("threads", [])}]


def main() -> None:
    parser = argparse.ArgumentParser(description="Post a Claude-authored message payload to Slack")
    parser.add_argument("--payload", help="Path to the JSON payload file (omit to read from stdin)")
    parser.add_argument("--channel", default=TEST_CHANNEL_ID,
                        help=f"Slack channel ID or #name (default: {TEST_CHANNEL_ID} = #revenue-alert-testing)")
    parser.add_argument("--report-url", default=None, help="Hosted report URL — linked in the parent (parent shape only)")
    parser.add_argument("--rca-blocks", default=None, help="JSON file of precomputed RCA blocks (from rca_helper.py) for $rca refs")
    parser.add_argument("--tables", default=None, help="JSON file of extracted bucket tables (from tables_helper.py) for $table refs")
    parser.add_argument("--update", default=None,
                        help="Comma-separated parent message timestamps to update in-place (one per message group)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load payload (file or stdin)
    raw = Path(args.payload).expanduser().read_text(encoding="utf-8") if args.payload else sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        log.error("Payload is not valid JSON: %s", e); sys.exit(1)

    try:
        validate_payload(payload)
    except ValueError as e:
        log.error("Invalid payload: %s", e); sys.exit(1)

    rca_blocks = {}
    if args.rca_blocks:
        rca_blocks = json.loads(Path(args.rca_blocks).expanduser().read_text(encoding="utf-8"))
    tables = {}
    if args.tables:
        tables = json.loads(Path(args.tables).expanduser().read_text(encoding="utf-8"))

    messages = normalize_to_messages(payload, args.report_url)
    # Resolve $table refs in every message's blocks up front
    for m in messages:
        m["blocks"] = resolve_blocks(m["blocks"], tables)

    # ----- Dry-run -----
    if args.dry_run:
        for m in messages:
            print_expanded(m["blocks"], label=f"MESSAGE — {m.get('fallback','')}")
            for th in resolve_threads(m.get("threads", []), rca_blocks):
                print_expanded(th["blocks"], label=f"  └─ THREAD — {th.get('fallback','')}")
        log.info("Dry-run OK: %d message(s)", len(messages))
        return

    # ----- Real post / update -----
    token = os.environ.get("REVENUE_ALERT_SLACK_TOKEN")
    if not token:
        log.error("REVENUE_ALERT_SLACK_TOKEN not set — export it or use --dry-run"); sys.exit(1)

    update_ts = args.update.split(",") if args.update else []
    if update_ts and len(update_ts) != len(messages):
        log.error("--update needs %d timestamps (one per message group), got %d", len(messages), len(update_ts))
        sys.exit(1)

    permalinks = []
    for i, m in enumerate(messages):
        fb = m.get("fallback", "message")
        blocks = expand_blocks(m["blocks"])

        if update_ts:
            parent_ts = update_ts[i].strip()
            log.info("Updating message: %s (ts=%s)", fb, parent_ts)
            for chunk in chunk_blocks(blocks):
                resp = slack_update(token, args.channel, parent_ts, chunk, fallback_text=fb)
                if not resp.get("ok"):
                    break
                time.sleep(0.4)
            link = get_permalink(token, args.channel, parent_ts)
            permalinks.append((fb, link))
            log.info("  ✅ updated: ts=%s  link=%s", parent_ts, link)
            ts = parent_ts
        else:
            log.info("Posting message: %s", fb)
            ts = post_message_chunked(token, args.channel, blocks,
                                      thread_ts=None, fallback_text=fb)
            if not ts:
                log.warning("  ❌ message post failed — skipping its threads"); continue
            link = get_permalink(token, args.channel, ts)
            permalinks.append((fb, link))
            log.info("  ✅ posted: ts=%s  link=%s", ts, link)

        if not update_ts:
            time.sleep(1)
            for th in resolve_threads(m.get("threads", []), rca_blocks):
                tfb = th.get("fallback", "reply")
                log.info("    → thread: %s", tfb)
                post_message_chunked(token, args.channel, expand_blocks(th["blocks"]),
                                     thread_ts=ts, fallback_text=tfb)
                time.sleep(0.6)

    log.info("🎉 Done — %d message(s) %s", len(messages), "updated" if update_ts else "posted")
    if permalinks:
        log.info("Permalinks (for the summary to link):")
        for fb, link in permalinks:
            log.info("  • %s → %s", fb, link)


if __name__ == "__main__":
    main()
