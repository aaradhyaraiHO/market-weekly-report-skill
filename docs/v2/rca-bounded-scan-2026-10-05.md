# RCA bounded-source scan — 5 October 2026

The September 27 release stopped before deployment or alerts when its base
WoW RCA query exceeded the unchanged 80 GiB per-query cap. Splitting CE IDs
still failed for `1049 - Dubai`.

Read-only investigation isolated 149.689 GiB of the 149.714 GiB estimate to
the two-week Mixpanel funnel source; revenue alone estimated 0.024 GiB.
The September 20–26 funnel window accounted for 148.936 GiB including the
revenue/metadata joins; September 27–October 3 accounted for only 0.803 GiB.
Source partition metadata showed 643,417,197 rows on September 22 and the
recent partitions last modified October 5. This identifies the expensive
source partitions, not the upstream reason for their volume. Job-history
listing was unavailable to the current identity; do not claim a proven
historical scan-size comparison.

## Recovery path

`rca_scan.bounded_dataframe` retains the existing direct SELECT. Only a
byte-cap failure invokes a fallback. It dry-runs date slices and bisects
until each fits the same cap; an over-cap single day stops explicitly.
Each slice selects DISTINCT source rows into BigQuery's automatically
created private anonymous query-result table. No permanent tables, source
writes, user-level local downloads or snapshot-archiving infrastructure
are introduced. All slices pin the same source time-travel timestamp.

The original SQL then reads their UNION ALL in place of the source table.
Weekly COUNT(DISTINCT user_id), channel splits, conversion windows, joins,
null handling and all downstream formulas are unchanged. Daily distinct
counts are never added. Anonymous results are used immediately within the
same invocation; they are not durable resume state. A missing/expired
result, unavailable source, permission failure or other query error stops.

## Verification before release resumption

- Real failed Dubai CE succeeded using five disjoint source slices; the
  largest processed 65,454,178,347 bytes (60.96 GiB), below 80 GiB.
- Original versus bounded source path, September 6 week, CEs `1049 - Dubai`,
  `1172`, `2174`: all 56 output columns matched for all three rows, including
  null context columns. Floating sums used rtol 1e-12 / atol 1e-10.
- Both existing SQL files remain byte-identical to `bb83301`.
- Unit tests cover unchanged direct queries, permission failures, disjoint
  slices, pinned source time, unchanged caps, repeated users across days
  and channels, and explicit single-day failure.

Evidence: `.cache/weekly_report/v2_package_2026-09-27/rca_scan_parity.json`.
This verifies the scan path, not deployment or Slack completion. Those
remain subject to the standard preservation, browser and read-back gates.
