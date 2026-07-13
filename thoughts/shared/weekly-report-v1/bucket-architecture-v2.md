# Bucketing Architecture v2 — State vs Change

**Principle:** *Monthly = state, Weekly = change.* They are two different jobs that
share one measurement substrate. Weekly never re-runs the monthly classification —
it detects movement on top of the monthly state and recommends this-week action.

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        LAYER 2 — CADENCE BUCKETS                             │
│                                                                              │
│   MONTHLY (STATE)  — keep as-is        WEEKLY (CHANGE) — redesign            │
│   "where does this CE stand?"          "what moved & what do I do this wk?"  │
│   ───────────────────────────         ────────────────────────────────     │
│   priority cascade → ONE home          decomposition → direction → lane      │
│                                                                              │
│   2  ROI / CM2 Optimization            ┌── DEFEND  (revenue ↓) ───────────┐ │
│   3  Losing Ground                     │   temporary  → −ve seasonality    │ │
│   4  Scale Opportunities               │                (−15%/7d, ROI<120) │ │
│   5  Iteration                         │   structural → fix top factor     │ │
│   6  Untapped                          └───────────────────────────────────┘ │
│   7  New Launches                      ┌── COMPOUND (revenue ↑) ──────────┐ │
│   (1 Market Top / Gap = overlays)      │   temporary  → +ve seasonality    │ │
│                                        │                (+15%/7d, ROI>140) │ │
│                                        │   structural → scale-up           │ │
│                                        │                (ROI>155% ×4wk)    │ │
│                                        └───────────────────────────────────┘ │
│            │                           +  New CEs        +  PP (prepurchase)  │
│            │                                     ▲                            │
│            └────── inherits home as context ─────┘                            │
│                    (weekly READS state, never recomputes it)                 │
└────────────────────────────────────────────────────────────────────────────┘
                         ▲                              ▲
                         │      both import the         │
┌────────────────────────────────────────────────────────────────────────────┐
│                 LAYER 1 — SHARED MEASUREMENT SUBSTRATE                        │
│                                                                              │
│   Identity:   revenue = clicks × CVR × AOV × CR × TR                         │
│               ROI     = RPC / CPC          (RPC = CVR · CR · AOV · TR)       │
│                                                                              │
│   Decomposition:  Shapley / log-delta → one signed $ per factor             │
│                   (the six contributions sum to Δrevenue exactly)           │
│   Constants:      ROI floors 100/70/20 · RPC cliff −25% / gradual −10%      │
│                   · revenue bands · gain floor max($500, 0.5% mkt wk rev)   │
└────────────────────────────────────────────────────────────────────────────┘
                         ▲
┌────────────────────────────────────────────────────────────────────────────┐
│                 LAYER 0 — DATA SOURCES (BigQuery)                            │
│   combined_entity_stats · google_ads_campaign_stats · fct_orders ·          │
│   dim_combined_entities · competitor_weekly_stats · revenue_goals           │
└────────────────────────────────────────────────────────────────────────────┘
```

## Weekly engine — runs for every CE, every week (no thresholds; pure measurement)

Produces the row substrate every bucket filters on:

| Field | Meaning |
|---|---|
| `direction` | revenue ↑ / ↓ (WoW, YoY-aware) |
| `total_delta_usd` | signed $ move |
| `factor_breakdown` | signed $ for clicks, CVR, AOV, CR, TR (sums to total) |
| `roi_split` | ΔROI attributed to RPC-side vs CPC-side |
| `time_shape` | `temporary` (single-wk / reverting) vs `structural` (sustained ≥2 wk) |
| `paid_state` | ROI now, trailing-4wk ROI, tROAS, tROAS-vs-actual pp gap |
| `monthly_home` | **inherited** monthly bucket (context, not recomputed) |

## Weekly bucket contract

| Bucket · lane | Trigger | Key columns | Action | Owner |
|---|---|---|---|---|
| **Defend · −ve seasonality** | rev↓, temporary, existing CE, ROI<120% | swing %, ROI, past-2wk ROI | cut −15% / 7d (campaign level) | Perf |
| **Defend · structural** | rev↓, sustained ≥2wk, ≥ gain floor | factor breakdown, ROI, sold-out% | fix top factor (routing ↓) | per factor |
| **Compound · +ve seasonality** | rev↑, temporary, existing CE, ROI>140% | swing %, ROI, past-2wk ROI | +15% / 7d (campaign level) | Perf |
| **Compound · scale-up** | Paid ROI>155% × 4 consec wk | tROAS, actual ROI, pp gap | fund; pp gap>+20 → also +ve seasonality | Perf |
| **New CEs** | launched ≤ N wk, not yet Pro+ | tier, weeks-since-launch, clicks | iterate (MMP inputs, coverage) | Growth |
| **PP (prepurchase)** | CVR or CR below own band / category median | CVR, CR vs band | prepurchase content / UX lever | PP |

## Factor → owner routing (structural Defend & Compound)

| Top factor | Read | Owner |
|---|---|---|
| clicks ↓ | dormant campaigns vs demand drop | Perf / seasonal |
| CVR ↓ | funnel or paid traffic quality | PP / Growth (Perf if click-quality) |
| CR ↓ | checkout / booking drop-off | PP |
| AOV ↓ | basket / mix | Pricing / Merch |
| TR ↓ | take rate | Pricing / SP |
| CPC ↑ (ROI↓, RPC flat) | bids / auction | Perf |

## What changes vs today

- **Keep:** B2 (→ the temporary/seasonality lane) and Scale-up (→ Compound-structural).
- **Replace:** B1 + B3 → the Defend engine (produces cost/clicks/CVR/AOV/CR/TR natively —
  no bolt-on columns; kills the "New+Existing mix" scoping problem via the New bucket).
- **Add coverage:** AOV, CR, TR, CPC now trigger buckets on their own instead of being
  Shapley decoration only.
- **Monthly:** untouched. Weekly inherits its `home` bucket as a context tag.

## Validated bucket set (v9, NA W0 2026-06-29 — dry-run converged)

Two engines feed the buckets: the **weekly decomposition** (structural) and the
**daily POF engine** (B2 `bucket1_fluctuations` — CM1/conv, RPC, CVR daily swings with
cause_tag) folded into Seasonal. Router priority (single home): New(parked) → ROI bleed
→ ROI cliff → Scale-Up → material weekly move → **Funnel Bleed** → daily-swing Seasonal
→ chronic-marginal → none.

| Bucket (group) | NA n | Entry |
|---|---|---|
| **Slipping** (Defend) | 20 | ROI bleed<100 / cliff>30pp / chronic-marginal<110 / sustained rev↓ |
| **Seasonal Dip** (Defend) | 6 | temporary rev↓ (weekly) OR daily-POF down-swing; ROI<120 → cut, else investigate |
| **Funnel Bleed** (Defend) | 6 | flat net, material CVR loss masked by volume (Niagara Canada −$11.7k) |
| **Scale-Up** (Compound) | 6 | ROI≥155%×4wk OR loading (rising≥2wk, crossed 110, net≥0) |
| **Seasonal Spike** (Compound) | 7 | temporary rev↑ OR daily-POF up-swing; ROI>140 → +15%/7d |
| **Compound gain** (Compound) | 2 | sustained rev↑ |
| *New CEs* | parked | Aaradhya's framework |
| *Prepurchase* | parked | supply/lead-time lever — needs fct_bookings lead-time, fct_pp_tickets STR, availability |

**PP note:** Prepurchase at Headout = buying inventory upfront to cover venue sell-out /
same-day restriction (a supply lever), triggered by lead-time collapse + availability-driven
CvR drop. It is NOT a funnel bucket — the earlier "Prepurchase" bucket was a mislabeled
**Funnel Bleed** (hidden CVR loss). Real PP needs data not in the weekly mart → parked.

## Open decisions

1. Structural boundary N (proposed: **≥2 consecutive weeks**).
2. PP trigger definition (proposed: CVR/CR below own trailing band or category median).
3. Material-move floor (proposed: reuse gain floor `max($500, 0.5% trailing-4wk mkt wk rev)`).
4. CM1/conv margin overlay — off the revenue identity; rides alongside as a margin escalator
   into Defend when revenue is flat but margin bleeds.
