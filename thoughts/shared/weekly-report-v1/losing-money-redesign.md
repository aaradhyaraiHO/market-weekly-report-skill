# Losing Money — redesign (schema + format)

Draft only. Mockup: `losing-money-mockup.html` (open in browser).
Modelled on Pranathi/Aditya's two working sheets:
- **"4 wks rolling avg"** (`1lmJ5B…`, tab gid=1282623121) — the CM2-avg + flag + driver logic
- **"Final Loosing money"** (`1sXd0m…`, tab gid=1066981225) — the raw week-by-week review layout

## The problem this fixes
Current `losing_money()` (`scripts/weekly_report/buckets.py`) carries **6 sub-lists**
(bleeders/eroding/full_waste/paused/tracking_gap/recovered) and, per row, a stack of
derived fields — `cm2_prior4avg`, `cm2_decline`, `cm2_improve_pct`, `recovering`,
`roi_dpp`, `roi_v4`, `status` strings ("NEW"/"CHRONIC"/"ESCALATING"). The reviewer must
**decode severity** instead of **seeing the trend**. Their sheets prove L1 review only needs
raw weekly numbers + a plain 4-wk average + one flag + one driver.

## Two tables (replaces the 6 sub-lists) — split by lifecycle
Per Aaradhya (this session): the top-level split is **Existing vs New CEs**, each sorted by
**|negative CM2 Δ vs 4-wk avg|** (biggest drop first).

| Table | Membership | Why |
|---|---|---|
| **Existing CEs** | `new_existing == "Existing"` | the real Defend problem — established CEs shedding CM2 |
| **New CEs** | `new_existing == "New"` | losing money often *intentional* while scaling at low ROI (transition CEs); full-waste is the exception |

The must-action vs flag-only idea (Jul-29) is demoted to an **inline `hold` tag** on high-ROI rows
(`roi_wk ≥ 120%`), not a separate section — so it's visible without fragmenting the table.

Footnote lines (NOT counted as bleed): **Paused**, **Tracking gap**, **Long-tail burn** — verify-only.

## Collapsible weeks (matches the All-CE view)
CM2 renders as ONE collapsible metric column, identical UX to `METRIC_COLS`:
- **Collapsed:** `CM2 this week` + `(WoW Δ%)` beneath.
- **Expanded ("Show weekly"):** `W-4 · W-3 · W-2 · W-1 · W0` raw columns — read the trend across.

The 4-wk average is **never displayed as a column** — it is only the quiet **sort key + flag driver**.
This is the fix for the "W1-W4 vs W5" confusion: the reader sees weeks, not an abstraction.

## How the two sheets are actually built (verified from formulas)
**Sheet 1 "ROI weekly cadence"** = SUMIFS pivot over two raw sources we already query:
- `Ads stats` — Omni export of `ads_campaign_stats` (weekly): CM1, cost, conversions, clicks,
  impressions, eligible-searches, **SIS Budget Lost, SIS Rank Lost**, week key.
- `CE Entity` — BQ Connected Sheet on `combined_entity_stats` + `dim_combined_entities`:
  orders, GBV, completed GBV, revenue, ad_spend, coupon, wallet, CM1, evolution_bucket, category.
- `4 wks rolling avg` = per metric×week cell `SUMIFS(col, ce, $A, week_col, week_hdr)`, then one
  uniform pattern: `W1-W4 = AVERAGE(first 4 wks)`, `W5 = latest matured wk`, pooled rolling ratios
  (`Σnum/Σden`), Flag off CM2-$ change, Neg driver = argmin of 4 clicks-anchored contributions,
  Marginal ROI = `ΔCM1/ΔSpend`, plus SIS / Rank Lost / Budget Lost.

**Sheet 2 "Weekly Flagged CEs"** = a MANUAL execution worksheet (verified via FORMULA render):
- Pipeline: our `export_flagged` CSV → `Losing Money` tab (spine) · our notes export → `from report`
  (GM comments) · Omni/BQ raw weekly pull → `All -ve CM2` (PASTED values) → `Sheet2` → `Final Loosing money`.
- `Final Loosing money` cols: A–D identity + E–AJ = **4 weekly blocks × 8 metrics (Cost/Clicks/CPC/
  Conversion/CVR/CM1/ROI/CM2), all PASTED values** + `AK new_existing`/`AL tier` = VLOOKUP into our
  `Losing Money` export + `AM` = `AND(W0 CM2<0, W-1 CM2<0)` (2-wk persistence) + `AO ROI Change=K/S−1`
  (WoW) + `AP Clicks WoW=F/N−1` (self-correcting filter) + `AQ–AT` hand-typed perf-action log
  (Actions Took / Perf Comments ×2 / Final Actions) + `AU GM Comments` = VLOOKUP our notes export.
- **KEY: the execution sheet uses WoW + 2-wk-persistence, NOT the 4-wk avg** (that's Sheet 1, analytical).
  They paste the raw weeks because our export omits them; hand-type the entire perf-action layer.

## Learnings to build in (most already in the snapshot)
1. Baseline = plain `AVERAGE(prior 4 wks)`, W5 = latest matured week (already have `cm2_series`).
2. **Emit the raw weekly CM2 series in the export** — snapshot carries `cm2_series[-12:]`, export drops it.
   Highest-leverage fix: kills their manual rebuild.
3. Pooled rolling ratios (ROI/CVR/CPC/CM-per-conv = Σ/Σ), not average-of-ratios.
4. Flag off CM2-$ change (−2k/−1k) + Marginal ROI (`ΔCM1/ΔSpend`).
5. Neg driver = argmin of 4 clicks-anchored contributions — already computed (`dominant_driver`).
6. **★ Add SIS / Rank Lost / Budget Lost** — the headroom signal (Jul-23 rule: check abs top-of-page IS
   before cutting ROAS; rank-lost = room via bid, budget-lost = room via budget). We fetch `paid_sis_pct`
   (Google) but NOT rank/budget lost, and surface none of it in Losing Money. Tells you if an action helps.
7. Persistence flag = `CM2<0 in W0 AND W-1` (their "−ve past 2 weeks").
8. Value anchor = CM/conversion (not AOV+TR split) → 4 factors reconcile to CM2 exactly; AOV/TR = fallback label.

## Core logic (all trivial — matches the sheets)
```
cm2_4w_avg   = AVERAGE(prior 4 weeks)         # this week EXCLUDED  (was cm2_prior4avg)
cm2_wk       = this matured week's CM2
cm2_delta    = cm2_wk - cm2_4w_avg            # $  (replaces cm2_decline)
cm2_delta_pct= cm2_delta / cm2_4w_avg
flag         = 🔴 if cm2_delta <= -2000 · 🟠 if <= -1000 · 🟢 else   (🟢 not surfaced)
neg_driver   = argmin(Clicks, CVR, CPC, CM-per-conv contribution)   # already computed as cm2_drivers/dominant_driver
marginal_roi = (cm1_wk - cm1_4w_avg) / (spend_wk - spend_4w_avg)    # NEW column
roi_4w       = ΣCM1 / ΣSpend over the window  # pooled, not avg-of-ratios
wks_neg      = consecutive weeks CM2 < 0
```
Thresholds (−$1k / −$2k, ROI 100%) copied from the sheet — expose as constants, tune later.

## Row schema (flattened — one list, `group` field)
```jsonc
{
  "ce_id": "189", "ce_name": "Vatican Museums",
  "market": "Italy", "category": "Museums", "tier": "Hero",
  "group": "action" | "flag_only",
  "flag": "critical" | "monitor" | "safe",
  "cm2_series": [17214, 17569, 11537, 11458, 5663],  // last 5 wks, oldest→newest (sparkline + printed)
  "cm2_weeks":  ["2026-06-20", ... "2026-07-18"],
  "cm2_4w_avg": 15422,
  "cm2_wk": 11458,
  "cm2_delta": -3964, "cm2_delta_pct": -26,
  "neg_driver": "cvr",              // clicks | cvr | cpc | aov_tr | full_waste
  "roi_wk": 126, "roi_4w": 130,
  "marginal_roi": 149,
  "spend_wk": 44100,
  "wks_neg": 0
}
```
Footnote payload stays as counts + name lists (`paused`, `tracking_gap`, `burn_line`).

## Columns shown (12, matches sheet width)
CE · Flag · CM2 trend (5-wk sparkline + printed values) · CM2 4-wk avg · CM2 this wk ·
Δ vs avg ($ + %) · Neg driver · ROI wk · Marginal ROI · Spend wk · Wks −ve · Action.

## What we keep from the current engine (no recompute needed)
- The 4-factor CM2 decomposition (`cm2_drivers`, `dominant_driver`) → becomes `neg_driver` (one word).
- full-waste guard (CM1>0 composite exclusion), paused/tracking-gap classification, burn_line.
- Google-Search paid basis + matured-week windowing.

## Dropped
`cm2_improve_pct`, `recovering`, `recovered` list, `status` strings, `roi_dpp`, `roi_v4`,
the `eroding` vs `bleeders` split as separate lists (now one `group` field).

## Resolved this session
- Top split = **Existing / New CEs** (not Action/Flag-only). ✓
- Sort = **|negative CM2 Δ vs 4-wk avg|**, biggest drop first. ✓
- Show **raw weeks collapsible** (All-CE pattern), avg is an invisible sort/flag key. ✓
- must-action/flag-only → inline **`hold`** tag on `roi ≥ 120%`. ✓

## Open questions for Aaradhya
1. Sort key Δ basis: **vs 4-wk avg** (current mockup — catches the Vatican step-down) or plain **WoW**?
2. `hold` threshold = **ROI ≥ 120%**? (Jul-29 examples: USJ 135-169, Naples 170.)
3. Should the **New CEs** table only show full-waste + genuinely-negative (hide intentional low-ROI scale-ups), or show all and let the `hold`/tag carry it?
4. Keep the three collapsible metrics to just **CM2**, or also make **ROI / Spend** collapsible like All-CE?
