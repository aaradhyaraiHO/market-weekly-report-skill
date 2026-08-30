# Frozen Review P0 UI → backend contract

Status: repository-readiness contract. The local fixture is frozen; no production, Preview, Slack, Sheet, Apps Script, or schema mutation is authorized by this document.

## Shared identity and state

Every Review and future compact CE-drawer operation uses one identity:

`market_slug + review_week/week_start + stable CE ID`

CE names are display-only. Browser drafts add `draft_type` to that identity. Slack summaries additionally bind to `thread_binding_id` and `slack_discussion_number`; a newer discussion must never inherit or overwrite an older discussion’s summary.

The Review tab owns the full workflow. The CE drawer may later project only BGM observation, Slack lifecycle/current summary state, and an `Open full Review` transition over this same state. It must not create parallel storage or API operations.

## Frozen control and operation matrix

| UI intent | Local state and validation | Existing endpoint | Persisted fields / authority | Success | Failure / rollback | Authorization |
| --- | --- | --- | --- | --- | --- | --- |
| Search/select CE | Local query; stable ID selection | None | None | Immediate queue/workspace update | Preserve current selection/drafts | Report visibility |
| Nominate/defer/reopen | Exact CE; no placeholder | `review_set_upsert` | market, week, CE ID/name, included, treatment, reason, position | Queue updates after confirmation | Restore previous queue state | BGM/GM/admin market access |
| Load thread lifecycle | Do not infer no-thread while pending/error | `review_thread_list` | `ce_threads`, keyed by market + CE ID | checking → no/prior/current | Clear retry state; no Start action on failure | Authorized market read |
| Continue discussion #N | Non-empty message; stable request ID | `review_weekly_slack_post` | current binding, weekly starter/source window, author, request ID | Append once; retain binding/permalink | Keep draft, enable retry; dedupe request ID | BGM/GM/admin + exact market channel |
| Start a new discussion | Non-empty message + reason + confirmation | `review_weekly_slack_post` with `thread_operation=new_parent` | predecessor/successor bindings, reason, actor, both permalinks, week, request ID | New numbered binding, old preserved | Keep drafts; no replacement on failure | Same as Continue |
| Add/edit BGM observation | CE-scoped draft; meaningful text | `review_weekly_note_upsert` (`note_type=bgm`) | BGM note, trusted author, timestamp, market/week/CE | Shared Review/drawer state refresh | Retain draft and saved value | BGM/GM/admin market access |
| Cancel observation | Local only | None | None | Restore last confirmed value | N/A | Local |
| Approve/edit/dismiss summary | Exact current discussion binding; valid JSON on approval | `review_summary_decide` | summary status/draft/approved body, approver/time, discussion binding | Approved enters CE Memory | Preserve source state; retry | BGM/GM/admin market access |
| Triage suggestion | Exact suggestion ID; edit required fields before approval | `review_suggestion_decide` | decision, trusted actor/time, accepted text/owner/date, destination | Exactly one committed item | Restore suggestion/editor | Server resolves suggestion market/CE before auth |
| Create manual action/check | Opening writes nothing; meaningful text, owner and relevant date | `review_work_upsert` | work ID, market/week/CE, kind, text, owner, status, due/next-check, source, idempotency key | Optimistic row reconciles once | Roll back row; retain draft | BGM/GM/admin market access |
| Edit/reassign/reschedule | Validate text/owner and state-specific date | `review_work_upsert` | Same work record; updated time/status/close evidence | Re-group row | Restore confirmed record/editor | Server resolves immutable scope |
| Complete/reopen | Explicit checkbox; optimistic with Undo | `review_work_upsert` | status and `closed_at` (or reopened empty close) | Counts and tab update | Roll back and retain prior state | Same work authorization |
| Finish review | Treatment + Slack or explicit no-discussion reason + complete suggestion triage | `review_receipt_upsert` | receipt, reviewer/time, treatment, summary, open count, optional no-discussion reason | Reviewed receipt/header/queue update | Remain unfinished; retry | BGM/GM/admin market access |
| CE Memory | Read-only/fail-soft | `review_memory` | Approved summaries, observations, work, receipts and historical read-only sources | Cached chronological history | Missing source does not block Review | Market-scoped authorized read |

## Required additive backend hardening

1. Add `thread_binding_id` and `slack_discussion_number` to weekly commentary records.
2. Set both fields after every successful Start/Continue operation.
3. Require summary decisions to identify the exact discussion and reject a stale/mismatched binding.
4. Return the binding fields through weekly list/memory unchanged.
5. Keep existing rows readable: legacy rows without binding fields remain historical compatibility records, but a new summary approval must bind explicitly.
6. Retain the existing proxy allowlist, signed actor, market access check, idempotency keys, channel validation, and legacy-route isolation.

## Configuration and migration readiness

- Apps Script: additive header migration only; no row rewrite or deletion.
- Required script properties: `REVIEW_ENFORCE_ACCESS`, `REVIEW_MODE_PROXY_SECRET`, `SLACK_BOT_TOKEN`, channel mapping, optional AI webhook URL/secret.
- Required site variables: `AUTH_SECRET`, `ALLOWED_DOMAIN`, `REVIEW_MODE_APPS_SCRIPT_URL`, matching `REVIEW_MODE_PROXY_SECRET`.
- Legacy variables/routes stay independent: `ACTIONS_PROXY_SECRET`, `/api/actions`, `action_upsert`, `action_delete`.
- Rollback: promote the previous complete-site deployment and keep the additive columns unused; existing rows remain compatible.

## Controlled canary still requiring explicit authorization

After an isolated backend version and complete stable Preview are separately approved: authenticate as an allowed BGM, read thread/access/history, save one uniquely labelled temporary observation, create one uniquely labelled action, post one uniquely labelled Slack discussion to the expected channel, approve its exact bound summary, verify reload/deduplication, and record Sheet rows, permalink, latency, and rollback identifiers.
