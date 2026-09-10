# Mid-week sidebar release — 10 September 2026

## Scope

User approved the remaining deployment, live Mini Audit verification, access/data
audit and reproducibility work, excluding new CSEE/Nordics aggregation. Existing
shared-page selection is preserved; no combined totals are introduced.

- Left navigation collapses from 196px to 68px on desktop. The right notes panel
  remains visible; the mistaken Hide notes/Show notes implementation is removed.
- Embedded metric headers remain within their data pane, below the toolbar.
- Empty seasonality copy: “Seasonality adjustments will be shown here.”
- No report metric refresh, new alert run, parent-alert repost, storage migration,
  OKR change or change to monthly pages.

## Frozen artifact and local gates

- Source: `.cache/weekly_report/midweek_mini_audit_resilient_release_2026-09-09`.
- Candidate: `.cache/weekly_report/sidebar_release_2026-09-10`.
- Its adjacent receipt verifies all 111 V2 pages preserve every prior payload
  value and order; unrelated files remain byte-identical. Preview notices and
  latest-week routing are retained. Apps Script stays on version 17.
- 323 tests passed in the shared checkout, including one unrelated bucket test;
  `git diff --check` passed. Unrelated bucket cleanup is excluded from this commit.
- Desktop/mobile/keyboard/state-preservation checks are detailed in
  `MINI_AUDIT_LAYOUT_FIX_2026-09-09.md`. Production checks are recorded below after
  activation, not inferred from the local mock.

## Preservation and live-test authority

Read-only baseline captures all 29 tabs in current and historical workbooks:
`.cache/weekly_report/mini_audit_followup_backend_2026-09-09/sidebar-before-*`.
The user explicitly authorized a dummy message in any CSEE CE. The test will be
clearly labelled verification-only, with no business finding or action requested.
Selected CE: 3286, Temple of Poseidon & Cape Sounion, week August 30.

## Fresh data audit

The prior statement that the completed-week Headout September goal was missing
was stale. Its published goal is $14,217,164; a fresh bounded BigQuery query of
`analytics_reporting.revenue_goals` confirms the same total across the 25 approved
September Market rows. Combined Entity rows are not added to Market rows.
The dated September 6 incomplete preview still lacks the goal sidecar.

Optional Google/Bing fields cannot safely be blanket-backfilled from today's
source without refreshing frozen parent metrics. Date-constrained source queries
captured 30,808 TY and 23,253 LY CE-week rows. Example CE3286 / August30: published
paid conversions 12, current BQ 14; published CM1 246.9136, current BQ 272.475369.
No frozen values were overwritten. Capture location:
`.cache/weekly_report/platform_source_audit_2026-09-10`.

## Production results

Pending exact deployment and live test; do not treat this document as completion.
