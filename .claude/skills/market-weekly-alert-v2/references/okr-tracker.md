# OKR tracker routing

Source: [OKR Tracker](https://docs.google.com/spreadsheets/d/1vRgfr9jnefP7grYKa-zaSkUzCpT7pnah7UCkaZuz5Dg), tab `H2 2026`, header row 10.

Columns are Team, Objective, KR, DRI, Baseline, Q3 Milestone, Q4 Milestone, Q3/Q4 status, tracking link, and comments.

## Regional mapping

- Europe Business: Italy, France, UK & Benelux, CSEE, Iberia
- APAC Business: Oceania, East Asia, South East Asia
- MENA Business: UAE and MENA expansion markets
- America Business: North America and Americas expansion markets
- Company: Headout roll-up

The exact machine-readable mapping lives in `alert/v2/okr_queries.json`.

## Finalized KRs and engine

Generate all four rows with `alert/v2/build_market_okr_results.py`:

1. `Grow cumulative Pro+ CEs`: count CEs with trailing-92-day predicted revenue of at least $10K as of the report week.
2. `Launch new Pro+ CEs — Mature`: current-quarter Mature CEs already at $10K QTD or projected to $10K using QTD plus the trailing-28-day/L4W daily rate over exact remaining quarter days, gated by maximum prior-four-quarter revenue below $10K.
3. `Launch new Pro+ CEs — Emerging & Growth`: the same achieved-or-L4W-projected and prior-four-quarter-new gate, split to current Emerging/Growth CEs.
4. `Grow non-POI GEL revenue YoY`: exact-calendar-QTD predicted revenue for non-Mature, non-POI, Managed/Managed Lite CEs versus the same month/day dates one year earlier.

Treat `scripts/band_dashboards/generate_dashboards.py` as the authority and mirror its query helpers and `MARKET_ALIASES` normalization. The source is `combined_entity_stats`; join current CE dimensions with the central engine's dimension-first/latest-stats market fallback. Keep the output at one row per approved business market plus Headout.

Do not source market values from `analytics_reporting.weekly_kr_metrics`: it is company-level and retains older metric definitions. Do not compare company KR targets with individual market actuals unless an approved market allocation is added later.
