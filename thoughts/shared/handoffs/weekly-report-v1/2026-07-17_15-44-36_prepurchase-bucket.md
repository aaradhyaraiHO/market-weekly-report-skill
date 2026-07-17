# Handoff — Prepurchase (PP) bucket, §6(c) of the weekly market report

**Date:** 2026-07-17 · **Branch:** `worktree-diagnostic` · **HEAD:** `7e53bf0`
**Status:** ✅ Built, verified (NA + Italy), committed. Local only (not pushed/merged).

## What it is
A per-CE Prepurchase tracking table rendered as **§6 Levers visibility → (c) Prepurchase**
in the weekly market report. Metrics only, **no verdict** (reviewer decides). One row per
CE with an active PP allotment in the snapshot's market.

## Data source (the important part)
**`fct_pp_tickets`** — the per-ticket "FDT" (future-dated-tickets) truth. Rich columns:
`experience_timestamp`, `expiring_at`, `is_sold`, `validity_type` (DATE_TIME | OPEN),
`loss_liability`, `booking_created_at`, `ticket_status`, `combined_entity_id`.

Dead-ends ruled out (don't waste time here again):
- `dim_pp_allotments.ticket_validity_timestamp` — **~66% NULL** for DATE_TIME allotments →
  can't window on dates. (Allotment grain, not ticket grain.)
- `fct_unpublished_pp_allotments` — **empty for NA**; only *unpublished* inventory.
- Earlier a schema check showed `fct_pp_tickets` as 3 opaque columns — that was **stale/wrong**;
  the table is rich. Verify with a direct SELECT, not just INFORMATION_SCHEMA.

**Join to CE + market:** `fct_pp_tickets.combined_entity_id` → `dim_experiences`
(combined_entity_id → `business_market`) to filter NA/Italy/Oceania. (Note `market_region`
in the PP tables is region-level e.g. "Europe", NOT business_market — must go via dim_experiences.)

## Files / functions
- `scripts/weekly_report/pp.py` — `PP_SQL` (single aggregate over fct_pp_tickets),
  `pp_by_ce(week)` (cached), `pp_row(ce, ppd, week)` (joins CE funnel), `build_pp(snap)`
  (report-engine entry; returns [] on any failure — guarded).
- `scripts/weekly_report/build_snapshot.py` — attaches `snapshot["prepurchase"] = pp.build_pp(snapshot)`
  right after `buckets_final` (guarded try/except).
- `scripts/weekly_report/template/report_template.html` — `renderLevers()` §6(c) table +
  per-header hover tooltips (cursor:help title=).

## Columns / definitions (all from fct_pp_tickets unless noted)
| Column | Definition |
|---|---|
| Dated / Open | ticket count by `validity_type`: DATE_TIME (fixed date, carries liability) / OPEN (resells anytime, no expiry loss) |
| STR nxt 2wk | sold ÷ total for tickets with `experience_date` in [week, week+20d]; all-open CEs fall back to overall STR. Shade ≥95% under-bought / <60% over-bought |
| Expiring this mo | count of UNSOLD dated tickets with `expiring_at` in current calendar month (the real loss) |
| Loss-liab (dated) | Σ `loss_liability` of UNSOLD dated tickets = at-risk $ exposure (USD). Open-dated → $0 |
| Run-rate last / need·wk | last-wk sold (`booking_created_at` in [week-7, week-1]) vs needed/wk = remaining_dated ÷ weeks-to-latest-expiry. Amber = behind pace |
| Net ROI | (trailing-4wk CM1 − **realized loss**) ÷ trailing-4wk cost. **Realized loss = `expiring_loss`** ($ of dated tickets expiring UNSOLD this month), NOT the full at-risk stock (CE funnel: cm1/spend) |
| CVR (WoW) | CE paid conversion rate (orders ÷ ad clicks), W0 + WoW (from snapshot ces) |

Ranking: by dated at-risk $ (loss_liab_dated), then expiring_unsold.

## Key decisions (and the why)
1. **Liability = DATED only.** Open-dated resell later → no expiry loss. dim_pp_allotments'
   raw `loss_liability_usd` includes open (overstated ~2×); we filter to DATE_TIME.
2. **Net ROI uses REALIZED loss, not the at-risk stock.** Subtracting the full $347k stock
   from a 4-wk CM1 flow gave nonsense (Colosseum −613%). Now uses `expiring_loss` (periodic) →
   Colosseum 133%. Loss-liab column keeps the full exposure; Net ROI keeps the realized haircut.
3. **No verdict** column (per Aaradhya — auto extend/kill isn't scientific). STR shading is the
   only nudge.
4. Dropped `last-upload` and `PP-%-of-orders` columns (per 2026-07-17 checklist).

## Verified
- **Italy** (has dated PP): Colosseum $347k liab / 1,245 expiring July / STR 97% / run-rate
  1,836 vs 1,055 needed / Net ROI 133%; Accademia, Vatican populate similarly.
- **NA**: all PP is **open-dated** → liability/expiring/needed correctly $0/— (not a bug); STR +
  last-wk pace + Net ROI populate for paid CEs.

## Known limitations / open
- **CVR & Net ROI blank** for CEs with no paid activity that week (organic PP sell-through) or
  not in snapshot `ces` (category CEs like "City Cards"). Data-honest; footnote says so.
- **needed/wk** only for dated CEs (open-dated don't expire) — by design.
- **PP %orders** removed as requested (was cross-window/approximate).
- On-disk report HTMLs may be stale — re-run `weekly_market_report.py <market>` to bake current PP.

## Extend later
- **Aries demand:** `prepurchase_aries_inventory_mapping` (partitioned by experience_date,
  half-hourly) has remaining PP inventory joined to Aries actual demand → "needed pace vs REAL
  demand" instead of "vs time-to-expiry".
- **Category benchmarks** for STR (currently STR is absolute) if a peer comparison is wanted.
- **Slack `#tf-prepurchase`** = approval/intent log (why a PP was done) — useful for the digest,
  not needed for detection.

## Commits (all on worktree-diagnostic)
- `ddd69d0` PP bucket added (§6c) + build_snapshot attach
- `7b05d29` reworked on fct_pp_tickets (FDT source)
- `4536272` header hover tooltips
- `af7b6c0` Net ROI fix (realized loss)
- `7e53bf0` (separate) hid Scale-Up table

## Run
```
cd scripts/weekly_report
python3 weekly_market_report.py north_america   # or italy / oceania / all
```
PP query is module-cached (one BQ hit across the multi-market build).
