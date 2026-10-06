# CE summary week-boundary repair — October 6, 2026

## Confirmed incident

Chicago CE `18 - Chicago` intentionally reuses Slack parent `1789466637.943559`
in `C0BQHT29WMB`. Its September 27 commentary nevertheless used that September 6
starter and four September 15 replies in a summary generated October 5 and
approved by Pari. September 22's negative-seasonality relay `1790052745.943929`
and human follow-up `1790053417.758089` exist in Slack. The relay is stored under
the September 13 reporting week.

This is incorrect week/source selection, not acceptable current-week carry-forward.
Findings/actions may be stale; this does not establish a financial metric or
bucket-calculation error.

## Source repair

- Resolve the reporting cycle separately from the durable CE discussion. Never
  give a new week the original parent by default.
- Refuse a later row duplicating an earlier starter. It cannot truncate the
  legitimate earlier cycle.
- Recover older same-week moved boundaries using exact owned sources without
  rewriting those records. Require matching channel, discussion, week and bounds.
- Stop when a scanned human source is already stored under another week. Do not
  steal sources, backfill records or silently omit the ownership conflict.
- Do not call the model for an incomplete paginated scan. Preserve collected
  sources/cursor for continuation and retain the existing approved summary.
- Reject approval for an unverified cycle, incomplete scan or missing/out-of-week
  citations.

No schema, metric, bucket, BQ, report-HTML, role-note or schedule changes.

## Offline verification

The regression uses the Chicago parent, four September 15 human replies,
September 22 relayed recommendation and September 22 human follow-up. It checks:

1. September 6 receives only the four older replies.
2. September 13 receives the negative-seasonality relay and human follow-up.
3. September 27/October 4 cannot invent a starter from the old parent.
4. Existing approved content and unrelated weekly rows stay byte-identical.
5. Wrong-week approval and cross-week source ownership stop without edits.

Existing historical-binding, duplicate-source, outage, thread-switch and
partial-page regressions also pass. Local tests are not a live backend pass.

## Live gate and human review

Apps Script is separate from repository push and Vercel report deployment.
Identify the actual deployed project/version, retain its exact rollback source
and deployment ID, and compare the patch to that source before rollout. Never
overwrite an unmatched backend.

Pari's September 27 approval and mis-owned source rows remain untouched and
require explicit human review. Do not regenerate their summaries as a test.
Review that summary against Slack before using its recommendations as current
evidence. This document flags the incident; no live warning/rejection/replacement,
Slack notification or Sheet write has been applied.

New-summary persistence/approval needs a separately approved test discussion and
period. Read-only checks do not prove that write workflow. Next real weekly/monthly
runs must measure storage savings while passing their preservation/live gates;
do not rerun an already-delivered week to manufacture those measurements.

## Verified backend rollout

The signed-in Apps Script UI and authenticated API identified `WBR Review Backend`
project `1PcyDdbEK8zpSm_L8lhopGOIJlode56Y1bMBSiABcQ0GoBqcIpcKRRsP6` and the
existing Review deployment ending `SPppxfSoqAX-o3aQy`. Its frozen version 21
matched the repository's exact pre-fix source (`acf385524eee…`).

On October 6, the shared writer lock protected a scoped rollout of commit
`8eff0c7` as immutable version **22**, source SHA-256
`335e1b4ad9ce81563a5c2809ad8160d54b3c2c31ec244aec993e274d6ab615f4`.
The endpoint, execution/access configuration, manifest and unrelated deployments
were preserved. The distinct editable project HEAD was restored exactly.
Version 21 and its exact deployment configuration remain the rollback point.

The update response confirmed version 22 while the immediate GET returned stale
version 21. A later read-only reconciliation confirmed the exact intended version
and source; the deployment update was **not replayed**. All populated values in
the 16-tab Review workbook matched before/after, including approved summaries,
notes, actions, access rows and thread mappings. No Sheet or Slack write was sent
by this rollout. Production report HTML and its Vercel deployment were untouched.

Private receipts and source backups are in
`.cache/weekly_report/ce_summary_boundary_backend_2026-10-06/`; the
`activation-receipt.json` records the single update and read-only reconciliation.
The 445-test suite verifies the repaired source's week-selection, incomplete-scan,
source-ownership and approval guards. This rollout verification does not replace
a separately authorized fresh-summary write/persistence test.
