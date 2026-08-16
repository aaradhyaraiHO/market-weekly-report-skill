# Weekly Report Notes + WBR Review Backend — Setup

The current CE drawer and the WBR Review workspace share one Apps Script web app.
Legacy notes/actions keep their existing contract. The production commentary path is
deliberately narrower: one original BGM note per CE × week and one evolving,
source-linked AI summary of that week's Slack discussion. Review mode also adds
persistent work items, review receipts, CE memory, review-set membership and one
persistent Slack thread per CE.

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

- **BGM note** → one `review_weekly_commentary` record per market × CE × week. Save
  updates the original wording; delete is a tombstone so the audit trail remains.
- **Start Slack discussion** → saves the textarea and posts that exact text in one
  idempotent operation. Natural-language names resolve through the Slack people
  directory. Ambiguous names fail closed instead of tagging the wrong person.
- **Slack discussion summary** → a five-minute trigger ingests only new human replies,
  retains their author, timestamp, permalink and source text, then asks the AI adapter
  for concise findings, decisions and open points. The BGM note and AI summary remain
  visibly separate in the UI.
- **Historical commentary** → CE Memory groups each week as a pair: original BGM note
  plus the corresponding Slack thread summary and source link.
- **Review commentary (compatibility)** → stable `comment_id`; older multi-author review
  records remain readable but are not the primary BGM authoring path.
- **Actions + scheduled checks** → stable `work_id`; both CE review and Open work read
  the same record. Checks may have no owner until they become an action.
- **Finish CE review** → upserts one receipt for market × CE × week, including treatment,
  reviewer, timestamp, next review date, summary and open-work count.
- **Ask in Slack** → creates or reuses the CE thread, stores `ts` + permalink, and never
  creates a new thread merely because the week changed. Each weekly starter defines the
  boundary for that week's replies, so replies cannot leak into two weekly summaries.
- **Scan Slack** → imports new human replies as pending source-exact suggestions. A BGM
  must approve/edit before they become commentary or work.
- **Granola** → sends CE-keyed suggestions through the same source-ingestion endpoint.
  Unmatched records are rejected because `market_slug`, `ce_id`, `week_start` and source
  identity are mandatory.
- **View thread** → the Post button becomes a deep-link once a thread exists.
- **CE Memory** → returns new records plus labelled legacy notes/actions. Perf finals are
  not copied: the UI reads the existing read-only `ce.perf_action_hist` snapshot field.

The ten review tabs auto-create on first use:

`review_comments`, `review_work_items`, `review_receipts`, `review_set`, `ce_threads`,
`review_weekly_commentary`, `review_source_suggestions`, `review_source_inbox`,
`bgm_access`, and `review_slack_people`. The inbox holds unmatched or ambiguous Granola
records until a BGM explicitly reconciles them to a CE.

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
3. **Invite the bot to each configured market channel** it will post to:
   - `/invite @Monthly Market Review` in `#mkt-usa`, `#mkt-italy-switzerland-malta`, `#mkt-anz`
4. Redeploy a new version so the property is picked up.

Optional AI adapter:

- Script property `REVIEW_AI_WEBHOOK_URL`
- Script property `REVIEW_AI_WEBHOOK_SECRET` (sent as `X-Review-Secret`; must
  match the server-side endpoint secret)
- For weekly Slack summaries it receives `mode: weekly_thread_summary`, the CE/week
  identity, the prior summary and all source-exact replies for that week. It returns:

```json
{
  "summary": {
    "findings": [],
    "decisions": [],
    "open_points": [],
    "action_suggestions": [],
    "check_suggestions": [],
    "source_refs": ["CHANNEL:MESSAGE_TS"]
  }
}
```

- Every summary must cite at least one ingested `source_ref`. If the adapter is absent or
  invalid, the UI shows **summary delayed**, raw replies remain stored, and no summary is
  invented. Owners on action suggestions are never inferred.
- The production adapter is `review_summary_api.js`. Its Vercel function reads the
  server-only `ANTHROPIC_API_KEY` environment variable and calls the Anthropic Messages
  API directly. `REVIEW_AI_MODEL` is optional; the default is the pinned
  `claude-haiku-4-5-20251001` model. Strict tool input schemas constrain both response shapes.
- The report login middleware must exclude only `/api/auth` and
  `/api/review-summary`; use `review_summary_middleware.js` as the matcher reference.
  The webhook itself remains protected by `X-Review-Secret`.
- If Anthropic authentication, quota, or model access is unavailable, the endpoint fails
  closed and the report retains raw attributed Slack replies while showing the summary
  as delayed.

External source ingress:

- Script property `REVIEW_INGEST_SECRET` is mandatory for `review_source_ingest` POSTs.
- The secret belongs in the server-side Granola adapter; it must never be embedded in report HTML.
- Exact CE matches enter `review_source_suggestions` as pending. Ambiguous/unmatched Granola
  records enter `review_source_inbox` and cannot affect CE memory until reconciled.
- `ingest_review_sources.py` is the dry-run-first server bridge. It accepts source JSON and
  only posts with `--apply`, `WR_REVIEW_INGEST_SECRET`, and the Apps Script URL configured.

Without `SLACK_BOT_TOKEN`, Save still works; Post returns an error and the
button shows "Post failed".

## 3. BGM access and automation

The report UI is BGM-operated. Perf, Ops, BDM and GM respond in the CE's Slack thread;
their replies return as attributed summary pointers.

1. Populate `bgm_access` with one row per BGM and market. Use the person's Workspace
   email, role `bgm` (or `gm`/`admin`), and `active=true`.
2. Deploy the web app inside the Workspace so `Session.getActiveUser().getEmail()` is
   available. Do not deploy the review endpoints anonymously.
3. Set Script property `REVIEW_ENFORCE_ACCESS=true` after the allowlist is populated.
   `REVIEW_ALLOW_ACTOR_PARAM=true` exists only for controlled local/pilot diagnostics;
   never enable it in production.
4. Run `installReviewAutomation()` once from the Apps Script editor. It creates
   every additive review tab and installs:
   - a five-minute Slack reply sync; and
   - an optional daily Slack people-directory refresh when Script property
     `REVIEW_ENABLE_DIRECTORY_SYNC=true` and the bot has `users:read`.

The directory refresh updates Slack names and membership while preserving aliases and
market scope curated in `review_slack_people`.

## 4. Channel map

Market → channel is in `config.py` → `NOTES_SLACK_CHANNELS`:

| Market | Channel | ID |
|--------|---------|-----|
| north_america | #mkt-usa | CNSHDD2H1 |
| italy | #mkt-italy-switzerland-malta | C045L2WQ79P |
| oceania | #mkt-anz | CHKRLFDPU |

Add a market by adding a row here (and inviting the bot to that channel).

## 5. Test

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

# save this week's original BGM note
curl -sLG "$WR_NOTES_SCRIPT_URL" --data-urlencode action=review_weekly_note_upsert \
  --data-urlencode market_slug=north_america --data-urlencode ce_id=3111 \
  --data-urlencode ce_name='Kennedy Space Center' --data-urlencode week_start=2026-08-10 \
  --data-urlencode bgm_note='Royan, please confirm the Riskified/C2O follow-up.' \
  --data-urlencode bgm_author=Pari
```

## Deployment boundary

Updating this repository does not mutate the live Sheet or Slack. Deployment is a separate,
intentional step: paste/deploy `apps_script.js`, populate access and people aliases, set the
properties above, run `installReviewAutomation()`, and publish a newly rendered report. The
renderer now embeds `review_client.js` automatically.
