# Weekly Report Notes + WBR Review Backend — Setup

The current CE drawer and the WBR Review workspace share one Apps Script web app.
Legacy notes/actions keep their existing contract. Review mode adds append-only
attributed commentary, persistent work items, review receipts, CE memory, review
set membership, source suggestions, and one persistent Slack thread per CE.

## Architecture

```
report.html / Review mode / CE drawer
   │  legacy endpoints + review_* endpoints
   ▼
Apps Script web app  ──►  Google Sheet  (source of truth)
   │  chat.postMessage + conversations.replies
   ▼
Slack #mkt-* channel  (one thread per market × CE)
```

- **Legacy Save** → writes the current one-note-per-CE/week row used by the report today.
- **Review commentary** → stable `comment_id`; multiple same-week authors are preserved;
  deletion is a tombstone rather than a row delete.
- **Actions + scheduled checks** → stable `work_id`; both CE review and Open work read
  the same record. Checks may have no owner until they become an action.
- **Finish CE review** → upserts one receipt for market × CE × week, including treatment,
  reviewer, timestamp, next review date, summary and open-work count.
- **Ask in Slack** → free-form text with unrestricted mentions; creates or reuses the CE
  thread, stores `ts` + permalink, and never creates a new thread merely because the week changed.
- **Scan Slack** → imports new human replies as pending source-exact suggestions. A BGM
  must approve/edit before they become commentary or work.
- **Granola** → sends CE-keyed suggestions through the same source-ingestion endpoint.
  Unmatched records are rejected because `market_slug`, `ce_id`, `week_start` and source
  identity are mandatory.
- **View thread** → the Post button becomes a deep-link once a thread exists.
- **CE Memory** → returns new records plus labelled legacy notes/actions. Perf finals are
  not copied: the UI reads the existing read-only `ce.perf_action_hist` snapshot field.

The seven review tabs auto-create on first use:

`review_comments`, `review_work_items`, `review_receipts`, `review_set`, `ce_threads`,
`review_source_suggestions`, and `review_source_inbox`. The inbox holds unmatched or
ambiguous Granola records until a BGM explicitly reconciles them to a CE.

## 1. Sheet + Apps Script (already deployed)

- Sheet: `Weekly Report Notes` (ID `1hC_IAsJrlPcpFv5K49eRtcwgK6i_DkAt4ZvETxlK-s8`)
- Web app URL is set in `config.py` → `NOTES_SCRIPT_URL`

If redeploying: paste `apps_script.js` into the sheet's Apps Script editor
(Extensions → Apps Script), then Deploy → Manage deployments → New version.
The `notes` tab auto-creates with headers on first call.

## 2. Slack posting (one-time)

The Post button reuses the existing **`REVENUE_ALERT_SLACK_TOKEN`** bot
(the "Monthly Market Review" bot). To enable posting:

1. In the Apps Script editor: **Project Settings (gear) → Script properties → Add**
   - Property: `SLACK_BOT_TOKEN`
   - Value: the `xoxb-…` token (same one exported as `REVENUE_ALERT_SLACK_TOKEN`)
2. The Review workflow needs bot scopes for posting and reply capture:
   - `chat:write`
   - `channels:history` (public market channels)
   - `users:read` (human-readable reply attribution; user ID is the fallback)
3. **Invite the bot to each market channel** it will post to:
   - `/invite @Monthly Market Review` in `#mkt-usa`, `#mkt-italy-switzerland-malta`, `#mkt-anz`
4. Redeploy a new version so the property is picked up.

Optional AI adapter:

- Script property `REVIEW_AI_WEBHOOK_URL`
- Receives source-exact Slack/Granola records and may return source-linked summary/action
  suggestions. If absent or invalid, the API returns `source_unavailable`; raw source records
  remain pending and no summary is invented.

External source ingress:

- Script property `REVIEW_INGEST_SECRET` is mandatory for `review_source_ingest` POSTs.
- The secret belongs in the server-side Granola adapter; it must never be embedded in report HTML.
- Exact CE matches enter `review_source_suggestions` as pending. Ambiguous/unmatched Granola
  records enter `review_source_inbox` and cannot affect CE memory until reconciled.
- `ingest_review_sources.py` is the dry-run-first server bridge. It accepts source JSON and
  only posts with `--apply`, `WR_REVIEW_INGEST_SECRET`, and the Apps Script URL configured.

Without `SLACK_BOT_TOKEN`, Save still works; Post returns an error and the
button shows "Post failed".

## 3. Channel map

Market → channel is in `config.py` → `NOTES_SLACK_CHANNELS`:

| Market | Channel | ID |
|--------|---------|-----|
| north_america | #mkt-usa | CNSHDD2H1 |
| italy | #mkt-italy-switzerland-malta | C045L2WQ79P |
| oceania | #mkt-anz | CHKRLFDPU |

Add a market by adding a row here (and inviting the bot to that channel).

## 4. Test

```bash
# list (empty ok)
curl -sL "$WR_NOTES_SCRIPT_URL?action=list&market=north_america"

# save a note
curl -sL "$WR_NOTES_SCRIPT_URL?action=upsert&market_slug=north_america&ce_id=220&ce_name=Test&week_start=2026-07-06&note=hello&author=me"

# post to slack (needs SLACK_BOT_TOKEN + bot in channel)
curl -sL "$WR_NOTES_SCRIPT_URL?action=post&market_slug=north_america&ce_id=220&ce_name=Test&week_start=2026-07-06&channel=CNSHDD2H1&text=hello&author=me"

# add independent same-week commentary
curl -sLG "$WR_NOTES_SCRIPT_URL" --data-urlencode action=review_comment_upsert \
  --data-urlencode market_slug=north_america --data-urlencode ce_id=3111 \
  --data-urlencode week_start=2026-08-09 --data-urlencode body='Inventory confirmed healthy' \
  --data-urlencode author_name=Royan --data-urlencode author_role=Ops

# schedule a dated check (owner intentionally optional)
curl -sLG "$WR_NOTES_SCRIPT_URL" --data-urlencode action=review_work_upsert \
  --data-urlencode market_slug=north_america --data-urlencode ce_id=3111 \
  --data-urlencode origin_week=2026-08-09 --data-urlencode kind=check \
  --data-urlencode text='Did C2O recover?' --data-urlencode status=scheduled \
  --data-urlencode due_date=2026-08-17

# CE Memory (new + labelled legacy context)
curl -sLG "$WR_NOTES_SCRIPT_URL" --data-urlencode action=review_memory \
  --data-urlencode market_slug=north_america --data-urlencode ce_id=3111
```

## Deployment boundary

Updating this repository does not mutate the live Sheet or Slack. Deployment is a separate,
intentional step: paste/deploy `apps_script.js`, then wire `review_client.js` into the report UI.
