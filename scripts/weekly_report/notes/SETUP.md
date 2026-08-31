# WBR Review Backend — Isolated Setup

The established CE-drawer notes and diagnostic actions remain on their existing
spreadsheet and Apps Script deployment. WBR Review is a separate service with its
own spreadsheet, Apps Script project, deployment URL and secrets. Never paste the
Review artifact into the established service and never point Review at its Sheet.

The Review commentary path is deliberately narrow: one original BGM note per CE ×
week and one evolving, source-linked AI summary of that week's Slack discussion.
Review mode also adds persistent work items, review receipts, CE memory, review-set
membership and one persistent Slack thread per CE.

## Architecture

```
report.html / Review mode
   │  /api/review → review_* endpoints only
   ▼
Review Apps Script web app  ──►  Review spreadsheet  (source of truth)
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
  the same record. Checks may have no owner until they become an action. BGM deletion
  writes a `deleted_at`/`deleted_by` tombstone; default lists and CE Memory hide it,
  while `include_deleted=true` preserves the audit view.
- **Finish CE review** → upserts one receipt for market × CE × week, including treatment,
  reviewer, timestamp, next review date, summary and open-work count.
- **Ask in Slack** → creates or reuses the CE thread, stores `ts` + permalink, and never
  creates a new thread merely because the week changed. Each weekly starter defines the
  boundary for that week's replies, so replies cannot leak into two weekly summaries.
- **Scan Slack** → imports new human replies as pending source-exact suggestions. A BGM
  must approve/edit before they become commentary or work.
- **Granola** → the server-side `granola_review_adapter.js` accepts a normalized meeting
  event, extracts source-linked commentary/action/check suggestions, and sends them through
  the same source-ingestion endpoint. Exact CE matches appear as pending BGM suggestions.
  Ambiguous or unmatched records are held in reconciliation and cannot enter CE Memory.
- **View thread** → the Post button becomes a deep-link once a thread exists.
- **CE Memory** → returns Review commentary, work, receipts and attributed source
  records only. Perf finals remain read-only in the report snapshot through
  `ce.perf_action_hist`; any older diagnostic history must cross a separate GET-only
  adapter and is never written into Review storage.

The ten Review tabs auto-create in the Review spreadsheet on first use:

`review_comments`, `review_work_items`, `review_receipts`, `review_set`, `ce_threads`,
`review_weekly_commentary`, `review_source_suggestions`, `review_source_inbox`,
`bgm_access`, and `review_slack_people`. The inbox holds unmatched or ambiguous Granola
records until a BGM explicitly reconciles them to a CE.

## 1. Separate Review spreadsheet + Apps Script

- Create a dedicated Review spreadsheet. Do not reuse `Weekly Report Notes`.
- Create a dedicated Apps Script project and paste `review_apps_script.js` into it.
- Set `REVIEW_SPREADSHEET_ID` to the dedicated Review spreadsheet ID.
- Deploy that project as a web app and configure the server proxy with
  `REVIEW_MODE_APPS_SCRIPT_URL` and `REVIEW_MODE_PROXY_SECRET`.
- Keep `NOTES_SCRIPT_URL` unchanged. It remains the established diagnostic service.

The combined `apps_script.js` remains incident history and backward-compatible source
for the current deployment. It is not the Review deployment artifact.

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
3. **Invite the bot to each configured Review channel** it will post to. Use
   `docs/weekly-review/MARKET_CHANNEL_MAPPING.md`; North America Review uses
   `#adhoc-north-america`, not the weekly-alert `#mkt-usa` route.
4. Redeploy only the isolated Review project so the property is picked up.

Optional AI adapter:

- Script property `REVIEW_MODE_AI_WEBHOOK_URL`
- Script property `REVIEW_MODE_AI_WEBHOOK_SECRET` (sent as `X-Review-Secret`; must
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

- Script property `REVIEW_MODE_INGEST_SECRET` is mandatory for `review_source_ingest` POSTs.
- The secret belongs in the server-side Granola adapter; it must never be embedded in report HTML.
- Exact CE matches enter `review_source_suggestions` as pending. Ambiguous/unmatched Granola
  records enter `review_source_inbox` and cannot affect CE memory until reconciled.
- `ingest_review_sources.py` is the dry-run-first server bridge. It accepts source JSON and
  only posts with `--apply`, `WR_REVIEW_MODE_INGEST_SECRET`, and
  `WR_REVIEW_MODE_APPS_SCRIPT_URL` configured.

Automatic Granola adapter:

- Deploy `granola_review_adapter.js` as `/api/granola-review` beside `/api/review-summary`.
- Set server-only `GRANOLA_WEBHOOK_SECRET`, `REVIEW_MODE_APPS_SCRIPT_URL`,
  `REVIEW_MODE_INGEST_SECRET`, `REVIEW_MODE_AI_WEBHOOK_URL`, and
  `REVIEW_MODE_AI_WEBHOOK_SECRET`.
- The upstream Granola automation sends `{meeting, matches}`. A match is only exact when it
  includes `market_slug`, `week_start`, `ce_id`, and `match_status: "exact"`.
- No exact match fails closed into `review_source_inbox`; nothing is attached to a CE.
- All imported suggestions have a stable source-derived ID. Retrying a webhook, pull, or
  transcript extraction is idempotent: it cannot create duplicate commentary, actions, or
  checks. A transcript that produces no conservative extraction is retained as inbox evidence,
  rather than being attached to a candidate CE.
- The CE drawer polls source suggestions with the normal review refresh. The BGM may edit,
  choose Commentary / Action / Scheduled check, accept, or ignore. Owners remain blank unless
  the BGM explicitly sets them later.

Granola REST pull (optional alternative to an upstream meeting job):

- Deploy `granola_pull_api.js` as server-only `/api/granola-pull`. It accepts only a
  Review AI secret, obtains `GRANOLA_API_KEY` server-side, and requires the caller to pass
  the market week's CE catalogue. It never exposes a Granola token to the browser.
- Run it on a server-side schedule with `market_slug`, `week_start`, and a snapshot-derived
  CE list. Exact full-name CE matches can produce pending suggestions for more than one CE;
  all partial, multiple, or no-match references remain in `review_source_inbox`.
- Use exactly one ingestion mechanism per meeting: the upstream `/api/granola-review`
  webhook/bridge *or* the REST pull cursor. Both are retry-safe, but two mechanisms would
  preserve two distinct external source records by design.

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

The runtime authority is `REVIEW_MARKET_SLACK_CHANNELS` in the isolated Review
Apps Script, mirrored by `MARKET_CHANNELS` in the Review UI. The reviewed human
reference is `docs/weekly-review/MARKET_CHANNEL_MAPPING.md`. Review currently
supports the 17 market reports; Headout/global is intentionally excluded.

Add or reroute a market only by updating both runtime maps, the mapping contract
test and the reference document together, then inviting the bot to every listed
primary/alternate channel. Weekly alert routing remains a separate contract.

## 5. Test

Use an authenticated preview through `/api/review`; the proxy signs the verified actor
identity. Do not test Review mutations against `WR_NOTES_SCRIPT_URL`.

```bash
# Examples below assume WR_REVIEW_MODE_PROXY_URL points to the authenticated preview.

# add independent same-week commentary
curl -sLG "$WR_REVIEW_MODE_PROXY_URL" --data-urlencode action=review_comment_upsert \
  --data-urlencode market_slug=north_america --data-urlencode ce_id=3111 \
  --data-urlencode week_start=2026-08-09 --data-urlencode body='Inventory confirmed healthy' \
  --data-urlencode author_name=Royan --data-urlencode author_role=Ops

# schedule a dated check (owner intentionally optional)
curl -sLG "$WR_REVIEW_MODE_PROXY_URL" --data-urlencode action=review_work_upsert \
  --data-urlencode market_slug=north_america --data-urlencode ce_id=3111 \
  --data-urlencode origin_week=2026-08-09 --data-urlencode kind=check \
  --data-urlencode text='Did C2O recover?' --data-urlencode status=scheduled \
  --data-urlencode due_date=2026-08-17

# CE Memory (Review records only)
curl -sLG "$WR_REVIEW_MODE_PROXY_URL" --data-urlencode action=review_memory \
  --data-urlencode market_slug=north_america --data-urlencode ce_id=3111

# save this week's original BGM note
curl -sLG "$WR_REVIEW_MODE_PROXY_URL" --data-urlencode action=review_weekly_note_upsert \
  --data-urlencode market_slug=north_america --data-urlencode ce_id=3111 \
  --data-urlencode ce_name='Kennedy Space Center' --data-urlencode week_start=2026-08-10 \
  --data-urlencode bgm_note='Royan, please confirm the Riskified/C2O follow-up.' \
  --data-urlencode bgm_author=Pari
```

## Deployment boundary

Updating this repository does not mutate either Sheet or Slack. Deployment is a
separate, intentional step: paste/deploy `review_apps_script.js` into the isolated
Review project, populate access and people aliases, set the properties above, run
`installReviewAutomation()`, configure the server proxy, and publish a newly rendered
report. Do not redeploy or change the established notes/actions service as part of a
Review release.

Before a Review canary, run the non-mutating configuration gate from the Vercel
environment (or another environment containing the same server-side variables):

```bash
python3 scripts/weekly_report/notes/review_preflight.py --server
```

It validates that only the isolated `REVIEW_MODE_*` configuration is present; it
does not read or write the legacy notes/actions service, Slack, Granola, or Sheets.
