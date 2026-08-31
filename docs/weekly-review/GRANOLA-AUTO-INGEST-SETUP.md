# Granola auto-ingest — setup runbook

## Current product status · 31 Aug 2026

The guarded ingestion contracts are implemented in the repository, but Granola
is **not part of the core Review launch** and is not authorized for production
activation yet. Activate it only after the manual Slack/BGM Review workflow has
been stable in production for 24–48 hours.

The beta contract is intentionally suggestion-only:

- an exact `market_slug + review_week + stable CE ID` match may create pending
  comment/action/check suggestions;
- ambiguous or unmatched items go to `review_source_inbox`;
- a BGM must approve, edit or reject every suggestion;
- nothing posts automatically to Slack;
- nothing writes automatically to the legacy Losing Money/RPC tables;
- retries are idempotent and retain the Granola link/transcript provenance.

A later Losing Money/RPC extension should surface approved Granola suggestions
beside the matching CE row and require an explicit BGM write through the existing
legacy action/comment contract. It must not add a second writer or change
`/api/actions`, `action_upsert` or `action_delete`.

Turns the deployed `/api/granola-review` endpoint into a live pipeline: a Granola meeting →
AI-extracted, source-linked comment/action/check suggestions → the Review tab's Granola card
(exact CE match) or the reconciliation inbox (ambiguous/unmatched). Nothing enters CE Memory,
commentary or work automatically; a BGM still approves every suggestion.

**Secrets are NOT stored in this repo.** Claude relayed the generated values in chat — paste those.
Never commit them or embed them in report HTML.

## Chain
```
Granola meeting  ──(POST {meeting,matches}, header x-granola-secret)──►  /api/granola-review
   │  per exact match: POST /api/review-summary (mode source_suggestions, header x-review-secret)  → Anthropic (Haiku)
   ▼
Apps Script  review_source_ingest (ingest_secret)  ──►  review_source_suggestions | review_source_inbox
   ▼
Review tab → Commentary / Actions Granola card (pending, BGM approves)
```

## 1. Vercel env vars  (Project → Settings → Environment Variables → Production)
| Var | Purpose | Value |
|-----|---------|-------|
| `GRANOLA_WEBHOOK_SECRET`      | auth for the inbound webhook (`x-granola-secret`) | *(from chat)* |
| `REVIEW_MODE_INGEST_SECRET`   | sent to Apps Script; **must equal** the Apps Script property below | *(secret store)* |
| `REVIEW_MODE_AI_WEBHOOK_SECRET` | shared secret between granola-review and review-summary | *(secret store)* |
| `REVIEW_MODE_AI_WEBHOOK_URL`  | authenticated Review summary/extraction endpoint | *(deployment URL)* |
| `ANTHROPIC_API_KEY`           | Haiku extraction in review-summary.js | *(likely already set — verify)* |
| `REVIEW_AI_MODEL`             | optional; default `claude-haiku-4-5-20251001` | *(leave unset)* |
| `REVIEW_MODE_APPS_SCRIPT_URL` | isolated Review Apps Script deployment URL | *(deployment URL)* |

## 2. Apps Script property  (Extensions → Apps Script → Project Settings → Script properties)
- `REVIEW_MODE_INGEST_SECRET` = **the same value** you set on Vercel above.
- Then redeploy the web app: Deploy → Manage deployments → New version.

## 3. Redeploy Vercel
```
vercel deploy --prod --cwd market-notebook-v2      # from ~/analytics, after setting env vars
```

## 4. Smoke test the full chain (fires one meeting through; lands as a pending suggestion)
```sh
curl -sS https://market-notebook.vercel.app/api/granola-review \
  -H "content-type: application/json" \
  -H "x-granola-secret: $GRANOLA_WEBHOOK_SECRET" \
  -d '{
    "meeting": {"id":"selftest-001","title":"KSC partnership meeting",
      "summary":"KSC wants to prioritise three side-letter actions. Draft the recap and connect with Danny. Revisit promo CVR next week.",
      "author":"Pari","occurred_at":"2026-08-11"},
    "matches": [{"market_slug":"north_america","week_start":"2026-08-09","ce_id":"3111","ce_name":"Kennedy Space Center","match_status":"exact","confidence":"high"}]
  }'
# expect: {"ok":true,"meeting_id":"selftest-001","exact_matches":1,...}
```
Then open the NA report → Review → Kennedy Space Center → the Granola card shows the pending
comment + action suggestions. Reject/approve to confirm the write path. (A wrong secret → 401.)

## 5. The upstream trigger — `granola_bridge.py` (built)
Granola does not push on its own, so something must POST `{meeting, matches}`. The bridge is
`scripts/weekly_report/granola_bridge.py`: it matches each meeting to a CE using the week's snapshot
and POSTs to `/api/granola-review`. Dry-run by default; `--apply` posts (needs `WR_GRANOLA_WEBHOOK_SECRET`).

- **Match contract:** a single full-CE-name phrase hit → `match_status:"exact"` (auto-attaches as a
  pending suggestion). 2+ name hits or token-only matches → `ambiguous` → reconciliation inbox
  (never silently attached to the wrong CE). Verified: "KSC partnership meeting" → EXACT Kennedy
  Space Center (CE 3111), not the token-colliding "Space Center Houston".

```sh
# dry-run (no secret needed) — see how meetings would match
python3 scripts/weekly_report/granola_bridge.py --market north_america --week 2026-08-09 --self-test
# real run for a market (needs the current-week snapshot + secret)
WR_GRANOLA_WEBHOOK_SECRET=… python3 scripts/weekly_report/granola_bridge.py \
    --market all --week 2026-08-09 --meetings meetings.json --apply
```
`meetings.json` = `[{ "id","title","summary"|"notes","url"?,"author"?,"occurred_at"? }, …]`.

### Feeding it meetings (Granola's local cache + token are encrypted, so not read directly)
1. **Automated loop (recommended):** a Claude scheduled agent (via `/schedule`) that, each week/day,
   calls the Granola MCP (`list_meetings` + `get_meeting_transcript`) for recent meetings → writes
   `meetings.json` → runs `granola_bridge.py --apply`. This is the true "stitched" trigger.
2. **Manual JSON:** build `meetings.json` by hand / export and run the bridge.
3. **Manual link (works today, zero setup):** in the Review tab → Granola band → *＋ Add link* →
   paste the meeting URL → *Add meeting*. Queues the same extraction for that CE.

## Fail-closed guarantees (already in code)
- No `x-granola-secret` / wrong secret → `401`, nothing ingested.
- No `ANTHROPIC_API_KEY` or AI secret → extraction fails, raw source retained, no invented summary.
- No exact CE match → source parked in `review_source_inbox`; never enters CE Memory/commentary/work.
