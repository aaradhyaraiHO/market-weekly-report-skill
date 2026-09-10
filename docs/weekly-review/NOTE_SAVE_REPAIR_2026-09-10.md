# Mini Audit note-save repair — 10 September 2026

## Scope and evidence

The user reported CE3286 / CSEE / August 30 staying on “Saving…”. The existing
“check” note was subsequently confirmed saved at 10:52, including in an
independent report tab. It was not resubmitted, edited or deleted for this repair.

The old note client used the same 90-second deadline as AI jobs. A lost write
response had no durable read-back check. New-note duplicate detection occurred
before the mutation lock, and a slow pre-save comments read could replace the
newly confirmed local list. Production logs contained intermittent upstream
failures, but did not establish the precise cause of this particular slow save
or the previously observed authentication failure. Do not claim otherwise.

## Repair

- Ordinary note writes have an 18-second proxy deadline and a 20-second browser
  deadline. AI summaries retain their existing deadline.
- At eight seconds the existing status area explains that saving is continuing
  and the draft is retained. No spinner animation, layout change or auto-resend
  was introduced; feedback remains in the existing accessible status element.
- An uncertain write is followed by one fresh, exact-identity read (10-second
  browser deadline). Success requires a stored comment ID and matching body,
  market, CE and week; otherwise the draft remains with a retry explanation.
- New manual-note retries reuse their request key. Duplicate detection and
  insertion now share the mutation lock. Exact replays do not rewrite a row;
  changed/deleted-note key reuse fails visibly. Existing edit revision history
  and compare-and-set checks remain in place.
- An older background read cannot hide a newly confirmed saved note.
- Browser-session expiry and backend signed-identity rejection have distinct
  errors. Signature canonical sorting and secret whitespace treatment now
  match the backend. Auth checks and access permissions were not relaxed.

This bounds waiting and handles uncertain outcomes safely; it does not promise
that Google services or the network will never be slow. Signing normalization
is hardening, not a proven explanation of the earlier intermittent error.

## Release gates

- All 324 baseline tests passed in the shared checkout, including an unrelated
  bucket-cleanup test that is excluded from this repair's changes.
- New runtime tests cover timeouts, lost/invalid responses, exact read-back,
  mismatched records, session/backend auth, single writes, duplicate-safe retry,
  the mutation-lock race, eight-second feedback and late-read protection.
- The exact candidate passed a local simulated browser save. This is not
  counted as a production integration test.
- Candidate `.cache/weekly_report/note_save_release_2026-09-10` upgrades 111
  frozen V2 pages from `sidebar_release_2026-09-10`. Its adjacent receipt passes
  original payload/order preservation and retains preview/latest-week routing.
- Backend immutable version **19** is independently verified on the existing
  endpoint. SHA256:
  `eae194565967050fe27963e6a3b8daddc6c0eaacd2515f72ddc038b5cf0e6d18`.
  First deployment GET was stale; a fresh read confirmed activation without
  repeating the write. Manifest, editable HEAD and other deployments match
  the pre-change capture. Rollback is version 18. Activation receipt:
  `.cache/weekly_report/note_save_backend_2026-09-10/activation-receipt.json`.
  This source hash supersedes the backend reference captured while the
  frontend artifact was packaging; frontend assets were already final.

## Preservation baseline

All 29 current/history workbook tabs were captured read-only before activation:
`.cache/weekly_report/mini_audit_followup_backend_2026-09-09/note-save-before-*`.
Backend baseline SHA256:
`b4c8f6aed3214f9ad24dde39f1c38dd1c6921bc61b834cc633dca2a913ef0d03`.
History baseline SHA256:
`544fae8bba52f7e7067fce8f3fe4c0f69624560470da0fc367e0f5465051a93f`.
No report regeneration, alert reposting, OKR/monthly changes, storage migration
or direct Sheet mutation is part of this repair. Production verification will
use one explicitly labelled CSEE dummy note through the ordinary report UI.

## Production verification

Frontend deployment `dpl_EDhKpPA3QTDVBRKYrD7GBT717vAC` is READY and promoted to
`https://market-notebook.vercel.app`. The alias was independently resolved to
that ID. Immutable URL: `https://market-notebook-qnjqo6q2y-headout.vercel.app`.
The prior frontend remains available for rollback as
`dpl_7hwEu84YY4fpred9HD8VsihyGR4F`.

On this exact frontend / backend v19 pair, in a separate authenticated browser
tab (the user's active tab was not reloaded or altered):

- Created one verification-only note in CE3286 / CSEE / August 30 using **Save
  note**, not Slack send. At 8.47 seconds the new progress message was visible;
  at 15.20 seconds the stored note and “Note saved.” were visible. These are
  browser observation bounds, not exact server latency. No resend was needed.
- Reloaded and confirmed the identical note next to the unchanged original
  “check” note.
- Edited only the new dummy note. “Note updated.” was observed within 9.71
  seconds; the edited text survived another reload. Neither save produced an
  authentication error.
- Independent storage reads confirm exactly one dummy comment:
  `cmt_dd6a3848-aa7c-4801-afec-59e78cf3cbf6`, request key
  `note_1789019569690_408327d4`. Created `2026-09-10T05:52:51.971Z`, edited
  `2026-09-10T05:53:56.952Z`. Its original text is retained as a revision event.
- All pre-existing rows and headers across 29 tabs are unchanged. The historical
  workbook is exactly unchanged. Only one dummy comment, one revision event and
  one report-view telemetry row were added. No Slack source, summary, binding,
  alert, existing note or current business action changed.
- Preservation receipts are `note-save-final-preservation.json` and
  `note-save-dummy-receipt.json` in
  `.cache/weekly_report/mini_audit_followup_backend_2026-09-09`.
- Alert ledger SHA256 remains
  `14ad1074ae3bbd3457cfd0d1221d0d1b494b926a489702e645df80926151fe4f`.

Timeout/response-loss/auth-error injection and concurrent retry behavior have
regression coverage; those failures were not artificially induced in production.
Normal live save/edit and persistence were verified. This is a save-resilience
repair, not a claim that all upstream latency or transient failures are removed.
The dummy note is intentionally labelled test-only and retained with its history.
