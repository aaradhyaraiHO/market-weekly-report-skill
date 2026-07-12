# CE-Level Opportunity Flags — mined from market channels (2026-07-10)

**What this is:** the catalog of CE-level opportunity types the weekly report should surface, extended by mining what market teams flag *manually* in Slack (searches across #mkt-uk, #mkt-usa, #mkt-csee, #mkt-france, #mkt-netherlands, #mkt-mena, #mkt-iberia, #mkt-malaysia, #mkt-italy-switzerland-malta, #pod-live-entertainment; mid-June → early-July 2026).
**Relation to the weekly spec:** extends the opportunity catalog in `market-report-weekly-v1-spec.md`. Detection architecture unchanged: **RPC and CM1/order are the composite detectors; the driver split (CVR / AOV / TR / CR) routes each detection to a lane** ([Perf] / [BDM-Commercial] / [SP-Ops] / [Growth]). Plus the standing flag `RPC < CPC` = losing per click, no diagnosis needed.

---

## Base catalog (already in spec)

| Lane | Flag | Trigger | Action | $ sizing |
|---|---|---|---|---|
| Perf | Scale-up window | sustained CM1/RPC upswing + ROI>target + SIS room | +seasonality adjustment (±15%/7d), extend if CM2 sustains | incremental $/wk |
| Perf | De-scale / trim | sustained downswing, ROI under target | −adjustment / revert / pause call | CM2 bleed $/wk |
| Perf | CVR drop | paid CVR >~30% WoW | LP/campaign/tracking check before bid moves | clicks×ΔCVR×AOV×TR |
| Perf | No-bid exposure | enabled campaign, MCV/no-tROAS, spending | bring under bidding control | spend at risk |
| BDM | TR check | CM1/order swing driver=TR; incentive start/expiry | verify intended / renegotiate / extend | ΔTR×GBV/wk |
| BDM | PP opportunity | unsold PP inventory; PP price advantage | push allocation / price play | tickets×price |
| BDM | Price/AOV check | AOV swing w/ stable orders; undercut flags | parity check, mix review | ΔAOV×orders |
| SP | Completion-rate recovery | CR < ~90–95% on volume | vendor/cancellation investigation | rev×(targetCR−CR) |
| SP | Availability unlock | zero same-day inventory on high-same-day-GBV CE; OSR crash w/ stable clicks | inventory/API/LIC fix | same-day GBV share |
| SP | Checkout friction | S2C/C2O anomaly, setup bugs | setup fix | funnelΔ×traffic×AOV |
| Growth | Exclusive-supply capture | inventory live that comps lack | launch/scale while exclusive | comp benchmark rev |
| Growth | LP/content fix | LP2S drop isolated | MB page fix | LP2SΔ×clicks×CVR |

---

## The 9 new flags (Slack-mined), with evidence

### 1. Price-parity violation — [BDM] · the most frequent manual check
- **Evidence:** Kunal (#mkt-netherlands) posts lists "GYG / SP website cheaper than us"; #biz-ops-execution circulates "TGID 37771: GYG much cheaper than HO (running 20% discounts), BDM checking"; Rahul (#mkt-usa) "GYG has a 10% discount and is cheaper than us"; Siddhi (#mkt-malaysia) repriced PPL to match **Klook-with-highest-SIS**, not the cheapest comp (+5–6pp TR expected).
- **Flag:** our price vs GYG/Klook at **TGID grain**; benchmark rule = comp-with-highest-SIS, not cheapest.
- **Data:** `competition_external` scrape models (GYG/Klook/FeverUp) — computable today. Weekly-able.

### 2. Demand-ahead-of-presence / launch-by deadline — [Growth]
- **Evidence:** Rahul (#mkt-usa): "Dyker Heights — SV 15–20K/mo now, peaks 700K in Dec, all leading competitors already selling. Launch ASAP." Chloe (#mkt-france): 9 collections where GYG does up to $112K/mo but our 5K-SV threshold blocks campaign launch.
- **Flag:** rising SV + competitors selling + us absent/dormant → **launch-by date** derived from the SV seasonality curve + booking lead times. The countdown is what makes it weekly ("6 weeks left to catch the Dec ramp").
- **Data:** google-ads keyword SV (MCP has keyword ideas/volumes) + comp revenue.

### 3. Post-event scale-down miss — [Perf] · Parag's own words
- **Evidence:** Parag (#mkt-mena): "post-Eid scale down of campaigns hasn't happened properly. RPC dropped massively from 1st week of June to 3rd week."
- **Flag:** event in the register **ended** + spend/seasonality-adjustment not reverted. The symmetric twin of Phase-1's "extend-if-CM2-sustains" → **revert-if-event-ended**. Generalizes flout-revert-overdue.
- **Data:** action/events register only — zero new data. Near-free in Phase 1.

### 4. Channel-mirror opportunity — [Perf]
- **Evidence:** Deeksha (#mkt-usa) Bing analysis: 150% overall ROI, scaling the 21 winning campaigns +10%; Jatin (#mkt-singapore): "Bing will automatically be scaled given such high ROI"; Asfan (#mkt-usa): Google keyword-restricted → "Can we run campaigns on Bing?"; Italy V5 reports' recurring "No Bing campaigns — consider mirroring Google Search."
- **Flag:** proven Google winner (ROI ≥ target, spend ≥ floor) with zero/low Microsoft spend; OR Google-restricted CE with demand → Bing alternative.
- **Data:** `sum_microsoft_ads_spend` already in combined_entity_stats. Near-free in Phase 1.

### 5. Auction-position gap — [Perf]
- **Evidence:** Gokul (#mkt-uk), Blackpool Zoo: "50% SIS but Top-of-Page rate below 20%, whereas GYG is achieving ~50%." UK deep-dive: GYG/booking.com/tickete "scaling across every CE simultaneously," official sites entering.
- **Flag:** SIS healthy but **abs-top-of-page low vs comp** → bid/QS work, not budget. Cousin: **competitor-entered-auction** alert (auction insights).
- **Data:** auction insights + abs-top rate (google-ads MCP / SIS pull — Phase 2).

### 6. Wasted-keyword spend — [Perf hygiene]
- **Evidence:** Priyanka (#mkt-mena): "AIMax enabled, negation missed — Ain Dubai, Motiongate, Kidzania keywords at 0 CVR with high CPC"; Siddhant (#mkt-csee) negating generic "shala river" terms eating impressions.
- **Flag:** search terms with spend > $X and 0 conversions over L2W; AIMax/broad-match leakage.
- **Data:** search-terms report (google-ads MCP `get_search_terms`). Sits next to the no-tROAS standing table — same config-leak family.

### 7. Assortment-driven AOV — [BDM]
- **Evidence:** Gokul (#mkt-uk): "GYG offers a family option that helps increase overall AOV" (ours $83, CVR at benchmark — AOV is the gap).
- **Flag:** AOV materially below comp benchmark on same CE, **missing variant type named** (family/bundle/combo).
- **Data:** comp scrape variants. Monthly-grade detection; renders as a chip on weekly AOV-driver rows.

### 8. Payment-authorization health — [SP/Ops]
- **Evidence:** Rimen (#mkt-france), Paradis Latin: "OSR dropped as the payment authorization rate drops 80% → 68%."
- **Flag:** auth-rate drop ≥ Xpp per CE — distinct from generic OSR (different owner: payments, not vendor).
- **Data:** checkout/payments events. Phase 2.

### 9. New-CE launch QA scorecard — [Growth] · takeoff window only
- **Evidence:** Samkit's (#mkt-csee) de-facto standard "Optimisation Thread (New CE)" format: L14D clicks/CVR · hero products SDA · **price benchmarking %** · **product benchmarking %** · image/content issues.
- **Flag:** for CEs in first N weeks — a **checklist row** (price benchmarked ≥90%? hero SDA ✓? assortment vs comp ✓?) instead of waiting for metrics to fail.
- **Data:** drawer template + manual/comp inputs. Renders in the CE drawer.

---

## Phase fit

- **Near-free in Phase 1:** #3 post-event scale-down (register logic), #4 channel mirror (existing spend columns), #6 wasted keywords (one MCP pull, standing-table family).
- **Data exists, needs a join:** #1 price parity (competition_external), #7 assortment-AOV (same scrape).
- **Phase 2 pulls:** #2 SV/launch-by, #5 auction position, #8 payment auth.
- **Template, not pipeline:** #9 launch QA (drawer).

## Meta-lesson (standing ritual)

Every flag above came from a thread a human wrote. The Slack digest is not just context — it is the **discovery mechanism for the flag taxonomy**. Quarterly ritual: re-mine the mkt channels for "what are teams flagging manually that the weekly doesn't yet?" — the catalog is exactly whatever the teams were forced to do by hand last quarter.

## One ranking currency

All flags compete for Focus slots in recoverable-or-incremental **$/wk**. A flag that can't state its $ is commentary, not an opportunity.
