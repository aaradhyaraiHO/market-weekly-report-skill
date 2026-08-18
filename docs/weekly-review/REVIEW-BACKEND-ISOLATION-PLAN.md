# Review-mode backend isolation plan

Status: implemented locally; not provisioned, migrated, deployed or activated

## Local implementation snapshot

- `scripts/weekly_report/notes/review_apps_script.js` is the standalone Review-only Apps Script artifact. It opens only `REVIEW_SPREADSHEET_ID`, uses `REVIEW_MODE_*` secrets, and contains no legacy notes/actions routes.
- `/api/review`, Granola ingestion, transcript extraction and AI summary adapters now fail closed unless the isolated `REVIEW_MODE_*` configuration is present.
- `scripts/weekly_report/notes/apps_script.js` remains the incident-history/combined artifact. Commit `ecc0127` and the legacy `action_upsert` / `action_delete` contract are unchanged; the only additive edits are Review work-item tombstones.
- `scripts/weekly_report/inject_review_view.py` now embeds the source-controlled Review client, never a potentially stale deploy-directory copy.
- No spreadsheet, Apps Script project, trigger, Slack thread, Vercel environment or production route has been changed by this implementation.

## Decision

Keep the established Weekly Report Notes spreadsheet and its Apps Script deployment as the permanent V1/V2 diagnostic-action service. Build Review mode as a separate service with its own spreadsheet, Apps Script project, deployment URL, secrets and mutation policy.

The production hotfix at Apps Script version 13 remains the behavioral baseline:

- `action_list`, `action_upsert` and `action_delete` belong to the diagnostic report workflow.
- Authenticated Headout users may write diagnostic actions.
- `action_upsert` derives `owner` from verified identity.
- Review access rules must never wrap or otherwise change these routes again.

Review mode may consume diagnostic context, but it must not write to, mirror into, migrate or replace the existing `actions` tab.

## Service boundary

### Remains on the current spreadsheet and Apps Script deployment

| Surface | Routes or data | Rule |
|---|---|---|
| CE drawer notes | `notes`; `list`, `upsert`, `delete`, `post` | Preserve current behavior and Slack linkage. |
| Diagnostic bucket actions | `actions`; `action_list`, `action_upsert`, `action_delete` | Preserve the version-13 authenticated-Headout writer contract. |
| Report UI integration | `DATA.notes_url` / `NOTES_URL` | Continues pointing only to the legacy deployment. |
| V1/V2 action UX | Required comment before sync; Saving/Saved/error states | Must remain covered independently of Review tests. |

Do not add Review tables, BGM allowlists, Granola ingestion or Review automation to this service in future versions.

### Moves to a new Review spreadsheet and Apps Script deployment

The new service owns only these tables:

1. `review_weekly_commentary`
2. `review_work_items`
3. `review_receipts`
4. `review_set`
5. `ce_threads`
6. `review_source_suggestions`
7. `review_source_inbox`
8. `bgm_access`
9. `review_slack_people`
10. `review_comments` — retained only for compatibility/history; the canonical current workflow remains one BGM note per CE × market × week.

The existing identifiers remain unchanged:

- weekly records: `market_slug × ce_id × week_start`
- persistent Slack thread: `market_slug × ce_id`
- work, receipts, suggestions and source records: immutable generated IDs plus the CE identity

The Review service contains only `review_*` routes, Review storage helpers, Slack-thread synchronization, source ingestion and BGM/GM/admin authorization. It must not define `ACTION_SHEET_NAME`, `getActionSheet`, `action_upsert` or `action_delete`.

## Read-only diagnostic boundary

Preferred: Review receives bucket reason, CE metrics, Slack context cards and `ce.perf_action_hist` from the immutable report snapshot already loaded in the browser. This avoids a runtime dependency on the legacy spreadsheet.

If historical diagnostic-action rows are later required inside CE Memory, expose a dedicated read-only adapter that permits only `action_list` and returns a reduced DTO. It must:

- use a separate route such as `/api/review-diagnostics`;
- reject every non-GET request and every action other than `action_list`;
- never expose the legacy Apps Script URL to Review mutation code;
- label results as diagnostic history, not Review work items;
- fail closed without blocking the report or Review writes.

There is no dual write. Accepting a Review action or Granola suggestion creates a `review_work_items` record only. It must never call `action_upsert`.

## Endpoint and configuration changes

### Browser

- Keep `NOTES_URL` for legacy notes and diagnostic actions only.
- Keep the public Review client on same-origin `/api/review`, but source the URL from an explicit optional `review_api_url` field so Review can be disabled independently.
- The Review client must never fall back from `/api/review` to `NOTES_URL` for mutations.
- If Review is unavailable, render an unavailable state; do not fall back to local-only or legacy action writes.

### Vercel

`/api/review` becomes a proxy exclusively to the new deployment:

- `REVIEW_MODE_APPS_SCRIPT_URL`
- `REVIEW_MODE_PROXY_SECRET`

Avoid the ambiguous current `REVIEW_APPS_SCRIPT_URL` name after cutover. The HMAC actor envelope remains, but the Review project verifies only `REVIEW_MODE_PROXY_SECRET`.

Granola and meeting extraction also target only the new Review deployment:

- `REVIEW_MODE_INGEST_SECRET`
- `REVIEW_MODE_AI_WEBHOOK_URL`
- `REVIEW_MODE_AI_WEBHOOK_SECRET`
- `GRANOLA_WEBHOOK_SECRET`

The legacy report deployment URL and any legacy signing/auth configuration remain unchanged.

### New Review Apps Script properties

- `REVIEW_MODE_PROXY_SECRET`
- `REVIEW_ENFORCE_ACCESS=true`
- `REVIEW_MODE_INGEST_SECRET`
- `REVIEW_MODE_AI_WEBHOOK_URL`
- `REVIEW_MODE_AI_WEBHOOK_SECRET`
- `SLACK_BOT_TOKEN` (prefer a separately scoped Review app; sharing the current bot is acceptable only as a temporary credential decision)
- `REVIEW_ENABLE_DIRECTORY_SYNC`

The new Apps Script should be bound to the new Review spreadsheet or use a fixed `REVIEW_SPREADSHEET_ID`. It must never use the legacy Notes spreadsheet as its active spreadsheet.

## Data migration

Do not migrate `notes` or `actions`.

For the Review tables, use an explicit export/import job rather than copying tabs manually:

1. Freeze only Review-mode mutations for a short announced window; legacy actions remain fully available.
2. Export all ten Review tables from the old spreadsheet read-only.
3. Validate headers, row counts, immutable IDs and normalized date/string fields.
4. Import into empty tables in the new spreadsheet with idempotency by immutable ID. For `review_set` and weekly records, validate their composite keys as well.
5. Compare per-table counts and deterministic row hashes, excluding Sheet row numbers.
6. Run read-only API parity checks for representative CE histories, open work, receipts, access records, Slack-thread mappings and pending suggestions.
7. Keep the old Review tabs untouched and read-only during the rollback period. Do not delete them.

If existing Review data is not required, launch with empty Review tables instead; that must be an explicit product decision, not an accidental omission.

## Cutover sequence

1. **Refactor locally:** split the combined Apps Script source into a frozen legacy artifact and a Review-only artifact. Keep commit `ecc0127` intact.
2. **Contract gate:** prove the Review artifact contains no legacy mutation route and the legacy artifact preserves version-13 action behavior.
3. **Provision:** create the new spreadsheet and Apps Script project, install Review tables/triggers and seed `bgm_access` in a non-production environment.
4. **Stage proxy:** deploy a preview `/api/review` configured with the new URL and secret. Do not change `NOTES_URL`.
5. **Migrate Review data:** run the export/import and parity checks above, if history is retained.
6. **Canary:** test one market and synthetic CE through note save/delete, treatment, receipt, work item, scheduled check, persistent Slack thread, Slack-summary ingestion and Granola reconciliation.
7. **UI cutover:** switch only `review_api_url` or the `/api/review` proxy target. Diagnostic actions continue to use the unchanged `NOTES_URL`.
8. **Observe:** monitor Review error rates, duplicate IDs, source-ingestion backlog and Slack sync for at least one WBR cycle before broader rollout.
9. **Retire old Review writes:** after the rollback window, disable only old `review_*` mutations. Do not edit or redeploy the version-13 legacy action contract as part of this step.

## Tests required before cutover

### Static isolation tests

- Review Apps Script contains no `ACTION_SHEET_NAME`, `action_upsert`, `action_delete`, `getActionSheet` or legacy `notes` mutation routes.
- Legacy Apps Script contains the version-13 diagnostic mutation branch and derives action owner from verified identity.
- Review browser code never sends a Review mutation to `NOTES_URL`.
- Review suggestion acceptance never calls or constructs `action_upsert`.
- `/api/review` reads only `REVIEW_MODE_APPS_SCRIPT_URL` and signs with only `REVIEW_MODE_PROXY_SECRET`.

### Legacy regression tests

- An authenticated non-BGM Headout actor can save and delete a diagnostic action.
- An unauthenticated actor cannot save or delete one.
- A blank diagnostic comment never syncs.
- UI state transitions are `Saving` → `Saved`, and failures retain the draft with an error.
- Existing reads and prior-week action history are unchanged.

### Review contract tests

- BGM/GM/admin market authorization applies to every Review mutation and to no legacy route.
- Same-week note save/delete preserves attribution and tombstones.
- Work-item and scheduled-check status transitions preserve source and due date.
- Review receipt and review-set identities are idempotent.
- One CE retains one persistent Slack thread across weeks.
- Slack replies and AI summaries retain author, permalink and source refs.
- Granola exact matches create pending suggestions; ambiguous matches enter reconciliation; no suggestion writes automatically to commentary or work.
- Missing Review service, AI service or optional diagnostic adapter fails closed without blocking V1/V2.

### Migration and rollback tests

- Row-count and row-hash parity for every migrated Review table.
- Read parity for Kennedy and at least one CE with no history, one with open work and one with a prior Slack thread.
- A proxy-target rollback restores old Review reads/writes without changing `NOTES_URL` or the diagnostic-action deployment.

## Rollback

Rollback is a Review-only operation:

1. Flip `/api/review` back to the previous combined Apps Script URL and its previous proxy secret, or disable the Review tab if old writes were frozen.
2. Leave `DATA.notes_url`, the legacy spreadsheet, version-13 deployment and diagnostic-action UI untouched.
3. Preserve records written to the new Review spreadsheet for reconciliation; do not copy them into `actions`.
4. Reconcile Review records by immutable ID before attempting a later cutover.

Because the diagnostic action path never moves, a Review rollback cannot interrupt Losing Money, RPC/CM1 or other established action comments.

## Worktree implementation shape

The safest eventual code layout is:

```text
scripts/weekly_report/notes/
  legacy_apps_script.js          # notes/actions only; version-13 contract
  review_apps_script.js          # review tables/routes only
  review_client.js               # /api/review only
  review_proxy_api.js            # new Review URL/secret names
  review_diagnostics_api.js      # optional GET-only adapter
  granola_review_adapter.js      # new Review ingestion URL/secret
```

The existing combined `apps_script.js` should remain available as incident history until the split is fully verified. Do not overwrite it during the first isolation change.
