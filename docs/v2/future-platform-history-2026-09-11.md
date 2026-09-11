# Future Google/Bing comparison evidence

Scope: query/snapshot retention for future generation only. No live backfill,
report rewrite, snapshot archive, scheduler change, deployment or Slack send.

## Source and periods

Both market and Headout builders call `fetch.ce_weekly_ads` for TY and LY.
The SQL already selects the needed fields from Google Ads + Microsoft Ads
**Search**, grouped by stable CE ID and Sunday-start week. Markets use the
existing business-market filter; Headout does not apply that filter.
The twelve TY report weeks and weekday-aligned LY weeks retain the existing
364-day alignment. Existing extra LY look-ahead used elsewhere is unchanged.
No metric SQL, date range, CM1 migration cutoff or bucket rule was changed.

## Stored optional evidence

Each populated paid CE-week retains `paid_platforms.google` and
`paid_platforms.bing`, including historical `weekly_ly` rows. Manual market
and Headout totals now retain the same optional evidence in both series.
The platform operands are spend, coupon/wallet, CM1, clicks, conversions,
impressions and attributed revenue. Google also retains SIS operands.

- Bing additive facts = combined Search facts minus Google Search facts.
- Paid ROI = CM1 / (spend + coupon/wallet) × 100, with unchanged validity gates.
- Paid CVR = ad conversions / clicks × 100; CTR = clicks / impressions × 100.
- CPC = spend / clicks; RPC = attributed revenue / clicks.
- Paid CM2 = attributed revenue − spend; average CM1 = CM1 / conversions.
- SIS = Google impressions / eligible searches × 100; Bing SIS is unavailable.

Ratios are computed from platform operands, not averaged from CE ratios.
Legacy parent fields and their calculations remain unchanged. Missing source
values are not coerced to zero for the optional platform evidence. If one
constituent of an aggregate is missing, its platform aggregate remains null
instead of presenting a partial sum as complete.

Missing columns/null counts are logged by the query adapter. Snapshot rows
also carry `paid_platform_missing_fields` when appropriate; an empty aggregate
source is explicitly marked `paid_platform_source_status: no_rows`.
Actual zero activity remains zero; undefined ratios remain null.

## Verification

- All 17 configured markets and Headout: query-contract tests cover TY/LY
  fields, market/global filters, Search scope and date parameters.
- Twelve-week TY/LY source-to-drawer projection verified.
- Formula, NumPy numeric-type, missing-field, partial-sum and zero-activity tests.
- Existing weekly metric outputs compared with release `fdf874c`: identical
  after excluding optional platform evidence/coverage metadata.
- Metric SQL and parameters compared with release `fdf874c`: unchanged.
- Full weekly/V1 regression suite: 365 tests passed; whitespace checks pass.

These are local code/contract tests with mocked query results, not a new full
warehouse run. They do not establish that every future source value exists;
the next real queries will flag any missing data. Existing historic reports
remain unchanged. The weekly-market-report-v2 skill kept the change confined
to additive evidence rather than metric or bucket reclassification.
