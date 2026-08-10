# RPC/CM1 (fluctuations · seasonality) bucket — start here

Worktree `worktree-rpc-cm1-bucket` off `main` @ 486dd66. **Publish/alert/sheet-writes only from main.**

## Current rule (simplified 2026-08-03, refined 2026-08-04)

CM1/conv and RPC fire on ONE comparison — no daily engine, no 3-day alert:

- **Window**: the FULL report week, Sun→Sat (`config.WEEK_START_DAY`)
- **Comparison**: pooled ratio over the prior **21 days** (L3W) = `[w0_start−21, w0_start−1]`
- **Threshold**: **±35%** (`config.FLUCTUATION_THRESHOLD`)
- **Volume floors** (both legs): W0 ≥ `MIN_ORDERS_WK` pro-rated to the window; baseline ≥ the
  same floor scaled to 21d (=30). Conversions for CM1/conv, orders for RPC.
- **ROI gate** (`buckets.FX_DOWN_ROI_MAX/FX_UP_ROI_MIN`, on the W0 Google ROI in the ROI cell):
  down hidden if ROI > 180 · up hidden if ROI ≤ 100 or unknown
- Ratio is Σvalue/Σdenom on both sides (pooled, not a mean of dailies)

Removed: the daily POF engine (28d baseline, ≥20% dev, SDLW ±25%, 7d-rolling WoW, CV ≤0.50,
min-conv/day, min-clicks/35d), the **3-day persistence alert**, `cv_excluded`, `config.POF`,
and the **maturity trim** (see below).

### Why the maturity trim went away (2026-08-04)
`mat_cutoff = min(week_end, today − MATURITY_DAYS)` used to cut W0 to the settled part (6d on a
Monday run). Measured on NA + Italy: the freshest day shows **no** attribution deficit vs the
same weekday a week earlier (NA ROI +8.7%), and excluding Saturday moved pooled RPC / CM1-per-conv
by **<1%** — far inside a 35% trigger — while discarding ~15% of W0 volume and making the window
depend on the run day (Mon→6d, Tue→7d). A full week is also exactly 3 baseline weeks, so W0 and
the L3W baseline share an identical weekday mix. `MATURITY_DAYS` is still used by
`latest_matured_week` elsewhere; `fluctuation_partial` is retained (always False) for back-compat.

## Where it lives
- **`scripts/weekly_report/alerts.py`** — `_weekly_ratio_alert` (the whole CM1/RPC qualifier),
  `_driver_windows` (emits only the `l3w` driver window now), `build_bucket1` (orchestrator →
  `bucket1_fluctuations`; `week_days` param is gone). `cvr_drops` / `cvr_gray_zone` /
  `wow_driver_alerts` still run and are still **WoW-based** — see Open question below.
- **`scripts/weekly_report/buckets.py`** — `seasonality()` reshapes rows into the ↓/↑ display
  (RPC → CVR·AOV·Completion·Take-rate; `verdict`; `recommendation`). Now also emits **`weeks`**
  = raw W0..W3 blocks (spend · ROI · clicks · CVR · CM1/conv · CPC, newest first) for the
  expanded Losing-Money-style table. `alert_type` is `L3W` or `WoW`. Constants
  `FX_RED_FLOOR / FX_SINGLE_MIN / FX_CVR_MIN / FX_COLLECTIVE_MIN`, `SEAS_UP/SEAS_DN`.
- **`scripts/weekly_report/config.py`** — `FLUCTUATION_THRESHOLD`, `FLUCTUATION_L3W_DAYS`,
  `CVR_WOW_DROP_THRESHOLD`, `MIN_ORDERS_WK`, `SEASONALITY_ADJ_PCT`.
- **`scripts/weekly_report/build_snapshot.py`** — maturity window (`flux_w0_start`, `mat_cutoff`,
  `fluctuation_context_week`); `meta.fluctuation_compare_*` now spans the L3W window.
- **`template/report_template.html`** — `FX_METRICS` (the 6 expanded weekly columns), `fxSwing`,
  `fxDriverCell`, `fxAction` (GM checkbox + note), `fluxHead`/`fluxRows` (reuse
  `lmMetricHeads`/`lmMetricCells` so Flux and Losing Money share one cell renderer),
  `seasDnBody`/`seasUpBody`, `_bucketBlock('…Fluctuations ↓/↑')`. Perf reviews live in the
  Weekly Flagged Sheet, not the report — the report cell stays GM-only.

## Build / preview
`python3 scripts/weekly_report/build_snapshot.py --market italy` → snapshot in `.cache`;
`python3 scripts/weekly_report/render.py <snapshot.json> --out /tmp/r.html`.

Note: `make_sample_data.py` fixtures carry no `ad_conversions`/`cpc`, so CVR / CM1-conv / CPC
render as `—` in a sample-data preview. Real snapshots emit `conversions_g`/`cpc_g` and populate.

## Open / not done
- **Mixed comparison bases.** `cvr_drops` (30% WoW) and `wow_driver_alerts` (collective-driver
  WoW) still feed this bucket on a **WoW** basis, so the table mixes `L3W` and `WoW` rows under a
  heading that advertises ≥35% vs L3W. Each row is now at least *internally* coherent (its driver
  deltas and Step-3 gate use its own window), but the mix is still there — and with the Signal
  column removed there is **no visual indicator of which basis a row used**. Decide: move those
  paths to L3W/35%, or re-add a basis chip.
- **`VALIDATION_NA` is stale.** Its `cm1_conv_alerts` list was calibrated to the old daily POF
  engine; `--validate` will MISMATCH until re-baselined. Its `week_start` (2026-06-29) is also a
  Monday, invalid under `WEEK_START_DAY = SUNDAY`.
- **Volume floor magnitude.** Now 10/wk on W0 + 30 over the baseline. A 3-window backtest on
  NA + Italy found rows under ~20 orders flip sign 57–67% of the time (vs a ~45% coin-flip base
  rate), so a higher floor (~40–50) is probably right — not yet applied.
- **Predictive power.** That same backtest found the swing % has **no** week-ahead predictive
  power at CE grain (confirmation ≈ base rate; a $-impact gate did not beat it either). The
  W0..W-3 columns are what let a reviewer separate trend from jitter — the swing number alone
  does not, which is part of why it is no longer displayed.
- **↓ overlaps Losing Money** — every NA ↓ row is also a Losing Money row (Italy ~⅓). Consider
  deduping or folding ↓ into LM as a driver view.
- **ROI gate barely bites** on the corrected W0 anchor (NA 0/9, Italy 1/21 at the time of
  measuring): a ≥35% drop mechanically pulls current-week ROI down, so "dropped hard but still
  >180%" is nearly an empty set. Kept as a cheap safety rail.
