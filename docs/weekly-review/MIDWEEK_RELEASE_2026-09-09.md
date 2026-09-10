# Mid-week Mini Audit release — 9 September 2026

## Scope and preservation

The user approved deploying the saved-note Mini Audit follow-up and explicitly
required preservation of current comments and all ongoing review activity.
This release does not regenerate snapshots, refresh business metrics, change
report weeks or URLs, repost alerts, migrate storage, or modify OKRs.

Frontend artifact: `.cache/weekly_report/midweek_mini_audit_release_2026-09-09`.
Machine receipt: the adjacent `_receipt.json` file. Baseline is the currently
deployed `.cache/weekly_report/integrated_release_2026-09-09` artifact.

- 111 V2 pages: 92 dated pages and 19 latest aliases.
- Every pre-existing embedded payload value, row order and list length compared
  recursively and preserved. The only additive report data is mover `yoy_abs`,
  calculated from the CE revenue and LY operands already in that same page.
- 132 unrelated files, including monthly/V1 pages, ledger and auth assets,
  verified byte-identical. Incomplete-week notices preserved.
- Latest remains August 30–September 5; September 6–12 remains a dated preview.
- Source freeze: view `9254930c1656d7d59cb377c62d9b32085be7b08e47c7b648dc0080a84b374a82`;
  backend `429d69be805496c482a043ce869637996d4f31c251032255583331f0fdca175d`.

The weekly-report skill supplied frozen-source and cutover gates. The interface
review skill guided responsive checks; no new design framework was introduced.

## Verification before promotion

- 319 automated tests passed, plus actual-JavaScript runtime regressions and
  `git diff --check`.
- Explicit selected-week commentary query avoids losing old selected weeks
  behind a latest-eight-record limit; full CE memory remains independently read.
- A saved summary is excluded from memory only when actually rendered inline.
  Missing/conflicting discussion bindings therefore do not hide saved content.
- Saved-note and edit controls inspected at 390px and 1280px. Movers inspected
  at 768px, with dollar-first display and secondary percentages. No page overflow;
  viewport overrides reset. Note saves used a separate local-only fixture server.
- Backend task captured all 29 tabs across current and historical workbooks,
  including the new second comment since the prior release. See
  `MINI_AUDIT_FOLLOWUP_PRESERVATION_2026-09-09.md` for guarded activation and
  exact-row preservation evidence.

## Activation and remaining live checks

Production build started with alias promotion disabled. Final deployment,
backend preservation and authenticated live checks are recorded below once
verified. No dummy Slack message or existing business-note edit is permitted
as a test fixture. A genuine note/CE has been requested for the new-send test;
without it, that path must remain explicitly unverified on this exact release.

Rollback anchors: frontend `dpl_4Y8NJeuJR1WReyqoA1NSmdU6i8HX`
(`market-notebook-aav8l9fnn-headout.vercel.app`) and existing backend version 16.
Rollback changes code only, never restores an old workbook over current records.

## First activation and live findings

- Frontend `dpl_DSRYByVSkS1oZFcre1nzbbFZmZ7H` promoted successfully to the existing
  production domain. Backend immutable version 17 is active on the same endpoint.
- Backend pre/post activation: all 29 tabs were exactly unchanged, including
  cell values, headers and row multiplicities. No concurrent new rows appeared.
- Live CE2567/August30 displayed both existing comments, including the newest
  manual comment, and the approved 17:17 summary inline under discussion 2.
  Opening and cancelling Edit retained the original note; no save was submitted.
- One Summarize repeat returned “Discussion updated.” Original summary,
  1 suggested / 0 open / 1 completed, and both notes retained. Independent
  after-repeat snapshot: all 29 tabs again exactly unchanged; no duplicates.
- A fresh load exposed intermittent 15-second read timeouts: the weekly summary
  could appear absent without an error, while failed suggestions could display
  “All done.” A normal Retry recovered the saved summary and counts. This was a
  presentation/read failure, not deletion; storage equality was independently
  verified. It must not be called a flawless live verification.

## Read-failure hardening follow-up

The additional frontend-only candidate is
`.cache/weekly_report/midweek_mini_audit_readsafe_release_2026-09-09`.
Backend version 17 and all report data stay unchanged.

- Selected-CE reads allow 45 seconds, matching the existing history read budget.
- Loading saved discussion is explicit; a failed read shows Retry discussion
  and states that existing notes/summaries were not removed. Previously loaded
  summary content remains visible; Summarize is disabled until its read succeeds.
- Failed suggestions/actions are labelled unavailable rather than complete/zero.
- 320 automated tests and actual-JavaScript regressions passed. These cover
  loading/error rendering, retry availability, preventing premature summary
  writes, and preserving a cached summary after refresh failure.
- Frozen view SHA256:
  `c5ad403c76a33b0de83fcbb846a79f148842a345528be5fe9c89fa33dc40df76`.

Final promotion and verification are recorded after this candidate is live.

- Read-safe frontend promoted: `dpl_EeMqm8DAWfhYYpo4X8w4u9MXaMqe`, immutable
  `market-notebook-pigzsln8v-headout.vercel.app`. Two archive-upload attempts failed
  before creating a deployment; the standard file-upload path succeeded without
  dropping or regenerating any site content.
- All **38/38 authenticated production routes passed**: latest and dated
  September 6 for north-america, italy, oceania, france, united-kingdom, iberia,
  csee, nordics, east-asia-jpn-sk-hk, sea-sin-tha, united-arab-emirates, gcc,
  north-africa, rest-of-mea, benelux, south-america, mexico-central-america,
  headout and csee-nordics. Latest labels August 30–September 5 with no preview
  notice; dated September 6 labels September 6–12 with the preview notice.
  Mini Audit is present everywhere intended and excluded from Headout.
- Fresh production load showed the new explicit loading and unavailable states.
  Retry discussion recovered the original approved summary. Both notes and
  1 suggested / 0 open / 1 completed remained intact. An occasional upstream read
  failure therefore remains a reliability issue, not a missing-record issue.
- A final API-only bounded GET retry is being prepared. POSTs must never be
  retried automatically. All report HTML will be preserved byte-for-byte.

## Final read-retry candidate

- Artifact: `.cache/weekly_report/midweek_mini_audit_resilient_release_2026-09-09`.
- The API-only staging receipt verifies all **230 HTML pages byte-identical**
  and every unrelated artifact unchanged. Only `api/review.js` is replaced.
- Proxy SHA256: `b316d0b9bacfe3425641f20225eba2ed0f3850e7498f2ebfc9bed0434ba9242d`.
- GET transport/body/5xx failures retry once, with 20 seconds per attempt;
  HTTP 4xx and business validation errors do not retry. The active backend
  rejects mutation actions over GET. POST remains a single attempt, with
  authenticated identity, signing and server-only credentials unchanged.
- All **321 automated tests passed**, including actual-handler network failures,
  body deadlines, timer cleanup, POST single-attempt and authentication tests.
  Syntax and `git diff --check` passed.
- Standard Vercel upload transferred only the changed 6.3KB proxy; no report
  regeneration, new Slack posts or review-store mutations were performed.

## Final production verification

- Promoted and independently inspected production **READY**:
  `dpl_42kTYc2YkRwhMffBVpjENTfXtZBy`,
  `https://market-notebook-2wriifj2o-headout.vercel.app`, served by the unchanged
  `https://market-notebook.vercel.app` domain. Backend remains version 17.
- Repeated all **38/38 authenticated latest/September 6 route checks on this
  exact final release**. All passed the date, incomplete-preview and Mini Audit
  visibility assertions described above. All report HTML is unchanged from the
  previously verified read-safe artifact.
- A fresh CE2567/August30 production load resolved without manual Retry:
  both existing notes, the approved 17:17 discussion summary, and 1 suggested /
  0 open / 1 completed remained intact. No test note, edit-save or Slack send
  was submitted to existing business records.
- Final read-only comparison of **all 29 tabs** preserved every original row,
  cell and header. No original row was removed or modified. One concurrent
  telemetry append (150 → 151) was retained; business tables and the entire
  historical workbook were unchanged. Private evidence:
  `.cache/weekly_report/mini_audit_followup_backend_2026-09-09/final-release-preservation.json`.
- Final backend raw SHA256:
  `e8efdbb805d84b5a091b9f9cf16804367d42c4dd9a042b69a12844bb8b915490`.
  Historical raw SHA256:
  `544fae8bba52f7e7067fce8f3fe4c0f69624560470da0fc367e0f5465051a93f`.

### Remaining explicit live gate

**A genuinely new Slack delivery and new AI summary are not yet verified on
this exact release.** The user has been asked for a real note and CE; no response
has supplied one. The existing source was already summarized, so a repeat is
not evidence of new-source processing. Do not mark that end-to-end gate passed,
or post dummy business feedback to manufacture a pass. Unsaved browser drafts
must be saved before refreshing; storage preservation does not persist them.
