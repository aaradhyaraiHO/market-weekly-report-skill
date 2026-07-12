# Bucket logic — gap audit vs the locked spec (NOTES ONLY, no fixes)

**Audited 2026-07-10** · spec = `thoughts/shared/market-report-weekly-v1-spec.md` §5 (mirrors the FINAL sheet `17xVzKYKb8hfSYVNoj…`, tabs B1–B5 + Overview). Built code = `scripts/weekly_report/{bucket_b1,bucket_b3,bucket_b4,flows,alerts}.py`.

Legend: ✅ built · 🟡 partial/approx · ❌ missing.

## B1 — ROI / CM2 Movement
- ✅ Entry doors: >30pp WoW drop < tROAS (CLIFF), <100% 2+ wks (NEW grind), escalation, exit.
- ✅ Truth table (Pause/Investigate/Transition + sub-reason) — imported from `ce_buckets.classify` thresholds; weekly Monitor·Cliff branch (gap #18).
- ✅ Movement flags NEW/CLIFF/ESCALATION/EXIT; ✅ CM2 bleed $/wk ranking; ✅ tROAS target; ✅ standing count line.
- 🟡 Hysteresis EXIT = single-week (spec wants sustained-2wk); exit constant 105 (spec §9.5 pending perf).
- 🟡 Spend floor = WEEKLY_SPEND_FLOOR $50 (spec B1 = **$1k/4w**); ❌ **long-tail burn line** (sub-floor aggregate) not emitted.
- ❌ **TR vs pre-change baseline** (change-point window) · ❌ **price/guest Δ** · ❌ **gray-zone counter** (N within 5pp) · ❌ **zero-revenue & zero-SPEND transition flags** · ❌ **MCV flag** (links no-tROAS table).
- ❌ **Sparkline**: RPC weekly + CM2 $/wk, 8w — no B1 spark data emitted.
- 🟡 Sort = (is_exit, bleed asc); spec = movement-class → recommendation-severity → CM2 asc (Investigate sub-order).

## B2 — Unexplained CM1/Conv Swings
- ✅ Detection = POF engine as-built (SDLW/WoW ±25%, 28d dev, persistence, CV, volume floors) — validated.
- ✅ cause_tag innocence routing (input-induced / supply-linked / unexplained / up-swing); ✅ Shapley swing-driver; ✅ daily CM1/conv spark + 28d baseline; ✅ CV-excluded count.
- ❌ **TR vs baseline** · ❌ **price/guest Δ** · ❌ **gray-zone counter** · ❌ **Known-cause writeback** dropdown (render-side) · 🟡 RPC shown as signal but not a dedicated evidence column.

## B3 — Losing Ground (forecasting)
- ✅ Pro+ gate (imports `bands.py`); ✅ ≥1-band fall; ✅ ≥2 wks on pace; ✅ reason cascade dormant→inputs→paid-opt→manual + owner actions; ✅ band now/projected/peak.
- 🟡 **Projection basis = weekly-RR pace (recent-4wk vs trailing)** — spec wants **MTD-extrapolated, weekday-corrected** reconciling with the team band sheet. Functional approx; NOT the spec method.
- 🟡 Ranked by projected monthly loss; spec = **cumulative structural loss over the streak**.
- ❌ **TR 4w YoY column** (next to RPC) · ❌ **🍂 seasonal tag** (sort-last) · ❌ **Turbulence flag** (manual writeback) · ❌ **comp same-CE trend** (GYG) · ❌ **Band-explorer cohort header** ("N of Pro+ universe") + on-pace-to-RISE counter.
- ❌ **Sparkline**: Rev'26 + Rev'25 grey, 10w + 4 forward LY wks.

## B4 — Scale Windows
- ✅ 3 lanes (sticky / ⚡NEW WAVE + Louvre guard / 🔄LOADING); ✅ gain floor max($500, 0.5% mkt); ✅ zero-spend flip; ✅ est-incremental ranking.
- 🟡 Sticky-lane stickiness = 2-wk rev growth proxy (spec = "in 80%-gains set ≥2 wks").
- ❌ **SIS <40% gate** (deferred — no weekly SIS pull; noted "check SIS" in action) · ❌ **supply-headroom** gate · ❌ **CVR-vs-category-bench + RPC-vs-median** gates (gate LOADING) · ❌ **RPC-Upside sizing** = (CVR_bench−CVR)×clicks×AOV (crude proxy instead) · ❌ **gain-driver** (CVR-led vs AOV-led) · ❌ **monthly-tag** (wave on a Losing-Ground CE = recovery).
- ❌ **Sparkline**: Rev weekly + RPC weekly, 10w. · 🟡 lane-a-vs-fresh-tROAS gap (#16) observed live (0 sticky rows) — spec fix pending perf.

## Header / flows / themes
- ✅ Structural Δ (centered LY ratio ±100% cap, $200 guard); ✅ G/L + N80; ✅ dual-clock verdict + disagree; ✅ theme attribution (contribution index ≥1.5× + $2k floor); ✅ concentration demotion; ✅ baseline-sensitive marker; ✅ routing (cards/market_rca/mixed).
- 🟡 Week-type thresholds = market-rev floor (spec = **52w-percentile calibration per market**).
- ❌ **Masking detection** (run week-type classifier per group — Six Flags case) · ❌ **in-bucket cluster detection** (collapse many same-direction bucket entries into one market-level line — France heat-wave case) · ❌ Shapley cross-read in header.

## Cross-bucket mechanics — BIGGEST STRUCTURAL GAP
- ❌ **Home cascade B1>B2>B3>B4** — buckets are computed independently; a CE can appear in several with **no single-home dedup**.
- ❌ **`(also in …)` chips** · ❌ **hard cap 10 narrative rows** (B1 + verdict-due B5 never dropped, rest by $ at stake, overflow counted) · ❌ **row anatomy** (Omni/store links, weeks-in-state, monthly-bucket tag, group chip, DRI, owner lane).

## Not built (known / blocked)
- ❌ **B5 Action Verdicts** — needs tracker infra (spec §8 defers).
- ❌ **OV1 Top-CEs strip** (5–7 by rev + 🔴🟡🟢 health) · ❌ **OV2 Gap/Pacing** (needs `revenue_goals` + Adjusted RR).
- ❌ **Standing tables**: no-tROAS ✅ built; Slack digest ❌; action-register drift ❌.
- ❌ **Deliberate-action register (§7)** as a standing table (only the bid-change innocence join exists inside B2).
- ❌ **ce_groups + NA seed** (group-first rendering — falls back to bucket-first).

## Prioritized fix themes (when we resume)
1. **Cross-bucket cascade + dedup + hard-cap-10 + `(also in)` chips** — the spec's core rendering contract; currently CEs double-count across buckets.
2. **Per-bucket sparklines** (B1 RPC/CM2, B3 Rev TY/LY+4, B4 Rev/RPC) — only B2 daily spark exists.
3. **TR-vs-baseline + price/guest Δ + gray-zone counters** (B1/B2/B3) — need daily + change-point sources.
4. **B3 MTD-extrapolation** (replace weekly-RR approx) + TR-4w-YoY + seasonal tag.
5. **B4 gates**: SIS / supply / CVR-bench / RPC-median + RPC-Upside sizing (SIS deferred on data).
6. **Header**: masking + in-bucket cluster detection; week-type 52w-percentile calibration.
7. Blocked-on-data: B5 (tracker), OV2 pacing (goals), standing digests.
</content>
