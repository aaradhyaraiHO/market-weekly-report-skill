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
