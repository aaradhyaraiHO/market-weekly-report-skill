# Mini Audit E2E acceptance run

## Production activation — 9 September 2026

User approved activation and explicitly retained the September 2 MMP execution
export. Current shared checkout: 312/312 tests pass; prior headline assertion is
already corrected. Approved Headout September target remains unavailable.

The first production attempt failed Review reads and was rolled back to
`dpl_2ch1dV3w3oG3haZftBTvsz1PXD2p`. Aligned the three Production signing secrets
(proxy, ingest, summary) to existing production Apps Script property values
without printing them; backend properties and Preview credentials were not
changed. Rebuilt the tested Preview artifact for Production and explicitly
promoted after rollback left the main URL pinned.

Final live deployment: `dpl_D2euUUHotTC4BJckLrpeFzXF6iGE`.
Production backend: existing bound project, immutable version 15.
Production browser checked the September 6 North America report, CE7006:
- Google sign-in and authenticated Review reads succeed.
- Existing discussion #2, four completed actions and prior weekly memory load.
- Full CE history refresh displays 11 sources.
- Transcript AI/ingestion returns 0 CE suggestions for an explicit technical
  connectivity transcript with no business content, showing it as unmatched.
- Repeat import reports Previously imported and adds no duplicate batch/actions.
- Manual Slack summary reports no new replies; prior summary stays in memory.
  This does not claim that a new Slack summary was generated during this smoke.
- All original rows in six Review tables are unchanged, including all 11 thread
  rows (not only rows with modern binding IDs). Added one new-week review row and
  one frozen test import batch. Work count remains 19; suggestions remain 36.
- No Slack messages or business actions created; no historical row deleted.

The production report is left open with CE memory collapsed. Earlier statements
that production is unapproved or unchanged are superseded by this activation.

## Transcript-only meeting imports — 9 September 2026

User removed Granola link import from scope after the plan restriction was verified.
The report now offers one transcript box and Find CE summaries & actions. The
link field, handlers and client methods are removed; the Review proxy no longer
accepts link submissions. Packaging removes inherited granola-link, granola-pull
and granola-review endpoints, and preflight rejects their reintroduction.
Existing Sheet history and meeting provenance remain readable. No Granola plan
upgrade, replacement key or REST-link test is needed for release. Earlier Granola
failure evidence below is historical, not an outstanding acceptance gate.

Validation for this removal:
- 144 Mini Audit/Review tests passed, including transcript import/replay runtime,
  approval/memory regressions and stale-route removal during next-run packaging.
- Full suite: 311/312 passed. Existing untouched headline/template test
  `test_v2_weekly_comparisons_use_relative_percentages_everywhere` fails because
  the template contains “percentage points”. This separate issue remains open.
- Full-site preflight passed; all 94 historical V1 report archives kept their bytes.
- Local browser fixture verified one transcript box, extracting suggestions for
  two CEs, opening Kennedy Space Center and seeing the pending action/owner/due
  date. Screenshot inspected. Simulated services only for this UI check; earlier
  live transcript results remain documented below.
- JS syntax and git diff whitespace checks passed. No Sheet records, API keys or
  production deployment changed for this removal.
- Preview deployment `dpl_CiKhHAWghgqhK97x1zngfkZoBvw9` completed and the stable
  `market-notebook-review-preview.vercel.app` alias was updated. Authenticated
  browser reload confirmed the transcript-only form on the August 9 report.
  The original production `dpl_2ch1dV3w3oG3haZftBTvsz1PXD2p` remains unchanged.

## Manual workflow follow-up — 9 September 2026

This section supersedes the locked-Mac / unidentified-writer blocker below.

- User explicitly requested removal of the five-minute sync.
- Found the writer in the Sheet-bound **WBR Review Backend** project
  `1PcyDdbEK8zpSm_L8lhopGOIJlode56Y1bMBSiABcQ0GoBqcIpcKRRsP6`.
  Its `reviewWeeklyBase` omitted base thread-binding fields. The sole trigger
  was `reviewSyncActiveThreads`, time-based, executing HEAD.
- Deleted that exact trigger through Apps Script UI. Verified **0 triggers**.
  Changed only the legacy HEAD installer so it removes pollers and never
  recreates one. Legacy deployed versions and production website are preserved.
- Candidate backend version **6** retains the Preview-only deployment ID and
  uses manual summarization. Normal Summary click restored CE7006 binding #2.
  Subsequent Sheet read confirmed base and summary IDs both equal
  `thb_3e93b699-c323-4ec1-9b7a-d51f5c8db742` with discussion number 2.
- Meeting import adds `review_meeting_imports` to the same workbook. It freezes
  the first extraction before materializing suggestions; retries replay it and
  read current approved/dismissed states. Suggestion uniqueness is checked under
  the script lock. No comments/actions are created without existing approval.
- Pasted transcripts surface unmatched CE passages for reconciliation, with a count and quoted text.
  User is asked to clarify those passages with CE names/IDs. Explicit owners
  and dates are preserved; oversized transcripts fail visibly without truncation.
- Granola adapter now reads documented transcript arrays and `summary_text` /
  `summary_markdown`; transcript takes precedence. Exact share-link lookup stays
  server-side. Same meeting/week reuses its frozen extraction. A real Granola
  link is still required for live integration verification.
- New behavioral coverage verifies multi-CE separation, ambiguity, replay after
  approval/dismissal, first-extraction ownership, empty imports, Granola transcript
  shape, and manual trigger setup. **302 tests pass**, full-site preflight passes.
- Next-week prepare-only all-market/Headout run started for `2026-09-06`.
  Do not infer completion until the release receipt is checked.
- Live multi-CE canary `MINI-AUDIT-E2E-2026-09-09-B` passed: Dorney7006
  action with Aaradhya Rai / 10 Sep; Chicago `18 - Chicago` observation only;
  one unnamed park passage stayed in the inbox. No Chicago work was changed.
- Approved Dorney suggestion `sgg_d921e9a6-964e-4899-8aba-e5f183b4cdda`;
  action `wrk_b2505f17-2c7b-4b2f-a967-a62938e516ed` completed at
  `2026-09-09T08:05:45.661Z`, origin week and source reference retained.
  Chicago fixture `sgg_403882fa-d027-4845-9db0-8de5f8baf562` dismissed.
- Repeating identical transcript after both decisions returned **0 pending,
  2 already reviewed**, same durable IDs. The first batch is stored as
  `meeting:4c9049141366d0c9232ba8a56060a1ff55c41457f7e8960285aad0f86e43a718`.
- At 08:05 UTC, over two former five-minute cycles after trigger removal, both
  base and summary thread bindings were still #2; reload showed saved summary.
- Granola API key presence verified via Vercel env metadata (no secret read).
  Actual meeting access remains unverified pending a designated link.
- Final Preview: `dpl_9bmuoct5jan1f62ZM1YqoriNCSQU`,
  `market-notebook-m6c1f0iq4-headout.vercel.app`. The stable Preview alias points
  here. Native UI verified the quoted unmatched passage, zero empty CE buttons,
  and replay after a full page reload. Backend version 6 additionally locks
  unmatched inbox insertion against concurrent duplicate retries.
- Granola link lookup also handles list responses without `web_url` by reading
  bounded note metadata, then fetching the transcript only for the exact target.
  Lookup has a 30-second overall deadline. A stored import skips provider reads
  entirely on replay. Route tests use the official list-response shape and reject
  any attempt to fetch another meeting's transcript. Documentation references:
  https://docs.granola.ai/api-reference/list-notes and
  https://docs.granola.ai/api-reference/get-note.


## Next-run recovery — 9 September 2026

- User completed the authorized Google ADC refresh with Drive read-only scope.
  The authoritative target query now succeeds; all 17 market goal records are
  current for September. Headout's source query returns no approved September
  target. A separate read-only inspection found no Headout/company target rows;
  global target remains explicitly unavailable, with no synthetic roll-up.
- Original all-market and Headout snapshot generation finished. The first run
  failed only at alert generation due to the missing Drive scope. Recovery uses
  the canonical plan from the combined target/parity gate onward, with a separate
  receipt: `.cache/weekly_report/mini_audit_targets_recovery_2026-09-06.json`.
  SHA-256 checks confirm all 18 core snapshots remain unchanged.
- V2 publisher now stages the complete Mini Audit routes/modules and injects the
  UI during each V2 package run. Broken V2 mounts fail staging; Headout is excluded
  and legacy V1 archives retain their bytes. Actual-renderer packaging/reinjection
  tests pass. Full baseline suite: **312 tests**, `git diff --check` passed.
- Complete candidate notebook passes Review preflight and preserves all **94 V1
  archives** and the monthly homepage from the existing Preview package. This is
  a local package plus Preview deployment only, with no production activation.
- Canonical 18-report parity gate, CSEE/Nordics shared report, alert readiness and
  notebook staging passed. Market alert dry run and next-week Preview browser
  verification were in progress at that checkpoint.
- Next-week Preview is now `dpl_7q8CRP1r2s6JgSbUf8xg79X3cW6k`,
  `https://market-notebook-mkfxpvm15-headout.vercel.app`; the stable Review Preview
  alias points to it. Use the stable domain for its registered Google callback.
- Native next-week browser check passed at
  `/weekly-report-north-america-2026-09-06?view=review&ce_id=7006`:
  existing discussion #2 is selected, Open 0 / Completed 4, August 30 weekly
  memory contains original note, human Slack reply, archived/current summaries,
  four completed follow-through records and 11 sources after full refresh.
  Memory was collapsed again afterward. No new notes, Slack posts or action
  changes were needed for this carry-forward check.

- Final recovery receipt status: **passed**. All 17 market alert/RCA dry runs
  completed; no Slack alert broadcast. Headout target source warning remains.
  MMP evidence uses the configured 2 September 2026 export.


## Production preparation and real Granola test — 9 September 2026

- User authorized using the existing temporary OpenAI key in Production. Vercel
  scope changed to Production + Preview without revealing/copying its value;
  Production `REVIEW_AI_PROVIDER=openai` added. No production redeploy performed.
- Prepared immutable backend version 15 in the existing bound project:
  `AKfycbwJ5HWaNwt2cikPHiD4xewKNYrIgI-MKpVe306M4zkiBXJQfiRSPppxfSoqAX-o3aQy`.
  Frozen content equals tested source. Original HEAD restored and verified;
  existing versioned deployments untouched. Endpoint switch awaits activation.
- User-provided meeting:
  `https://notes.granola.ai/t/3bf18bb5-b0e8-4130-9945-40cbf598a4f0-008umkv4`.
  Tested through Add meeting notes → Read link in the North America August 9
  report, matching the meeting’s August 11 date. Vercel log at 14:48 IST:
  `Granola list lookup returned 403: request failed`. Report displayed the
  integration-access error. Extraction was not reached; no suggestions approved
  and no messages sent. This is a failed live link test, not a passing fallback.
- Granola connector can read the user’s selected meeting, but its access is
  separate from the report’s REST API key. User asked to enable Personal notes
  scope or replace the Vercel Granola credential. Official setup reference:
  https://docs.granola.ai/introduction.
- Native Granola → Settings → Connectors → Personal API keys inspected on
  September 9: current account shows Basic Plan; the existing key is Active and
  already grants Personal notes and Public notes. The page explicitly states
  “API is available with Granola Business”; Create new key is disabled. This
  corrects the earlier assumption that the Personal notes scope was missing.
  Eligible API plan access is required before retesting the report integration.
  No subscription purchased, key replaced, Vercel secret changed, or deployment
  performed during this inspection.


## Earlier investigation — superseded by the manual workflow follow-up

At the earlier checkpoint on 9 September, status was **not production ready: recurring legacy binding reset; investigation blocked by locked Mac**.
The 301 passing local tests and fixture browser walkthrough are supporting checks;
they do not establish real Slack delivery, Sheet persistence, AI quality, or latency.

## Follow-up finding — 9 September 2026, 00:12 UTC onward

The longer stability check **failed**. This supersedes the short final version-4
binding checks below. `review_weekly_commentary!AK13:AL13` is blank again, while
`AM13:AN13` still contains the approved summary binding and discussion number 2.
The same row reports `sync_status=summary_delayed`, `last_error=invalid_response`,
and version 11. Its summaries, original Slack threads, archived timeline event
and completed work are retained; the recurring write clears the weekly binding.

Native Sheets cell edit history shows repeated writes by Aaradhya Rai at 05:38 and
05:43 IST. The five-minute pattern and old failure shape indicate an older sync
writer, but its exact project/deployment has not yet been identified. The separate
Preview script's Executions UI has no Time-Driven executions in the past seven
days. Standalone-project discovery found no other relevant Review project.
The next diagnostic step is the Apps Script project bound to **WBR Review Backend**,
opened through that Sheet's Extensions → Apps Script menu. Do not disable an
unidentified trigger or silently route production to the candidate.

Browser discovery then failed because the Mac is locked and automatic unlock was
unsuccessful. User unlock is required to inspect that bound project. A real
Granola meeting link suitable for importing review suggestions was also requested;
no link has been provided. The production-readiness follow-up is paused at these
user-required blockers. Multi-CE import/replay, real Granola retrieval and the next
full report-generation gate remain unexecuted. No production alias was changed.

## Latest verification — backend version 4

The user authorized Google Apps Script API access. It is enabled. Script
`1caSJvFHaBbfT7pu__KH9fu00tuQfCyLuY1Yay5gnWT3kDuNJB897ZjDa` now has immutable
versions 3 and 4 in addition to its original versions. The Preview-only deployment
`AKfycbyJ6A3uDqyi58vNLX-nkM8NRNcoZp-uaRV1uxiyWXTkUHBNsvJC90bUmtZAF19UqzS8`
executes version 4. A version read verifies exact equality with the tested local
source. Vercel's Preview-only `REVIEW_MODE_APPS_SCRIPT_URL` points to this URL;
`REVIEW_AI_PROVIDER=openai` is now saved as a Preview project variable. The
replacement key stays in Vercel. Existing Vercel deployment protection remains on.

- **Slack summary passes:** the real human reply about positive seasonality was
  summarized and saved. `/api/review-summary` returned HTTP 200 in deployment logs,
  using the actual Apps Script callback. The report reached its saved state within
  14 seconds of clicking. Repeating with no new messages left the summary timestamp,
  version and suggestion count unchanged.
- **Approval passes:** the expanded editor approved a labelled test check into Open
  and CE memory. Work `wrk_5f93707e-7f58-4547-b312-541f7c98140c` was then completed;
  independent Sheet reads confirm its origin week, due date and original Slack
  source reference/URL survived completion. All three test work items are complete.
- **New thread isolation passes:** a new parent at
  `https://headout.slack.com/archives/C0BQHT29WMB/p1788911178445529` has binding
  `thb_3e93b699-c323-4ec1-9b7a-d51f5c8db742`. Direct Slack reads verify continuation
  under that parent. Its summary cites only the new thread's source record. The
  previous binding is retained as replaced, with predecessor/successor links.
- **Full memory and cross-report visibility pass:** the 23 August report reads the
  same CE's work and 30 August history. A fresh full-memory load exposed Sheet date
  coercion in archived-summary `review_week` and thread week fields. Version 4
  normalizes all date-only fields in the Sheet timezone and writes them as text.
  After deployment propagation and Refresh, both summaries appear in the 30 August
  block; the earlier summary is not lost or hidden under an undated section.
- **Additional binding persistence verification:** the binding was observed blank
  once during the deployment transition, while its approved summary binding and
  archived source remained intact. The exact writer is not established. Re-sync
  recovered the binding using the exact starter timestamp, including with two
  threads. The final version-4 continuation and fresh-page reload retain both
  binding fields and the approved summary. Independent Sheet reads confirm version
  11, binding `thb_3e93b699-c323-4ec1-9b7a-d51f5c8db742`, discussion number 2, and
  matching summary binding. The reset has not recurred in those final checks; no
  background-writer or long-duration stability claim is made.

The initial AI summary inferred a follow-up from the factual human reply. It
remained a proposal, not assigned work. For the approval test, its text was replaced
with an explicit TEST ONLY verification and completed. This validates the review
gate; it is not a blanket model-quality acceptance. Granola-link retrieval,
multi-CE ambiguity handling, and a future report-generation/cutover run remain
outside this verified canary. The earlier sections below retain the test history
and are superseded by these latest results where stated.

## Real canary results — 9 September 2026

This section supersedes the initial readiness status below. The user designated
`#adhoc-north-america` for testing. Candidate UI/API code was deployed to Preview
only and assigned to the established authenticated preview alias:

https://market-notebook-review-preview.vercel.app/weekly-report-north-america-2026-08-30?view=review&ce_id=7006

Current preview deployment: `dpl_BvYeLCHsrcdsRQL4fMJQUoAw4avk`
(`market-notebook-44qz9706m-headout.vercel.app`). Previous preview alias target
before this canary: `market-notebook-omrpzo5le-headout.vercel.app`.
Production aliases were not changed. Preview now uses the candidate Apps Script
backend, version 4, through a separate deployment; existing version 1 and version 2
deployment IDs were preserved.

Test identity: `MINI-AUDIT-E2E-2026-09-09-A`, CE `7006` (Dorney Park Tickets),
report week `2026-08-30`. The run used the existing **WBR Review Backend** Sheet
(`1iM8v31-Ti7le_Y-6Nivn--ddqPJ43EvXCurBL2h3RmA`), not a new isolated test Sheet.
Every created note/message/action explicitly says TEST ONLY and no business work
is required. Existing discussion records were not edited or replaced.

| Check | Result | Evidence / limitation |
| --- | --- | --- |
| Candidate preview authentication and CE drawer | PASS | New split Mini Audit UI loads correct CE 7006 and frozen 30 August metrics. |
| Save note through report | PASS | Independent Sheet read found one comment `cmt_e396faca-6a7b-4eb2-a589-c3bab5147ef6`, correct CE/week/author and exact writeup. |
| Start Slack thread through report | PASS | One parent in authorized channel `C0BQHT29WMB`, timestamp `1788906967.894319`; direct Slack read verifies CE/week/writeup/report link. |
| Continue same Slack thread through report | PASS | Direct Slack read verifies reply under the same parent. Natural-language owner text resolved Aaradhya Rai to Slack user `U03QFJSE6D6`; no other participant was tagged. This is not a full mention-picker acceptance test. |
| Human participant reply | PASS ingestion and summary | Direct Slack read and Sheet suggestion `sgg_9602723a-1b0c-4970-b15b-3c7fc33d51d5` confirm the exact human reply with its Slack source URL. |
| Manual action create and complete | PASS | One canonical work record `wrk_3debba76-547d-428d-b3c4-d8ea460a75fa`. Independent Sheet read confirms `complete`, origin week unchanged, `closed_at=2026-09-08T22:38:28.382Z`. |
| Inline memory projection | PASS | Saved note, approved meeting observation, and both completed canonical actions appear under 30 August. |
| Full CE memory refresh | PASS in updated Preview | Opening the disclosure completes the full-history request and renders memory without the earlier timeout error. The per-execution backend cache optimization is deployed. Final execution-table samples show memory/read requests completing in roughly 1–6 seconds; this is not a load test. |
| Backend thread binding compatibility | PASS final version-4 checks | Legacy single-thread recovery, new-parent binding, continuation and fresh reload pass. A transient deployment-transition reset is documented above. |
| Pasted meeting transcript | PASS single-CE extraction | After the user saved a replacement Preview key, OpenAI produced one labelled observation and one labelled action for CE 7006. UI reports 2 suggestions / 1 CE; Sheet confirms both, including Aaradhya Rai and due date 2026-09-10. Multi-CE/ambiguity acceptance remains outstanding. |
| Proposed-action approval and completion | PASS | Approval removes the pending card immediately, opens the saved action and shows it in memory. Sheet confirms `wrk_7c8613f0-9d67-498e-acc9-d750d1155073`, subsequently completed; UI shows Open 0 / Completed 2. The expanded editor also passed on a Slack-derived test check, subsequently completed. |
| Summary, second-thread isolation, cross-report retention | PASS | Two source-isolated summaries, separate thread parents, exact continuation and reads from the 23 August report are verified. A future report-generation cycle has not been executed. |
| Granola link and multi-CE meeting ambiguity | NOT TESTED | Single-CE pasted transcript extraction passed; these additional acceptance cases remain outstanding. |

Test Slack thread: https://headout.slack.com/archives/C0BQHT29WMB/p1788906967894319

The inspection found an Apps Script project named **WBR Review — Isolated Service**
with versions 1 and 2 dated 31 August. Its exact binding to the preview environment
has not been confirmed: the CLI environment export returned empty sensitive values
and was removed. The Cloud-project API was subsequently enabled and source/version
reads now succeed. The user subsequently enabled account API access. Version 4 is now deployed to
the separate Preview endpoint described above.

Added bounded provider-error classification to transcript extraction so logs
distinguish credits, authentication, model and schema failures without printing
credentials or meeting content. Syntax checks, all **299** local tests and
`git diff --check` pass. No claim of full E2E completion or production readiness.

## Blocker fixes prepared — 9 September 2026

- CE-memory reads reuse the Spreadsheet handle and table rows within one Apps
  Script execution. Writes invalidate cached rows; locked upserts re-read under
  the lock. The browser loads full memory only when its disclosure is opened,
  with a bounded 45-second cold-read timeout.
- Suggestion approval applies confirmed comment/work records immediately and
  removes the approved card without waiting for history reads. Duplicate clicks
  are suppressed; the original CE/week is retained while the request runs.
- Both compact Approve and expanded Save & approve controls are wired. Status
  updates preserve source references in both the browser payload and backend.
  Date-only fields from Sheet Date cells use the spreadsheet timezone, including
  proposed and accepted due dates, preventing an unintended previous-day display.
- The Review proxy strips browser-supplied automation credentials and adds the
  project's existing `VERCEL_AUTOMATION_BYPASS_SECRET` to a signed sync POST.
  Apps Script accepts it only after HMAC verification, uses the Vercel protection
  header, and retains it as a Script Property for scheduled sync. Neither the
  header nor credential is returned to the browser. Deployment protection remains
  enabled.
- The previously tested thread-binding fixes are included in the same candidate
  Apps Script source. Existing deployment versions are preserved.

Local verification: 301 tests, V1 baseline verification, complete-site package
preflight and whitespace checks pass. Runtime coverage includes row-cache
invalidation/copy isolation, rejecting unsigned credential injection, scheduled
callback headers, and immediate approval while refresh is deliberately stalled.
Additional runtime checks cover both approval controls, preserving source fields
on status updates, and date-only values in the spreadsheet timezone.

The completion test exposed source-reference loss in the old backend. The exact
reference was restored only on the TEST ONLY action in `review_work_items!L18`,
from its approved suggestion, and verified through an independent Sheet read and
the native Sheets formula bar. Its complete status, due date, and timestamps were
unchanged. This is a repair of test data, not evidence the backend fix is deployed.

Cloud-project and user-level Apps Script API access are enabled with user
authorization. The initial source write was rejected before that approval; the
subsequent upload and Preview deployment succeeded.

The browser and backend cache, timezone, thread-binding and authenticated summary
callback changes are deployed to Preview. Production aliases remain unchanged.

## Test environment

### Temporary OpenAI option — activated on Preview

All three AI routes (Slack summary, pasted transcript, Granola link) can select
OpenAI with server-only `REVIEW_AI_PROVIDER=openai`. Set `REVIEW_OPENAI_API_KEY`
in Vercel **Preview**; the adapter deliberately does not borrow the project's
existing `OPENAI_API_KEY`. `REVIEW_OPENAI_MODEL` defaults to the pinned
`gpt-4.1-mini-2025-04-14` snapshot. Set the provider back to `anthropic` (or unset
it) and redeploy to restore the prior provider. No Sheet migration is involved.

The adapter uses Responses structured output with `store:false`, a 45-second
timeout, and explicit rejection of refusals, incomplete responses, malformed JSON
and schema mismatches. It does not retry against another provider. The shared
server module is staged under `lib/`, and the package check rejects missing imports.
Offline runtime checks exercise all three handlers, source-reference validation,
repeat-import identity and failure before ingestion. These checks do not establish
live model quality or successful backend summary persistence.

The user revoked the pasted key and saved its replacement directly to Preview.
CLI metadata confirmed `REVIEW_OPENAI_API_KEY` as encrypted and Preview-only.
The deployment was created with `--env REVIEW_AI_PROVIDER=openai`; the provider
selection was initially a deployment override. It is now also saved as the
Preview-only project variable `REVIEW_AI_PROVIDER=openai` through the Vercel API.
Production environment values and aliases remain unchanged.

Live extraction saved suggestions `sgg_2ba6f36b-7a7e-4add-a90c-755880000d98`
(comment) and `sgg_c4b6b4af-661d-48c3-b315-f7692b612912` (action). The observation
was approved through the UI and the Sheet confirms `approved` / destination
`comment`. The updated Preview fixes the stale display; the observation appears in
memory. The action was subsequently approved and completed, with Sheet and UI
verification recorded above.

A fresh report load verified that the earlier saved note and completed manual
action survived deployment. Full-history refresh passes on the updated Preview.

Slack summarization failed with Sheet `last_error=invalid_response`. Read-only
Apps Script settings confirmed its webhook points to the correct Preview
`/api/review-summary` URL. An unauthenticated server POST received Vercel HTTP 401
with `protection.vercel_auth_enabled=true`, before route execution. No summary
request appeared in deployment function logs. This is a deployment-authentication
blocker, independent of the now-working model key. Keep protection in place;
configure approved automation authentication for Apps Script before retrying.
The callback and binding fixes subsequently passed the core Preview canary as
recorded above. No production-cutover or complete Granola/multi-CE claim is made.

Official references: [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
and [GPT-4.1 Mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini).

### Environment requirements

Use the candidate report and API package on an authenticated preview URL, backed
by a separate test Review Apps Script deployment and test Sheet using the same
schema as production. Keep the production Review Sheet as the eventual production
backend; the test Sheet is only for acceptance testing.

Record the preview URL, code revision/diff, report week, test spreadsheet and
Apps Script deployment IDs, test Slack channel ID, and participating test users.
Keep credentials in server/Apps Script configuration, never in this document.

Before sending anything:

- Verify both client routing and backend market-channel allowlists target the test
  channel. Use only designated participants for mentions.
- Start with test thread bindings. A copied Sheet can contain production Slack
  channel IDs and thread timestamps; remove or replace those in the test copy
  before writes or sync. Do not alter the production records.
- Point summary/extraction callbacks and ingestion secrets to the test deployment.
  Keep production webhooks and scheduled ingestion disconnected from the test copy.
- Use copied historical notes/Performance fixtures for historical-read checks.
  Compare real source schemas separately without altering original workbooks.
- Include authenticated report routes, `/api/review`, `/api/review-summary`,
  `/api/review-extract`, and `/api/granola-link` in the preview package.
- Verify report authentication, BGM access, Sheet header order, Slack bot access,
  AI credentials, and Granola access in their actual hosting environments.
  `review_preflight.py --server` checks environment presence only; it is neither
  connectivity proof nor complete validation of the current manual meeting flow.

The local configuration preflight on 9 September found no Review endpoint/secrets
or integration credentials in this shell. Subsequent Vercel metadata inspection
confirmed Preview has the Review Apps Script URL, proxy/ingestion/AI secrets, AI
key, Granola API key and report-auth variables configured. Values were not
exported or printed. This does not prove the Apps Script properties or backend
version are ready. External test sends require a designated test channel and
participants before execution.

## Readiness findings — 9 September

- **PASS, existing preview login:**
  `https://market-notebook-review-preview.vercel.app/weekly-report-north-america`
  signs in with the active Headout account. Use this stable alias for OAuth.
  The raw deployment URL fails with `redirect_uri_mismatch`; no auth change or
  bypass was needed to sign in through the established alias.
- **PASS, existing backend read:** old Review UI loaded persisted CE 3111 canary
  notes, its reviewed state, one completed action and an existing Slack binding.
  These are connectivity observations about the old deployment, not acceptance
  of the new Mini Audit build.
- **NOT ISOLATED YET:** old preview explicitly displays destination
  `#adhoc-north-america` and has an existing real Slack permalink. No send,
  summary refresh, note save or action update was performed during this check.
  The user has been asked to designate the test channel and mention participants.
- **CANDIDATE PACKAGE READY LOCALLY:** complete notebook staged at
  `.cache/weekly_report/mini_audit_e2e_site`; the North America current alias and
  dated 30 August report contain the new Mini Audit. Injector updated 87 V2
  market pages and excluded 11 Headout pages. The 88 older V1 archives remain
  byte-for-byte identical to their source notebook.
- **PASS, package gate and 299 local tests:** the gate now requires the transcript
  extraction route and permits V1 archives only with an explicit unchanged
  baseline. It still rejects V2 pages without Review and cannot exempt the
  requested test report. Reproduce the full-site check with:

  ```sh
  python3 scripts/weekly_report/review_release_preflight.py \
    .cache/weekly_report/mini_audit_e2e_site \
    --preserve-legacy-from /Users/aaradhyarai/analytics/market-notebook-v2
  ```

The candidate has not been deployed or assigned to an alias. Updating the test
Apps Script to the candidate version, verifying its Sheet isolation and channel
routing, and running real mutation/AI workflows remain outstanding. No production
deployment, Sheet-record edits, or external test messages were made.

## Acceptance scenarios

For each row record PASS/FAIL/BLOCKED, actual duration, browser evidence, and the
relevant stored record IDs or Slack permalinks. Do not mark a failed prerequisite
as a passing downstream scenario.

| Scenario | User steps | Evidence required |
| --- | --- | --- |
| Entry and CE isolation | Open Mini Audit; then All CEs → drawer → Mini Audit; switch between two CEs. | Correct CE data and audit side by side; no notes/actions crossing CE or market boundaries. |
| Durable note | Save a distinctive note; refresh; open in another authenticated browser session. | Exactly one stored comment ID and the same wording in weekly CE memory. |
| First Slack discussion | Write once, choose a designated test mention, start discussion. | One parent in the test channel, correctly resolved Slack user mention, CE/week/report link and stored binding. |
| Continue discussion | Send another writeup using the active thread. | Reply under the same parent; no extra parent or duplicate note caused by retry. |
| Real discussion and summary | A designated human replies with a finding, decision, unresolved question and explicit action; click Summarize discussion. | Source-linked summary reflects actual replies; uncertain points stay uncertain; proposed work awaits review. |
| Summary update | Add another human reply; summarize again; repeat with no new replies. | New content incorporated without duplicated work; unchanged sources do not create extra summaries/actions. |
| Action lifecycle | Edit/approve a proposed action; set owner/date; complete it; reload. | One canonical work ID, correct Open/Completed state, same record linked from memory. Dismissed proposals do not become open work. |
| New thread | Choose Start a new thread on a CE with an existing discussion; send; add human reply; summarize. | New parent and binding; earlier sources and approved summary retained; no unrelated old-thread content in new summary. |
| Cross-week return | Open a second dated report against the same test backend; revisit the CE; continue or create a thread. | Earlier weekly blocks and open work remain; new entries have the new report week; completion does not move an action's origin week. |
| Meeting transcript | Paste a transcript covering two exact CEs, one ambiguous CE and explicit actions; approve selected results; repeat import. | Correct CE grouping, review before acceptance, ambiguous text never silently assigned, no duplicate accepted records. |
| Granola link | Submit an accessible designated test meeting link; then an inaccessible link. | Real meeting content and provenance retrieved; inaccessible link gives a clear error and usable paste fallback. |
| Historical Performance | Expand collapsed memory and an older week; inspect Sources. | Original wording, owner, recorded status and source remain; historical status is not falsely interpreted as completion. |
| Failure and retry | Interrupt a test save; cause a controlled test AI failure; retry after recovery. | Visible error and preserved draft/prior approved summary; verify ambiguous delivery by stored ID before retry; no duplicate note, parent or action. |
| Concurrent and stale work | Use two browser sessions; update an action; switch CE/thread while summary is pending. | No silent overwrite of unrelated fields; no result applied to the wrong CE/thread; both sessions converge after refresh. |
| Access | Test logged-out and unauthorized users against preview UI and API. | No unauthorized reads/writes; no trusted actor supplied merely by client input. |
| Midweek update | Save notes/actions/thread refs, record IDs, update the preview package, refresh and compare. | Persisted IDs/content/statuses survive; same dated metrics snapshot; prior client remains compatible during transition. Unsaved refresh behavior explicitly recorded. |

## Release decision

Record actual note-save, CE-memory load, Slack-send, summary, and meeting-extraction
durations separately. Fast local fixture responses are not production measurements.
Test slow operations for visible progress, bounded failure and successful recovery.

Release requires every critical scenario above to pass on the candidate package,
with no lost records, wrong-thread posts, duplicate actions or inaccessible saved
history. Report blocked integrations explicitly. Keep the production change and
rollback plan separate from this acceptance run; passing the run does not deploy it.
