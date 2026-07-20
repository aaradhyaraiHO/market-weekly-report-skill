# Handoff — Fluctuations redesign + Losing Money (Jul-17→20 meetings)

**Date:** 2026-07-20 · **Worktree:** `.claude/worktrees/diagnostic` · **Branch:** `worktree-diagnostic`
(ahead 7 / behind 7 of `main` — diverged, needs a merge). **Paths** relative to `scripts/weekly_report/`.

## TL;DR
Rebuilt the two DEFEND buckets to the Jul-17/19 meeting specs, live-verified on NA. **Losing Money**
is done. **Fluctuations (CM1/RPC)** is now a fully **order-grounded, paid-Google-Search** engine:
qualifiers + decomposition + gate all run off one `fct_orders` funnel; a multi-metric gate caps
output to ~5-6 real opportunities. **One open decision** (weekly "collective impact" qualifier) + the
usual ship steps (cross-market rebuild, Slack sign-off, merge).

## Commits this session (newest first)
```
b5afeb9  unify RPC + CVR qualifiers onto fct_orders funnel
bd2e83b  handoff: fct_orders decomposition data-accuracy + Step-3 logic
73b6f63  fct_orders 4-driver decomposition + multi-metric gate (Step 3)
3474281  fluctuations 3-day persistence 20%→25% (Step 2)
304b673  fluctuations → all paid Google-Search (Step 1)
0f44052  rebuild Fluctuations + Losing Money to the Jul-17 spec
```
Working tree clean. **Only NA (2026-07-06) is built on the current engine; IT/OC snapshots are stale.**

## Bucket A — Losing Money  ✅ done
New/Existing tags (metadata.new_vs_existing) · split pause guideline (New ROI<30% · Existing <70% ·
else scale-down) · Recovering tag (CM2 bleed halved vs prior-3wk, `RECOVER_CM2_IMPROVE_PCT=50`, sorted
last) · per-row Action dropdown (Pause/Scale-down/Intentional, localStorage) · **Google-Search-only
economics** (spend_g/cm1_g/roi_g via `has_g` fallback) · "Google Search only" in the cohort bar.

## Bucket B — Fluctuations (CM1/RPC)  — order-grounded, paid Google-Search
**Data source (one unified funnel):** `fetch.ce_daily_orders_google` (fct_orders, `ad_network='Google:
Search'`, `valid_to_timestamp IS NULL`, `COUNT(DISTINCT order_id)`) merged with `ce_daily_paid_google`
clicks → `d_funnel_g` (orders/booked/completed/revenue + clicks). Built in `build_snapshot`, passed to
`alerts.build_bucket1` as `ce_daily_funnel_google`.

**Qualifiers (all fct-grounded except CM1):**
- **RPC** — daily engine `_ratio_alert(funnel, "revenue","clicks","orders")`: ≥20% dev vs 28d baseline
  AND ≥25% short-term (SDLW/7d-WoW) AND ≥25% 3-day persistence (`config.POF`, persistence raised to 0.25).
- **CVR** — weekly `cvr_drops(funnel)`: orders÷clicks WoW drop >30%, ≥300 clicks/wk (WoW-only, per spec).
- **CM1/conv** — still ads (Google+Bing), separate margin-per-conversion signal (kept per meeting).

**Decomposition (display, `buckets.seasonality`):** `RPC = CVR × AOV × Completion × Take-rate`, all paid
Google-Search from the funnel, pooled Σ/Σ → reconciles exactly. WoW rows show weekly Δ; 3D rows show
3-day-vs-28-day Δ (`drivers` = {wow, 3d} attached per row in `_driver_windows`). Completion is real & sane
(~92%) — order-grounded (the ad table couldn't: completed/booked >100%).

**Step-3 multi-metric gate (down-swings; `buckets.seasonality`):**
- red driver = adverse move ≥ **15%** (`FX_RED_FLOOR`); CVR uses WoW only.
- **1 red → ≥25%** (`FX_SINGLE_MIN`; CVR ≥30% `FX_CVR_MIN`).
- **≥2 red → compounded paid-RPC drop ≥20%** (`FX_COLLECTIVE_MIN`).
- CM1/conv exempt. NA result: **6 down-swings** (from 15 pre-gate).

**Display/UX:** value-over-Δ cells, dominant driver highlighted, WoW/3D Alert chip, always-on 28d ROI +
28d Spend (Google-only, Δ vs prior 28d), Clicks context, confirm-seasonality checkbox + note, how-to
banner + per-column hover tooltips, "Google Search only" cohort bar.

## Data accuracy — validated
See `2026-07-20_fct-orders-decomposition-accuracy.md`. Key: aggregation exact (no SCD2 dup) · 12/12
sampled drivers sane + reconcile · **cross-source fct-vs-ads agree within 5% (booked) / 2% (net rev)** ·
blended CVR 3.5%. The fct-vs-ads gap is attribution-method difference (session vs Google conversion).

## OPEN DECISION — weekly "collective impact" qualifier
Unifying the qualifier to fct closed the ads-vs-fct gap AND caught a real miss (+Hawaii Luaus). BUT the
**daily RPC engine still gatekeeps candidates** (needs a 3-day-persistent daily pattern), so a **pure
weekly multi-driver collective drop** (e.g. **Kings Island**: CVR−27/AOV−21/TR−30 WoW → RPC≈−60%) is
**not a candidate** and the "collective impact" path can't rescue it. The meeting's "collective impact"
is a *weekly* concept.
- **Full fix:** driver-based WoW qualification — evaluate the single/multi rule for **every active CE**
  (single ≥25% / ≥2 red → collective WoW-RPC ≥20%), so weekly collective drops qualify directly. Keep the
  3-day engine only for intra-week breaks; keep CM1/conv. This is the fullest realization of the Jul-19 model.
- **Or:** ship the current 6-flag version and revisit after Slack sign-off.

## TODO (ship + remaining)
- [ ] **Decide the weekly collective-impact qualifier** (above).
- [ ] **Slack sign-off** on the Step-3 logic + thresholds (paste from the accuracy handoff).
- [ ] **Cross-market live rebuild** (IT + OC) — stale; only NA is current.
- [ ] **CM1/conv → Google-only?** (last Google+Bing signal).
- [ ] **Re-baseline / retire `validate_na`** (CVR/CM1 reference shifted; gate currently false-fails).
- [ ] **Merge `worktree-diagnostic` → `main`** (diverged 7/7).
- [ ] Tunable dials if 6 is still too many: `FX_SINGLE_MIN`, `FX_COLLECTIVE_MIN`, `POF` thresholds.

## Reproduce / verify
```
cd scripts/weekly_report
python3 weekly_market_report.py north_america --no-open      # live build + render (needs BQ auth)
# headless check: Chrome --headless=new --dump-dom <report_north_america_2026-07-06.html>
```
Per-step flag lists: `fluctuations-tuning-log.md`. Config dials: `config.POF` (detection), `buckets.py`
top (`FX_*`, `RECOVER_CM2_IMPROVE_PCT`, `SEAS_*`).

## Key files touched
`fetch.py` (ce_daily_paid_google, ce_daily_orders_google) · `build_snapshot.py` (funnel merge, spend_g)
· `alerts.py` (_driver_windows, cvr_drops, RPC src, build_bucket1 sig) · `buckets.py` (losing_money,
seasonality + Step-3 gate) · `template/report_template.html` (renderBleeders, flux table, tooltips).
