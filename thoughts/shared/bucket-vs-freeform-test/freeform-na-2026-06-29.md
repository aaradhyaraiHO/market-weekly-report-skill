# North America — Free-Form Weekly Revenue Analysis
**Week analyzed:** Mon 2026-06-29 → Sun 2026-07-05 (TW)
**Comparisons:** WoW = 2026-06-22→28 (LW); YoY = weekday-aligned −364d = 2025-06-30→2025-07-06
**Analyst:** independent free-form pass, BigQuery only (fct_orders net revenue `amount_revenue_usd`, google_ads_campaign_stats CM1 = `sum_conversion_value_offline_contribution_margin`, mixpanel_user_funnel for traffic/CVR)
**Known gap:** `revenue_goals` (and its staging view) is a Drive-backed external table — query denied ("Permission denied while getting Drive credentials"), so target attainment could not be computed. Flagged, not silently skipped.

---

## Market summary

| Metric | TW | LW | WoW | YoY wk | YoY |
|---|---|---|---|---|---|
| Net revenue | $618.5k | $607.5k | **+1.8%** | $409.2k | **+51.1%** |
| Orders | 10,581 | 10,927 | −3.2% | 7,925 | +33.5% |
| Rev/order | $58.5 | $55.6 | +5.2% | $51.6 | +13.4% |
| Guests | 32,023 | 32,361 | −1.0% | 24,308 | +31.7% |
| Google spend | $290.2k | $290.2k | 0.0% | $237.3k | +22.3% |
| Google CM1 | $366.4k | $370.0k | −1.0% | n/a (2025 CM1 unpopulated) | — |
| Blended ROI | 126.3% | 127.5% | −1.2pp | — | — |
| Paid clicks | 207.8k | 196.6k | +5.7% | 161.4k | +28.8% |

Structure: this is a paid-led market — ~85% of TW net revenue carries a Paid channel tag ($527k of $618k). YoY growth is a spend-reallocation story: +22% spend YoY but redeployed from NYC attractions into Niagara, Chicago cruises, Disney/Universal, and Hawaii, at CPC down 1.47→1.40. Top-5 CE concentration = 46% of revenue.

---

## Claims

### C1. Market: flat-to-up week masking a volume decline — growth is 100% AOV/mix
(a) Revenue +1.8% WoW but orders −3.2%; rev/order +5.2% ($55.6→$58.5).
(b) Root cause: deliberate Vegas spend cuts removed ~1,000 low-AOV orders (see C4, C5-HighRoller), while high-AOV CEs (Niagara $74/order, WDW $105/order, KSC $81/order) grew. Not a demand problem: market paid clicks +5.7% WoW, blended ROI stable at 126%.
(c) Impact: neutral this week, but the market is now more concentrated and more price-sensitive.
(d) Action: none at market level; act at CE level below. Urgency: low.

### C2. Kennedy Space Center (3111): −16% WoW on a July price increase; −57% YoY on paid pullback — two separate problems
(a) Rev $61.3k→$51.6k WoW (−$9.7k); orders 839→640 (−24%). YoY: $119.4k→$51.6k (−$67.8k/wk, −57%).
(b) Root cause, WoW: **conversion, not traffic**. Select-page users +9% WoW (11.9k→12.9k) but CVR fell 11.5%→7.96% (−31%), and the loss is deep-funnel (checkout→purchase ~39%→~30%). This coincides exactly with a price step-up: price/guest was $77–85 all June, then $92–100 every day Jul 1–5 (+15%); rev/order rose $73→$81. Take rate stable (~26–28%), so it's sell-price, not margin games. Paid ROI fell 144%→111% on flat spend ($32k) — you're now buying the same clicks into a worse-converting page. Root cause, YoY: spend halved ($70.0k→$31.5k), clicks −51% (34.9k→17.1k), sessions −71%.
(c) Impact: −$9.7k/wk WoW; if CVR elasticity is fully price-driven, the price increase is net revenue **negative** (orders −24% vs price +15%). YoY gap −$67.8k/wk.
(d) Action: confirm who changed KSC pricing/ticket mix around Jul 1 (supplier price rise vs markup change); if markup, A/B back to June pricing immediately. Separately decide whether the −55% YoY spend level is intentional. Urgency: **high — this week's #1 revenue leak on the market's #3 CE.**

### C3. High Roller Observation Wheel (2094): take rate jumped 20%→32% around Jun 26–27 and conversion collapsed — value-destroying price/markup change
(a) Rev $12.1k→$9.6k WoW (−20%); orders 448→315 (−30%). YoY −54% ($20.7k→$9.6k).
(b) Root cause: unambiguous in daily data. Through Jun 25: take rate ~19–23%, price/guest ~$29–32, ~60–80 orders/day. From Jun 26–27 onward: take rate 30–34.5%, price/guest $39–42, orders fall to 23–46/day. Funnel confirms: select→checkout 25.8%→18.6% (−28%), CVR 11.2%→6.8% (−40%) on traffic **+10%**. Paid: CM1 $10.3k→$7.8k, ROI 158%→103% — the margin grab lost money even in CM1 terms, on rising spend ($6.5k→$7.6k).
(c) Impact: −$2.5k/wk net revenue and −$2.5k/wk CM1 vs pre-change run-rate; annualized ~$130k if left alone.
(d) Action: roll back (or split-test) the Jun 26 markup/price change this week; don't scale spend into an 18.6% sel2co page. Urgency: **high — cleanest cause→effect in the dataset.**

### C4. Las Vegas group (Immersive Theatre 1104-LV, LV Shows 49, + High Roller): deliberate spend cut removed ~$20k/wk
(a) Immersive Theatre: rev $47.9k→$33.5k (−$14.3k, −30%); LV Shows $11.4k→$8.5k (−$2.9k, −25%). With High Roller, Vegas −$19.6k WoW — the entire market orders decline.
(b) Root cause: pure traffic withdrawal. ITLV spend −29% ($22.7k→$16.0k), clicks −24%, sessions −23%, CVR **flat** (9.40→9.39) — demand quality intact. LV Shows spend −46% ($8.4k→$4.5k), sessions −30%. ROI improved (ITLV 119%→130%, Shows 107%→120%), consistent with intentional efficiency trimming of sub-target campaigns.
(c) Impact: −$17.2k/wk revenue, roughly −$9.5k/wk CM1 foregone (ITLV CM1 $27.0k→$20.9k, Shows $8.9k→$5.4k) in exchange for +11pp ROI.
(d) Action: confirm the cut was deliberate and sized correctly — CVR-flat means the marginal spend was converting; if the ROI floor allows, restore ITLV partially (it's a top-6 CE). Urgency: medium — decision review, not a fire.

### C5. NYC attractions group: −$66k/wk YoY from paid defunding, while conversion actually improved — demand is intact, traffic was withdrawn
(a) Group (Edge, SUMMIT, AMNH, One World, American Dream, MoMA, Intrepid, ESB, Statue of Liberty, TotR, 9/11, CP Zoo, Met): TW ~$52.9k vs LY ~$118.9k → **−$66k/wk**. Individually: Edge $40.1k→$15.0k, SUMMIT $21.7k→$13.7k, AMNH $14.8k→$3.8k, American Dream $10.4k→$1.2k, One World $11.3k→$7.0k, MoMA $5.6k→$1.7k, Intrepid $5.3k→$0.8k.
(b) Root cause: paid withdrawal, not demand. Group paid-channel revenue −56% YoY ($101.3k→$44.5k). Spend YoY: AMNH −86%, American Dream −95%, Edge −48%, SUMMIT −43%, MoMA −75%, Intrepid −89%. Meanwhile YoY CVR **improved** where measurable: Edge 7.0→9.8%, SUMMIT 4.4→9.1%, AMNH 13.8→16.0%, ESB 5.0→10.1%. Sessions down 70–90% YoY across the group.
(c) Impact: −$66k/wk vs LY. Even at a conservative 120% ROI re-entry, tens of $k/wk of profitable volume appears recoverable.
(d) Action: this is the biggest strategic YoY gap in the market. Re-entry is already being tested and is working where ROI-led: Edge spend +13% WoW at ROI 141% → rev +23%; One World spend +140% → rev +77% at ROI 127%. But SUMMIT is being re-scaled badly: spend +36% WoW into CVR −22% (11.7→9.1%) and ROI 140→107%. Recommend: continue Edge/One World ramp, pause SUMMIT ramp until its select→checkout drop (26.5→21.4%) is diagnosed. Urgency: **high (portfolio-level dollars).**

### C6. Niagara Falls US (2567) + Canada (2554): the market's growth engine — $123.0k/wk combined, +8.6% WoW, +192% YoY; keep feeding it
(a) US: $72.6k (+$8.2k WoW, #1 CE; LY $25.8k). Canada: $50.4k (+$1.6k WoW; LY $16.3k).
(b) Root cause of growth: paid scale-up **plus** conversion transformation. US spend +146% YoY ($19.7k→$48.5k) at ROI 131%, and US CVR went 1.35%→8.11% YoY (6×) — last July the CE barely converted; whatever changed in product/landing since has made paid scalable. This week CVR still improving (7.34→8.11 WoW). Canada ROI 137%.
(c) Impact: +$81k/wk YoY; +$9.8k WoW.
(d) Action: budget headroom exists — budget-lost impression share is only 2.3–2.4% but non-zero at ROI 131–137%; test raising caps. Watch Canada ROI (163%→137% WoW as spend +27%) for dilution slope. Urgency: medium (opportunity, not risk).

### C7. Cruises – Chicago (18-Chicago): #2 CE at $67.8k but conversion is softening — early-warning watch
(a) Rev −1.7% WoW ($69.0k→$67.8k); orders −6.7% (1,780→1,660). Essentially a new bet vs LY ($3.3k → $67.8k, spend $2.5k→$31.5k).
(b) Root cause of the soft week: CVR 11.32→9.91% (−12%) and select→checkout 24.9→22.9% on traffic **+8%**; ROI eased 146%→137%. Take rate actually improved (22.8→25.2% by week-end) and price/guest stable — so not price; likely audience dilution as clicks scale or availability/weather on specific sailings. Daily revenue held $8.5–11k with no cliff.
(c) Impact: ~−$1.2k WoW; risk is larger — at $32k/wk spend a further CVR slide of 1pp ≈ −$6k/wk revenue.
(d) Action: monitor CVR daily; check sold-out sailings / boat capacity for peak slots before adding budget. Urgency: medium.

### C8. Hawaii cluster (Luaus 6074, Kualoa 6495, Star of Honolulu 6496): $25.1k/wk of essentially new YoY revenue, conversion improving, and clearly under-fed
(a) Luaus $14.9k (+48% WoW), Kualoa $6.3k (+12%), Star of Honolulu $3.9k (+70%). LY combined ~$0.3k.
(b) Root cause of the jump: CVR gains, not spend — Luaus CVR 8.0→10.1% (+26%) and checkout rate 32–33% (best-in-market), on spend flat WoW ($5.0k); ROI 169%. Star ROI 159%, Kualoa 128%.
(c) Impact: +$8.5k WoW; the cluster is running ~170% ROI with static budgets — leaving profitable volume unbought.
(d) Action: raise Luaus/Star budgets 30–50% and re-measure; Kualoa scale more carefully (ROI 183→128% as spend +54% WoW — dilution already visible). Urgency: medium-high (peak Hawaii season is now).

### C9. Universal Studios Orlando (2331): paid running at 100% ROI (breakeven) with CVR down 27% WoW — bleeding quietly
(a) Rev $12.6k→$10.5k WoW (−17%); also below LY ($13.8k, −24%) despite the park's Epic-era demand. Contrast: Universal Hollywood +7.5% WoW at ROI 135%.
(b) Root cause: CVR 3.23→2.37% on traffic +11% (clicks +20%, spend +11%); ROI 135%→100%. Price/guest stable (~$220) and take rate stable (~10%) → not price; the extra bought traffic isn't converting (select→checkout 25.3→23.8). At a 10% take rate this CE has zero paid margin for error: CM1 $5.3k = spend $5.3k, economic profit ≈ $0.
(c) Impact: ~$5.3k/wk of spend earning nothing; −$2.1k/wk revenue WoW.
(d) Action: pull spend back to last week's level, audit which campaigns/queries added the incremental clicks, and revisit take rate with supply. Urgency: high (paid is free-rolling at breakeven).

### C10. Steamboat Natchez (6103): −25% WoW, checkout-rate driven
(a) Rev $8.7k→$6.5k (−$2.2k); orders 209→168. ROI 156%→112%.
(b) Root cause: traffic flat (2,562→2,532 sessions), price/guest and take rate stable — but select→checkout fell 29.0→24.1% and CVR 13.4→10.8%. Pattern matches an availability/schedule gap (specific cruises unavailable) or checkout friction rather than demand or price.
(c) Impact: −$2.2k/wk.
(d) Action: availability audit on peak dinner-cruise slots for the July window; check sold-out states on the select page. Urgency: medium.

### C11. SUMMIT One Vanderbilt (3732): re-scaling into a broken week — spend +36% WoW for flat revenue
(a) Rev $14.1k→$13.7k (−2.5%) while spend $5.9k→$8.0k (+36%); ROI 140%→107%; YoY rev −37% ($21.7k).
(b) Root cause: bought traffic +37% (sessions 4.5k→6.2k) but CVR 11.7→9.1% and select→checkout 26.5→21.4% — incremental audience much colder, or page/pricing issue emerged. (Direct contrast: Edge NYC absorbed +13% spend at improving CVR and ROI 141%.)
(c) Impact: ~$2.1k extra spend for −$0.4k revenue; ~−$1.5k/wk CM1 vs holding budget.
(d) Action: hold SUMMIT budget at prior level; reallocate the increment to Edge/One World until sel2co recovers. Urgency: medium-high (it's live spend).

### C12. Sub-100% ROI tail — ~$8k/wk of spend destroying margin
(a) TW ROI by CE: Cruises–New York 22% ($684), Seattle→Victoria Ferry 26% ($1.1k), Mendenhall Glacier 0% ($480, zero CM1), Boston Tea Party 52% ($819), Grand Canyon Helicopters 60% ($1.6k), Schlitterbahn 74% ($1.3k), Six Flags Magic Mountain 75% ($489), 9/11 Museum 84% ($403), Seattle Whale Watching 89% ($2.6k), Knott's 88% ($540). Total ≈ $10k/wk at blended ~60% ROI.
(b) Root cause: mixed — Grand Canyon Heli also shows 20.4% budget-lost IS (capped *and* unprofitable = wrong structure/bids, not budget); Schlitterbahn 38.6% budget-lost at 74% ROI (same); Seattle Whale Watching persistently 78–89%.
(c) Impact: ≈ −$4k/wk CM1 vs breakeven; pausing/restructuring is nearly pure margin.
(d) Action: weekly hygiene sweep — pause or rebuild the sub-80% set; for Grand Canyon Heli specifically fix bidding before ever lifting the budget cap. Urgency: medium, cumulative.

### C13. Budget-capped winners: Boston Whale Watching (6105) and friends losing impression share while profitable
(a) Boston Whale Watching: rev $14.7k (+9% WoW), ROI 140%, but **11.4% of eligible searches lost to budget**. Cruises–San Francisco: ROI 107% with 22.6% budget-lost. New England Aquarium: spend was cut −39% WoW while ROI improved to 176%.
(b) Root cause: budget caps binding on profitable campaigns — the inverse error of C12.
(c) Impact: conservatively +$1.5–2.5k/wk revenue available at ≥130% ROI (Boston WW alone).
(d) Action: lift Boston WW cap ~20–30%; restore New England Aquarium spend; SF cruises only after ROI stabilizes >120%. Urgency: medium (seasonal window — whale season won't wait).

### C14. Walt Disney World (2330) + Disneyland (6321): the new-CE block is working — $49.0k/wk from zero LY
(a) WDW $33.3k (+20% WoW), Disneyland $15.7k (+8.7% WoW); both had $0 LY-week revenue.
(b) Root cause of growth: paid build-out (WDW spend +22% WoW to $16.7k at ROI 124%; DL $6.6k at 133%) with CVR improving (WDW 1.89→2.07%, DL 2.49→2.51). Watch: WDW ROI drifted 136→124% as spend scaled; 2.6% budget-lost on DL says room remains there.
(c) Impact: +$49k/wk YoY, +$6.8k WoW — largest single block of new YoY revenue after Chicago cruises.
(d) Action: keep scaling Disneyland (higher ROI, budget-constrained); scale WDW in smaller steps watching the ROI slope. Urgency: low (working as intended).

### C15. Mercer Labs (6530) + Arte Museum NY (6614): new NYC immersive niche compounding — scale it
(a) Mercer $6.8k (+53% WoW), Arte $3.6k (+28%); both $0 LY.
(b) Root cause: efficiency, not spend — Mercer ROI 97%→160% on spend −23%; Arte ROI 110%→151% with CVR 10.6→13.4%. Conversion quality is rising on both.
(c) Impact: +$3.2k WoW combined; ~$10.5k/wk new YoY revenue.
(d) Action: these two are earning a budget raise; test +30% with the savings from C12/SUMMIT. Urgency: medium.

### C16. American Dream (5962): defunded YoY (−$9.2k/wk) and this week's restart is misfiring
(a) LY $10.4k/wk on $12.5k spend; then defunded (spend ~$33 LW). TW spend restarted at $680 → ROI **18%**, rev $1.2k.
(b) Root cause: LY CVR was 4.8% with 11.3k sessions; TW CVR only 2.06% on 1.6k sessions — the restart is buying the wrong traffic or the product/page has degraded since (checkout rate 19.7% is fine; drop is post-checkout).
(c) Impact: currently trivial ($0.7k spend), but the YoY hole is −$9.2k/wk and the current re-entry path won't close it.
(d) Action: diagnose the post-checkout drop (pricing? inventory?) before spending further. Urgency: low-medium.

### C17. Country Music Hall of Fame (6853): quietly switched off — confirm intentional
(a) Spend $2,653→$239 WoW; sessions 2,049→317; rev $2.2k→$0.5k.
(b) Root cause: campaign pause/cut; LW ROI was 64% so the cut is defensible economics.
(c) Impact: −$1.7k/wk revenue, ~+$1.4k/wk CM1 saved.
(d) Action: confirm deliberate; if the CE stays, rebuild rather than restore (64% ROI wasn't viable). Urgency: low.

### C18. Alcatraz (144): +18% WoW, +166% YoY at ROI 125% — same playbook as Niagara working
(a) Rev $6.2k→$7.4k; LY $2.8k. CVR 3.7%→10.6% YoY.
(b) Root cause: conversion transformation vs LY plus modest paid ($1.6k/wk); traffic +20% WoW absorbed with CVR still >10.6%.
(c) Impact: +$1.1k WoW, +$4.6k/wk YoY.
(d) Action: spend is tiny relative to conversion quality — test scaling toward $3–4k/wk. Urgency: medium (opportunity).

### C19. High-value context: 2025 CM1 backfill gap in google_ads_campaign_stats
(a) `sum_conversion_value_offline_contribution_margin` is zero for all 2025 rows, so YoY ROI is not computable from this table.
(b) Root cause: column not backfilled pre-(roughly)2026.
(c) Impact: analytical only — YoY paid comparisons here rest on spend/clicks/revenue, not CM1.
(d) Action: note for data team; no growth action. Urgency: low.

---

## The 5 claims I'd lead with

1. **C3 — High Roller take-rate change:** the cleanest, most fixable finding. A dated (Jun 26–27) markup change that cut CVR 40% and lost both revenue and CM1. One decision reverses it this week.
2. **C2 — Kennedy Space Center July price increase:** same failure mode on a 5× bigger CE (−$9.7k WoW, ROI 144→111). Price elasticity is currently net-negative; needs an owner today.
3. **C5 — NYC group −$66k/wk YoY:** the market's largest dollar gap, caused by paid withdrawal while CVR *improved* — meaning recoverable demand. The re-entry playbook already shows what works (Edge, One World) and what doesn't (SUMMIT, American Dream).
4. **C8 + C13 — profitable CEs starved of budget (Hawaii cluster, Boston Whale Watching):** ~170% and 140% ROI with flat/capped budgets and double-digit budget-lost IS during their seasonal peak — the cheapest growth available this week.
5. **C9 — Universal Studios Orlando at 100% ROI:** $5.3k/wk of spend earning zero margin at a 10% take rate, with CVR down 27% — either fix the funnel/take-rate or cut spend; free-rolling is the one option that's wrong.
