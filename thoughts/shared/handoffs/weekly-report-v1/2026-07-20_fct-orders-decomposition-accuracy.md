# Handoff — Fluctuations: fct_orders 4-driver decomposition + data accuracy

**Date:** 2026-07-20 · **Worktree:** `.claude/worktrees/diagnostic` · **Commit:** `73b6f63`
**For:** Slack sign-off (Aadi / Pranathi) before deploy.

## TL;DR
The CM1/RPC Fluctuations bucket now decomposes **paid Google-Search RPC into CVR × AOV × Completion ×
Take-rate**, all **order-grounded from `fct_orders`**, and applies a **multi-metric gate** that caps the
list to the real opportunities (NA: 15 → 7 down-swings). Completion is back as a real, sane metric.
Data accuracy validated (below). One known gap flagged.

## Data source & aggregation (accuracy-critical)
Google-Search paid order funnel from **`fct_orders`**:
```
ad_network = 'Google: Search'  AND  valid_to_timestamp IS NULL   -- current SCD2 version only
COUNT(DISTINCT order_id) AS orders · SUM(order_value_usd) booked ·
SUM(order_value_completed_usd) completed · SUM(amount_revenue_usd) revenue     (by CE, DATE(created_at))
```
- **No SCD2 duplication in-window:** `rows == distinct_orders` (6,926 = 6,926); all current rows are
  `valid_to IS NULL`. `COUNT(DISTINCT order_id)` is exact.
- Clicks come from the **ads table** (Google-Search paid); everything else from `fct_orders`.
- Drivers: `CVR = orders/clicks · AOV = booked/orders · CR = completed/booked · TR = revenue/completed`.
  Pooled Σ/Σ over each window → `RPC = CVR×AOV×CR×TR` reconciles exactly (both WoW and 3-day windows).

## Accuracy validation (NA, week 2026-07-06)
| Check | Result |
|---|---|
| Drivers sane + reconcile to paid RPC | **12/12** sampled CEs (CVR 0.8–5.7% · AOV $109–680 · CR 84–100% · TR 10–32%) |
| Completion rate (was 110% nonsense on ads) | **~92%** — sane |
| Cross-source: fct booked vs ads offline-gross-bookings (aligned 4wk) | **ratio 1.05** (5% higher) |
| Cross-source: fct net-rev vs ads offline-revenue | **ratio 1.02** (2% higher) |
| Blended CVR = fct orders ÷ ads clicks | **3.5%** — sane |

The ~2–5% fct-vs-ads gap is expected (session/last-click attribution vs Google conversion attribution).
Two independent sources corroborating within 5% is the key accuracy signal.

## Step-3 multi-metric qualification (the exact logic to sign off)
Per **down-swing** CE, on the paid fct drivers:
- A driver is **red** if its adverse move ≥ **15%** (`FX_RED_FLOOR`). **CVR uses its WoW move only**;
  AOV/CR/TR use the alert window (WoW or 3-day).
- **Exactly one red** → keep only if that driver ≥ **25%** (`FX_SINGLE_MIN`); **CVR ≥ 30%** (`FX_CVR_MIN`, WoW).
- **≥ 2 red** → keep only if the **compounded paid-RPC drop ≥ 20%** (`FX_COLLECTIVE_MIN`).
- **CM1/conv is exempt** (separate margin-per-conversion signal; stays).
- Result NA: **7 down-swings** (was 15). Dials are single constants — start tight, relax later.

## Known gap (needs a decision)
**Qualifiers are still ads-based; the Step-3 gate + decomposition are fct-based.** So:
- The gate correctly **drops ads-flagged CEs the order-grounded fct data doesn't confirm** (e.g. New
  England — ads-CVR −42% was attribution noise; fct orders-CVR minor). *Intended.*
- BUT the ads qualifier can also **miss** a real fct-driver opportunity that never becomes a candidate
  (false negative). **Full fix = move the RPC + CVR qualifiers onto `fct_orders` too** (unify the engine
  on the order funnel). Recommended next step.

Other caveats: `fct_orders` windows on `DATE(created_at)` (order-creation), which can drift a few orders
vs the ads/CE_STATS `report_date` windows. Heavier/slower build (order-grain scan).

## Open TODOs
- [ ] **Slack sign-off** on the Step-3 logic + thresholds (this doc).
- [ ] **Cross-market live rebuild** — IT + OC are stale (built before the fct/Step-3 changes); only NA is current.
- [ ] **Unify qualifiers onto fct_orders** (close the false-negative gap above).
- [ ] **CM1/conv → Google-only?** (last Google+Bing signal).
- [ ] Re-baseline / retire `validate_na` (CM1/conv reference shifted).
- [ ] Merge `worktree-diagnostic` → `main`.

See `fluctuations-tuning-log.md` for the per-step flag lists (Steps 1–3).
