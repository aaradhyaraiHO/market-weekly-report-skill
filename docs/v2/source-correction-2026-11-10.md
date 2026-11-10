# Forecast authority and source-anomaly correction — 10 November 2026

The November 1–7 publication matched its frozen source but missed two semantic
errors. North America's monthly outlook used a four-week extrapolation instead
of Revenue Goals' full-month warehouse forecast (104.03% versus 96.73% on Nov 9).
Headout included an extreme negative CE/day source entry: Spanish Riding School
5266, Nov 6, predicted revenue −322,022.10 against order value 903.08. Historical
BigQuery reads reproduced that entry; current source reads show +155.54. No person
or upstream order-level cause has been established by this correction.

## Recurring release changes

`market_month_forecast` reads the complete calendar month of
`combined_entity_stats.sum_revenue_predicted`, including warehouse forecast rows,
with the existing market filter (no filter for true-global Headout). This matches
the Revenue Goals monthly actuals query. It never extrapolates weekly revenue.
The target grain/selection and report-week MTD cutoff remain unchanged. The
forecast includes later actuals/forecast dates available when retrieved, and is
frozen with source provenance. Country forecasts aggregate CE month forecasts;
missing CE forecast evidence cannot fall back to the old extrapolation. Existing
historical sidecars/rendering retain their original definitions.

`source_guard.py` runs before generation and again before staging/deployment:

- Read all markets, including markets outside the configured 17 for Headout.
- Check W0, W−1 and weekday-aligned LY daily CE economics. Block missing/non-finite
  required revenue/cost inputs and negative revenue exceeding both $1,000 and
  twice absolute daily order value. Small refunds are allowed. These are review
  gates, not financial adjustments; do not replace, clamp or silently ignore rows.
- Independently reconcile snapshot revenue, business CM1, gross marketing cost
  and ROI operands for W0/W−1/LY. Dollar tolerance is max($1, 1 ppm); rounded ROI
  tolerance is 0.011 percentage points.
- Verify attached forecasts use the full-month authority, complete day coverage,
  matching operands and fresh independent full-month source totals. Optional
  failed target enrichment stays visibly unavailable, never inferred.

A gate failure stops the release. Preserve its JSON evidence, notify the operator
and investigate the source; do not raise byte caps or alter metric/bucket rules.
The gate catches these observed failure classes; it does not guarantee that all
upstream business errors can be detected automatically.

## Approved correction procedure

Use a new package, preserving the original complete artifact, snapshots, frozen
delivery bundle, ledgers and journals. Pin business/forecast/OKR source reads to
one warehouse time-travel timestamp. Rebuild with the same formulas and original
maturity evaluation date. `evaluation_date` is an optional correction-only input;
normal builders still use their original current-date behavior. Never substitute
calendar-date LY for the approved 364-day-aligned comparison to match a screenshot.

Reconcile all corrected snapshots, parity-check reports, stage from verified
current production and require byte-identical preservation of every unrelated
page/API/Mini Audit asset. Deploy via the reviewed upload helper and freshly
verify every canonical manifest route through the signed-in browser.

Only then use `alert/v2/edit_delivery.py` with original/corrected immutable bundles,
original delivery state, exact artifact and browser proof. First dry-run it. It
preflights every exact original TS, author and content before any `chat.update`.
There is no posting or deletion API. Changed operation-slot counts fail closed.
A separate journal records preimages, targets and write-ahead state; ambiguous
updates are reconciled by fresh reads, never by replacing the original journal.
Read back every parent/RCA after edits. Old frozen delivery commands intentionally
reject corrected content; use the correction receipt for this edition's audits.
Future weeks use new packages normally. Never clear old state to make a retry pass.

After the correction's complete verified deployment receipt exists, record its
snapshot directory and hashes in `verified_snapshot_corrections.json` inside the
weekly cache. Next week's follow-up reader uses that verified version, not the
superseded cache file. The original snapshot bytes remain unchanged. Missing,
tampered, symlinked or unverified correction evidence stops the read instead of
silently falling back to known superseded facts. Ordinary weeks without a
correction keep their original reader behavior. This changes data-version
selection only; follow-up and bucket calculations are unchanged.

Live correction evidence resides under
`.cache/weekly_report/source_correction_2026-11-10/`. A staged package or passing
fixture suite alone is not proof that deployment/Slack correction completed.
