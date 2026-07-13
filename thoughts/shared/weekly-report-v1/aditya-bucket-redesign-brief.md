# Weekly Buckets — Redesign Brief for Aditya

**TL;DR:** We rebuilt the weekly buckets (B1–B4) around a single revenue decomposition
(`revenue = clicks × CVR × AOV × CR × TR`, `ROI = RPC/CPC`). **All your recos are in.**
Validated on 3 markets (NA, Italy, Oceania) against real W0 = 2026-06-29 data — identical
gates, zero material moves lost. **One decision is yours: Scale-Up strictness.**

---

## Your recommendations → where they landed (all ✅)

| Your ask | New home | Status |
|---|---|---|
| **B1**: fix "New+Existing mix" · add cost & clicks | **Slipping** + New(parked) | ✅ Cohort split by data (not the unreliable flag); cost/CPC & clicks are native columns |
| **B2**: campaign-level rec · past-2wk ROI · ROI gates +ve>140 / −ve<120 · existing-only | **Seasonal Dip / Spike** | ✅ Verbatim; your daily CM1/conv POF engine is folded in |
| **Scale-up**: ROI≥155%×4wk · tROAS / actual ROI / pp-gap · pp>+20→+ve | **Scale-Up** | ✅ Verbatim (Aquarium of the Pacific = your exact def) |
| Seasonality & Levers sheet | action column + levers | ⏳ awaiting your sheet |

## The 6-bucket set (2 engines: weekly decomposition + your daily POF engine)

| Group | Bucket | Fires on |
|---|---|---|
| **Defend** | Slipping | ROI bleed<100 · cliff>30pp · chronic-marginal · sustained rev↓ |
| **Defend** | Seasonal Dip | temp rev↓ *or* daily down-swing; ROI<120→cut −15%/7d |
| **Defend** | Funnel Bleed | flat revenue but material CVR loss masked by volume |
| **Compound** | Scale-Up | ROI≥155%×4wk *or* loading (ROI rising, net≥0) |
| **Compound** | Seasonal Spike | temp rev↑ *or* daily up-swing; ROI>140→+15%/7d |
| **Compound** | Compound gain | sustained rev↑ |
| *parked* | New CEs · Prepurchase | separate frameworks |

## Validation — 3 markets, same gates

| | NA | Italy | Oceania |
|---|---|---|---|
| Actionable CEs | 47 | 44 | 37 |
| **Material moves unbucketed** | **0** | **0** | **0** |
| Defend recall vs B1/B3 | 0.47 | 0.67 | 0.64 |
| Gain floor (auto = 0.5% mkt wk rev) | $2,650 | $1,693 | scaled |

## THE DECISION YOU OWN — Scale-Up strictness

Your strict definition (ROI≥155% for 4 consecutive weeks) surfaces very few:

| Definition | NA scale CEs |
|---|---|
| **Your strict def** (155%×4wk only) | **1** (Aquarium) |
| **+ loading lane** (ROI rising ≥2wk, crossed 110, revenue not falling) | **6** |
| B4 today (sticky/newwave/loading, looser) | 12 |

We're proposing the middle (6). **Do you want strict (1), middle (6), or looser?**

## What the redesign catches that B1–B4 never did

1. **The two biggest NA drops were invisible to all current buckets** — Immersive Theatre
   −$14.1K and Cruises-Chicago (weekly volume drops; B2's daily engine didn't see them).
2. **Hidden funnel bleeds** — Niagara Falls Canada: revenue **flat (+$70)** but CVR
   **−$11,743**, masked by buying +15.5K clicks. B1–B4 structurally can't see this.
3. **B1 was ~50% noise / B4 ~58% over-flag** — the redesign keeps the real ones, drops
   weekly-ROI wobble, and adds ~15 net-new actionable CEs.

## Open (not blocking your review)
- Scale-Up strictness (above) — your call.
- New CE + Prepurchase frameworks — parked (PP = supply/lead-time lever, needs lead-time
  + STR + availability data, out of the current mart).
- Madame-Tussauds guard (W0 min-activity on chronic-marginal) — minor pre-lock fix.
