# ROI precision and Levers release — 11 September 2026

## Scope

Source commit: `a7c7305`. Only the approved Losing Money ROI WoW precision and
Levers disclosure changes are included. The separate RPC/CM1 precision and
Revenue-heading findings are not included. CSEE/Nordics aggregation remains
deferred. Existing latest routes still resolve to Aug 30–Sep 5, with Sep 6–12
explicitly an incomplete-week preview.

Candidate: `.cache/weekly_report/roi_levers_release_2026-09-11`, mechanically
patched from the exact deployed `target_platform_mobile_release_2026-09-10`
artifact. Rollback: `dpl_FCiGn87uuT2tySE5q2hyPTiqN8sc`.

## Preservation and tests

- 111 V2 pages: only two renderer functions, disclosure CSS and an additive
  Losing Money `roi_wow_pct` field changed. Every pre-existing JSON value,
  record and ordering is preserved.
- 137 other files are byte-identical, including all API/auth handlers, AI
  provider code, Mini Audit dependencies, site navigation and state files.
- All 19 latest aliases are byte-identical to their Aug 30 dated reports.
- 4,705 ROI presentation fields have valid frozen operands; 221 are unavailable
  rather than derived from rounded or mismatched evidence. Counts include
  historical, country-view and alias copies, not unique CEs.
- 348 weekly tests and the V1 baseline gates passed; whitespace check passed.
- The unrelated bucket-cleanup working changes were not committed with this
  release. No report regeneration, BQ queries, alert sends or Sheet writes.
- Alert ledger SHA256: `14ad1074ae3bbd3457cfd0d1221d0d1b494b926a489702e645df80926151fe4f`.

## Mini Audit evidence and limits

The September 10 real app-to-Slack reply test produced a new AI summary, saved
it, survived reload and produced no duplicates on repeat summarization. Exact
source bindings and all existing rows across 29 workbook tabs were preserved.
See `docs/weekly-review/SIDEBAR_RELEASE_2026-09-10.md` and its preservation receipts.

Following the save repair, backend v19 and the matching frontend also passed
live note creation, note edit and reload checks. Exactly one dummy note and its
revision were stored; the original “check” note remained unchanged. See
`docs/weekly-review/NOTE_SAVE_REPAIR_2026-09-10.md`.

These are live integrations, not just mocks. The fresh Slack source was relayed
from the app, not newly typed in a human Slack client. The full summary test was
on v18; the later v19 test covered note save/edit. Today's release preserves the
current Mini Audit runtime and APIs byte-for-byte and does not create another
dummy note, Slack reply or summary. Before deployment, an authenticated live
read again confirmed the original note, edited dummy note and saved summary.

## Interface review

Full mode within the two changed presentation surfaces; plain HTML/CSS and
existing Oak/Eevee styling. No broader layout redesign.

| Category | Evidence inspected | Result |
| --- | --- | --- |
| Typography | Actual ROI table cell and disclosure title/count at mobile width | −6.1% rendered; labels contained |
| Surfaces | Mouse click, Enter, focus outline and actual 390px CSS viewport | Open/closed states work; 22 PP rows retained; scroll width 390 |
| Animations | Scoped diff and disclosure behavior | Instant native toggle; no animation added, so 10% replay not applicable |
| Icons | Existing static disclosure chevrons | State indication retained |
| Performance | Two function replacements and additive JSON field | No new dependency or runtime fetch; broad profiling not performed |

The implementation findings and alternatives are recorded in
`levers-disclosure-2026-09-10.md`. No further styling changes were made: a custom
animated accordion and a wider layout redesign were rejected as unnecessary
scope. Physical devices and screen-reader audio are not verified.

## Activation

- Production: https://market-notebook.vercel.app
- READY and promoted: `dpl_8Vb6FBgJT2YRSSUNzLtfMWcXrGxp`.
- Immutable URL: https://market-notebook-9ud4p7fts-headout.vercel.app
- The production alias was independently inspected and resolved to this ID.
- Live North America latest report: Aug 30–Sep 5, Kennedy Space Center ROI
  WoW **−6.1%**, Levers initially closed, mouse-open retains 22 rows, Enter
  closes it. Actual mobile CSS viewport/document scroll width both **390px**;
  expanded summary height 152.5px, all 22 rows retained.
- Live Headout latest report: same corrected **−6.1%** cell; collapsed Levers
  header retains the **336 PP CEs** count.
- Live Headout Sep 6 dated preview: incomplete-week notice retained, Sep 6–12
  dates, through-Sep-9 cutoff and **$14.2M** goal remain visible.
- Live CSEE CE3286 Mini Audit: the first saved-discussion read failed temporarily.
  One read-only **Retry discussion** recovered it. The complete visible Mini
  Audit text then exactly matched the pre-deployment capture, including both
  notes and the existing saved summary. No note, reply or summary was generated.
- All 19 aliases were checked against dated pages in the exact artifact; live
  browser checks sampled North America, CSEE and Headout. An authenticated
  remote byte comparison of every page was not performed.
- Alert ledger hash is unchanged after deployment. Temporary mobile viewport
  overrides were reset. No backend deployment or API/runtime changes.

Verdict: approve the scoped release. The transient discussion-read failure is
recorded rather than claiming failure-free upstream services. Physical-device,
screen-reader and broad performance checks remain unverified.

Skills used: weekly-market-report-v2 for frozen-report preservation;
make-interfaces-feel-better for disclosure, keyboard and mobile checks.
