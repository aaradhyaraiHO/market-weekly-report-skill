# Historical Mini Audit summary binding repair — 9 September 2026

Status: implemented and verified locally; **not deployed**. The coordinating
“Check report readiness” task owns integration, backend deployment and live
summary validation. This repair performed no live Sheet writes, Slack sends,
business-data creation, deployment, commit or push.

## Failure and repair

An August 30 weekly record can have a saved Slack parent but no binding ID.
When the same thread is reused in September 6, its latest weekly starter changes.
The old recovery compared against that mutable starter first, rejected the
otherwise matching immutable parent, and returned “CE thread changed”. Its
source filter also excluded already-scanned legacy replies without binding IDs
whenever a CE had more than one thread.

`reviewResolveWeeklyThread` now prioritizes the explicit weekly binding. For
missing IDs it requires unique saved parent/starter/permalink evidence within
the CE's thread registry, including channel agreement where a Slack permalink is
present. Contradictory or ambiguous historical evidence fails closed. Explicit
request/weekly conflicts remain rejected. No historical week falls back to the
active thread just because it is active.

The normal locked weekly mutation may fill a previously blank binding ID or
discussion number after that proof. It compares the saved binding and starter
again under the lock, preserves existing nonblank identities, source links and
scan cursor, and does not rewrite the thread registry. There is no bulk migration.

Legacy source rows are matched in memory using their exact Slack channel,
parent permalink and message reference. An already-scanned source is eligible
within its original weekly cycle, rather than only after the scan cursor. The
next cycle remains an exclusive upper bound, even if that later weekly record
also needs read-only legacy binding resolution. Sources themselves are unchanged.
Existing stale-result and summary-approval guards remain in force.

The frontend sends a pinned week's explicit binding for summarization. If its
binding is missing, it leaves resolution to the backend instead of sending the
current active binding. The writeup's Continue / Start new thread behavior is
unchanged. Historical summary numbering is separate from active-thread numbering.

## Exact files in this repair

- `scripts/weekly_report/notes/review_apps_script.js`
- `scripts/weekly_report/review/review-view.js`
- `tests/weekly_report/js/mini_audit_runtime.cjs`
- This repair note.

Earlier Mini Audit changes in these files and unrelated shared-checkout work
are retained. Overview/template/platform/publishing files were not edited by
this repair.

## Local verification

- `node tests/weekly_report/js/mini_audit_runtime.cjs`: passed.
- `python3 scripts/weekly_report/verify_baseline.py`: 312 tests passed.
- Summary binding contract tests: 3 passed.
- Both changed production JavaScript files pass `node --check`.
- `git diff --check`: passed.

The new runtime cases cover two threads, an August 30 missing binding, an
advanced September 6 starter, an already-scanned approved human reply without
a binding, exact source preservation, successful summary approval, repeat and
regenerate deduplication, later-cycle exclusion, a legacy later-cycle boundary,
wrong/missing source provenance, conflicting channel/parent evidence, ambiguous
registry matches, an older replaced binding, concurrent binding changes before
recovery and during AI, plain reply permalinks with explicit bindings, and the
actual frontend summary request selecting the pinned binding.

## Remaining coordinated live validation

1. Build/freeze the approved integrated report and API artifact with this backend
   version; do not substitute the old production artifact for the newer Overview.
2. On the pinned August 30 CE2567 report, summarize the existing Asfan reply in
   `C0BQHT29WMB / 1788876228.790149`. Verify fresh summary creation and memory
   persistence from the real source, without posting another human/test reply.
3. Verify the September 6 cycle does not inherit that August 30 reply; repeat the
   August 30 summary and confirm no duplicate work or source rows. Confirm original
   thread associations, weekly starters, source text and scan cursors are retained.
4. Verify an older explicitly bound replaced discussion and the approved complete
   report release checks before declaring the integrated rollout live.

The incomplete-week latest-link correction remains owned by the coordinating
task. This local repair does not claim that production's summary failure is fixed
until the exact deployed workflow passes those checks.
