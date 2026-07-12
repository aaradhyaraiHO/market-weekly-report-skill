# Market Weekly Report — v1 Spec (final, locked)

**Status:** LOCKED 2026-07-07. **Buckets FINALIZED 2026-07-09** (bucket-by-bucket review): all three original [CONFIRM]s resolved (§9); §12b guards ported into the companion sheet; A/B agent test run (§14b). Remaining perf-team confirms: 🔄 LOADING arm, hysteresis exit constant, B4 lane-a gate vs fresh tROAS raises (§9).
**Companion sheet (buckets × metrics, shareable):** https://docs.google.com/spreadsheets/d/1lm3K02C95NdtLQhUvuBZ6kyLLkP_b6Y8UL_GdcN_48M
**FINAL snapshot sheet (with decision changelog):** https://docs.google.com/spreadsheets/d/17xVzKYKb8hfSYVNoj_Sf6lEV_C_LTFPa-GICFqzHoFY
**Relationship to monthly:** same bucket vocabulary and engine family as `market-report-buckets-v3-brief.md` / `ce_monthly_buckets`. Founding rule (Jun-5 spec): *same format across weekly & monthly — only the columns shown and the time window change.*
**Core law:** the monthly is the balance sheet (stock — full standing membership); the weekly is the transactions ledger (flow — a row must have **changed state this week, or have a decision due this week**, to render). Same accounts.

**Evidence base:** Parag's growth-model thread (C0975BGAX0B, p1780855655563239 — incl. the Jun-24 ping tagging Aaradhya "for inclusion in weekly reports"), Pari DM discussions Jul 3–7 (D0450L7CAAW), POF "CE avg CM1 fluctuation alert" sheet (1CR84MV1vTQoFfgWWdZkPXEoVFzSTfXL8mp_OpJRCNzY), Pari's "Weekly DB America" workbook (1xMpyuhwq1oy7I57jnbgrZ54BYIZ_DUfDpMLQLYV9Y3E) + her Jul-7 commentary recording, NA backtest on week 2026-06-29 (this session).

---

## 1. Jobs to be done (who asked)

1. **What kind of week was it, and what do we learn — by theme, not just net.** (Pari: week-types + 80% sets + Six Flags/Carowinds masking; her transcript narrates group-by-group.)
2. **Which few CEs deserve my hours this week, and why.** (Jun-5 founding spec: prioritize *what* to look at, never *how* to fix. NA has ~50 Pro+ CEs — attention is the scarce resource.)
3. **Catch money leaking now.** (Parag: ROI breaks, unexplained RPC/CM1 swings, symmetric wasted scale-ups, ~10% of spend, "$80K CM2 in 3 weeks… money to be saved here.")
4. **Did what we did land?** (Varun manually chasing "are the above action items closed?"; Pari's "did our actions land" + status taxonomy.)
5. **Protect the month while there's time.** (Pacing is a save in weeks 1–3, an autopsy at month-end.)
6. **Be the team's memory.** (Follow-ups graded from data, Slack digest, notes that provably round-trip. Every prior weekly died here — format resets wiped continuity.)

Jobs 1–2 are reading jobs; 3–5 are acting jobs; 6 compounds them.

---

## 2. Architecture — three layers

**L1 Fact layer (computed centrally, identical everywhere).** One row per CE×Monday-week carrying all states + all grouping attributes. Source: `ce_weekly_snapshot` / `ce_weekly_buckets` (conformed to v3 constants) + `int_ce_weekly_attribution` + new models in §8. State definitions, thresholds, cascades, clocks are **global — markets may not redefine them** (else portfolio roll-up and monthly reconciliation break).

**L2 Groups layer (declared locally, data not code).** `ce_groups`: `group_id · parent_group_id · group_name · market · ce_id · created_by · created_at`. Hierarchical (theme → sub-theme). Seeded per market from their own artifacts (NA: import Pari's `[Jul 26] CE Metadata` 8-theme/24-sub-theme taxonomy; Italy/SEA/CSEE: mine their WBR sheets). Rule-based groups allowed (e.g. `category='Musicals' AND market='Australia'`) so they self-maintain. Created/edited from the report UI (select rows → create group) — same writeback infra as GM Notes.

**L3 Rendering (per-market lens over shared facts).** Group-by any metadata dim or custom group; expand/collapse group → CE → metrics (Pari's SS1/SS2); saved views per market. **BGM default view = group-first** (groups are the sections; bucket states are chips on rows; per-group flow lines as group headers). **Fallback when a market has no curated groups: `groups := diagnostic buckets`** — i.e. bucket-first rendering is the degenerate case of group-first. Severity-ordered bucket queue remains the perf-analyst projection and the portfolio roll-up view. *Every market gets the same report reading their own map — the map is theirs, the legend is shared.*

**Per-market config row (parameters, not definitions):** tier display floor (NA: Hero+; smaller markets: Pro+), materiality floors scaled to market size, group ordering, Slack channel.

---

## 3. Report skeleton (section slots identical in every geo)

```
0. FOLLOW-UP        last week's items graded RESOLVED / CONTINUING (wk n) / REVERSED
                    — a QUERY over tracker rows, never regenerated prose
1. WEEK HEADER      revenue line · week type · gross flows · themes · routing note
2. CE NARRATIVE     sections = market's group set (fallback: diagnostic buckets)
                    rows admitted by bucket-state change; bucket chips; per-group flow lines
3. PACING           market + targeted groups/CEs, Adjusted RR (§6)
4. STANDING TABLES  no-tROAS campaigns (new-this-week) · Slack digest · action-register drift
                    (two failure modes: not reverted + not filed — the B5 starvation guard)
5. → STORE LINK     full tables, drill-downs, alternate projections, writeback lives here
```

---

## 4. Week header — flows, week type, themes

**Flows.** Per CE: structural delta = actual WoW − seasonally-expected WoW. **Expected ramp (locked after v2 backtest 2026-07-07):** ratio of 3-week *centered* LY averages (LY weeks [t−1,t,t+1] ÷ [t−2,t−1,t]), **capped at ±100% of last-week revenue**, guard: no expectation if LY base < $200 (falls back to raw WoW). The blend absorbs calendar drift (5-vs-6 July days) and one-off LY spikes (single-week Chicago July-4 explosion −$129K → −$31K); the cap bounds small-CE artifacts. G = Σ positive, L = |Σ negative|; base = prior-week revenue. **80%-contributor sets** with counts (N80). ⚠ Bucket membership near thresholds is baseline-sensitive (v1→v2 flipped Hawaii Luaus gain→loss, Nouvelle Eve wave→loss): borderline rows carry a "baseline-sensitive" marker.

**Dual-clock header (mandatory).** Raw line (WoW, YoY) AND structural line, explicitly labeled — never a bare verdict. Week-type labels resolve against BOTH clocks: loss-dominant + raw net ≥ 0 → **"UNDER-RAMPING vs LY seasonality"** (not "mostly loss"); loss-dominant + raw < 0 → "MOSTLY LOSS"; gains-dominant + raw < 0 → "BEATING SEASONALITY"; disagreement flagged inline. A +53%-YoY market must never read "mostly loss."

**Week type (5):** Mostly stable / Mostly gains / Mostly loss / Both large gains beat by $X / Both large losses beat by $X. Thresholds percentile-calibrated per market from trailing 52w (not hand-picked — small markets churn more in % terms).

**Routing rule.** N80-loss small (≈2–4 CEs) → those CEs get the deep-dive cards; N80-loss large (≈20+) → suppress CE cards, render ONE market-level RCA (systemic cause). The header decides how the rest of the report generates.

**In-bucket cluster detection (added after 3-market backtest 2026-07-07).** The same rule applies *within* buckets: many same-direction entries in one bucket in one week (France heat wave: 15 B1 ROI drops incl. Notre-Dame −47pp, Orsay −61pp, while B4 simultaneously caught indoor CEs surging) collapse into one market-level line ("systemic — likely exogenous demand shock; don't over-correct bids") with the CE list behind drill-down, instead of N rows. Backtest also cross-validated: Italy Duomo Florence = the B5 loop live (vendor re-enable Jun 19 → top structural gainer 2 wks later); Oceania Musicals Brisbane/Perth = identical CEs flagged by the POF alerts log independently.

**Theme attribution (mechanical, no LLM vibes):**
1. Aggregate structural gains/losses along every dim (subcategory, city, evolution/GEL, management type, launch cohort, LY tier) **and every custom group**.
2. Contribution index = share-of-loss ÷ share-of-revenue (same for gains). Flag if index ≥ ~1.5×, ≥3 CEs, $ materiality floor. **[thresholds directional — calibrate via 8-week Italy/NA backtest]**
3. Concentration check: top-CE share of theme delta >60% → demote to CE callout ("driven by Carowinds, not the group").
4. **Masking detection:** run the week-type classifier per group — net-flat groups with "both large" inside get surfaced (Six Flags case).
5. Dedup overlapping dims (report higher index, tag overlap). Render explicit "(unclassified: $X)" line — ~2,022 CEs have NULL metadata; never silently drop.
6. Shapley cross-read: flows = CE-dimension cut; Shapley (traffic×CVR×AOV×TR×CR) = metric-dimension cut of the same delta. Header carries both.

---

## 5. The buckets (diagnostic, home cascade in this order)

Weekly admission = **movement only**. Standing membership renders as one count line ("no changes; 8 standing — see monthly"). Empty bucket = one line ("none this week ✅") — that is information.

| # | Bucket | Entry (weekly-computable) | $ ranking metric |
|---|---|---|---|
| **B1** | **ROI / CM2 Movement** *(renamed from "Burning" 2026-07-09 — monthly-style naming; weekly movement view of monthly ROI/CM2 Optimization)* | ROI drop **>30pp WoW AND lands < campaign tROAS target** (fallback: market ROI target — healthy volatile CEs stay out), OR **<100% for 2+ consecutive wks** (✅ RESOLVED #3 2026-07-09: floor = 100%, shared constant with monthly — matches the bleed formula and the v3 truth table), OR recommendation escalation (Investigate→Pause at CHRONIC_WEEKS=6, ROI<20→Critical), OR exit. Hysteresis: enter <100% · exit >~105% sustained 2wks **[exit constant pending perf — §12b validated 110/115 pre-rebase]**. Spend floor $1k/4w + long-tail burn line for the sub-floor aggregate. **Deliberate-action tag mandatory** (§7). Added columns: tROAS current value · TR vs baseline (⚠ change-point window, not 4w avg — §14b F1) · price/guest Δ (§14b F6) · gray-zone counter · zero-revenue and zero-SPEND transition flags. | CM2 bleed $/wk = spend×(ROI−1) |
| **B2** | **Unexplained CM1/Conv Swings** *(renamed 2026-07-09)* | ✅ RESOLVED #1 2026-07-09: detection = POF CM1/conv engine **as-is** (SDLW/WoW ±25%; 28d baseline excl. last 3d, ≥20% dev; 3-day same-direction persistence ≥15%; CV≤0.50; ≥10 conv/day, ≥500 clicks), **RPC = evidence column, not trigger** + bid-change join + **supply/availability check before the UNEXPLAINED tag** (sold-out → route to Ops, not a Perf mystery). Downward alerts land here; upward route to B4 (with §12b guard #4). Added columns: TR vs baseline · Shapley swing-driver (traffic×CVR×AOV×TR×CPC — the Blue Grotto template, mechanical) · gray-zone counter. Weekly form = digest of the week's alerts. Count the CV-filtered ("N excluded as too volatile"). | CM1 delta $/wk |
| **B3** | **Losing Ground — on pace to fall** | Pro+ AND projection shows ≥1-band fall by month-end (✅ RESOLVED #2 2026-07-09: **MTD-extrapolated, weekday-corrected** — reconciles with the team band sheet; the ≥2-wks-on-pace rule absorbs week-1 thinness), ≥2 consecutive weeks on pace. Reason cascade unchanged from monthly: dormant → inputs (RPC) → paid-optimization → manual. Added column: **TR 4w YoY next to RPC** (a TR change must not read as an LP/feed hunt). 🍂 seasonal = tag sorted last, NOT exclusion (v2 decision). Column: weeks-on-pace. Retires with handoff note when monthly confirms. | cumulative structural loss $ |
| **B4** | **Scale Windows** *(renamed from "Ride the Wave" 2026-07-09 — weekly time-boxed view of monthly Scale Opportunities)* | Three lanes (2026-07-09): **(a)** in 80%-gains set ≥2 wks (sticky) AND ROI above target+margin; **(b) ⚡ NEW WAVE fast lane** — B2 up-alert enters immediately (POF gates already killed spikes), probe-capped action (+~20%) until stickiness earned, **§12b guard #4: only if structural revenue ≥ 0** (margin-up + revenue-down = "efficiency/mix shift — investigate pricing/TR", never scale); **(c) 🔄 LOADING [pending perf]** — ROI improving ≥2 wks AND crosses 110% AND CVR rising, probe-capped, exempt from the above-target gate (the Veiled Christ class). Gain floor = **max($500, 0.5% of trailing-4w weekly market revenue)**. All lanes: **SIS<40% pre-check** (Parag's confirmed rule; missing → "n/a", don't block) + supply-headroom check. ⚠ lane-a gate vs freshly-raised tROAS is self-defeating — §14b F2, pending perf. Monthly-Scale members with a weekly green light also surface here. Acting files a tracker item → CE reappears in B5. | est. incremental $/wk |
| **B5** | **Action Verdicts** *(renamed from "Did our actions land" 2026-07-09; unit = intervention)* | Tracker item at checkpoint this week (tROAS change, MMP iteration, scale push, supply fix, flout revert). Checkpoints (2026-07-09): **default wk 2/4/8 + per-type overrides** — tROAS first verdict wk 4, final wk 8 (4–6wk learning, Pranathi) · scale push wk 2/4 · supply fix wk 1/2. Verdict vs **pre-intervention baseline** (never WoW): Too early / Working / Not working / Slipped-after-working. Status: In progress / To be picked up / Deprioed (Pari). Expected $ vs realized $. Every verdict terminates in a decision: continue / iterate / rollback / close. **Starvation guard:** untracked-actions drift counter in the action-register standing table (actions in register/Google-Ads change history with no tracker item — named + counted). | expected-vs-realized $ |

**Overlays (always rendered, never a home):**
- **Top CEs strip** — 5–7 by revenue, health state: 🔴 broken=B1 · 🟡 watch = B3 signals **OR structural loss ≥2 consecutive wks OR YoY < −20% weekday-aligned (channel-agnostic catch-all, 2026-07-09 — organic erosion on an anchor cannot stay green)** · 🟢 = none. + "the one thing" only on 🟡/🔴. ⚠ candidate 4th trigger: pacing attainment <~70% (§14b F3, ITLV case). Green board = seven green rows, zero prose. Tier floor from market config; manual pin field for strategic small CEs.
- **Gap / Pacing** — §6.

**Permanently monthly (never weekly sections):** Scale membership, Iteration classification, Untapped, New Launches. They enter the weekly only via B5 when someone acts, or as count deltas ("2 launched → now tracked").

**Cross-bucket mechanics:** one home by cascade B1>B2>B3>B4 (+B5 keyed by intervention, linked not deduped); `(also in …)` chips; **hard cap 10 narrative rows** — B1 and verdict-due B5 never dropped; B3/B4/pacing fill remainder by $ at stake; overflow always counted ("+4 more in store"), never silent.

**Row anatomy (every row):** CE + Omni/store links · trigger (one sentence, metric from→to) · $ at stake/wk · weeks-in-state · monthly-bucket tag · group chip · deliberate-action tag · DRI (versioned source) · owner lane [Perf]/[Growth]/[SP] · GM Notes.

**Monthly-v3 ports (2026-07-09) — sparklines, columns, logic reused instead of reinvented:**

*Sparkline map (universal conventions from monthly v3: per-CE auto-scaled, ≤2 lines, prior-year always grey `#a0aec0`, null = gap never zero, baked JSON → SVG):*

| Bucket | Line 1 | Line 2 | Window |
|---|---|---|---|
| B1 | RPC weekly | CM2 $/wk | 8w |
| B2 | CM1/conv **daily** | 28d baseline band | 35d (only daily spark) |
| B3 | Rev '26 | Rev '25 (grey) | 10w **+ 4 forward LY wks** — shows what the CE should ramp into; the projection argument, drawn |
| B4 | Rev weekly | RPC weekly | 10w |
| B5 | target metric weekly | — | 4w pre-ship → now, **vertical marker at ship date** |
| Strip | Rev '26 | Rev '25 (grey) | 10w+4 (unchanged) |
| Pacing | cumulative MTD actual | expected-to-date curve | MTD |

*Column ports:* Rev/wk on B1 (size the bleeder) · **Known-cause writeback** on B2 UNEXPLAINED rows (dropdown: Closure/Inventory/TR/Price/Competition — bootstraps the register) · **Turbulence flag** (manual dropdown, monthly Losing Ground verbatim) + **Band Peak** on B3 · **CVR vs category bench** (gates 🔄 LOADING — rising toward bench ≠ recovering from terrible) + **RPC vs category median** on B4 · **GM Notes on every bucket**.

**B1 glossary (semantics, added 2026-07-09 — the sheet carries the same text):**

*Movement flags:* **NEW** = crossed in this week, via two doors — grinding (2nd consecutive wk <100%) or cliff · **CLIFF** = >30pp WoW drop landing < tROAS ("something happened" vs "something is rotting") · **↑ ESCALATION** = already in, worsened (wk-6 hardening Investigate→Pause, or fell into <20% Critical) · **EXIT** = back above floor + hysteresis, sustained — rendered deliberately, exits prove actions worked. No change = standing count line only.

*Truth table (classify.py, shared constants — ROI band = severity, weeks = patience, RPC = diagnosis):*
```
ROI < 20%                                  → Pause · Critical    (stop first, diagnose later)
ROI 20–70%:
  ≥6 wks, RPC not cliffed                  → Pause · Structural (RPC sliding −10..−25%) | Pause · Chronic (RPC flat)
  ≥6 wks, RPC cliff < −25%                 → Investigate · Chronic + new signal
  <6 wks, RPC cliff < −25%                 → Investigate · Input-induced
  <6 wks, RPC fine                         → Investigate · Recent entry / Watch
ROI 70–100%                                → Transition          (restructure; neither pause nor scale)
cliff entry, ROI still ≥100%               → Monitor · Cliff     (weekly-only branch, gap #18)
```
*The rebuild-or-walk-away fork:* **Chronic** (RPC flat ≥6wks) = clicks worth what they always were, we buy them badly → pause now, rebuildable later. **Structural** (RPC sliding gradually ≥6wks) = the value of a click is itself decaying → rebuilding buys the same decay; fix product/pricing or walk away. An RPC cliff always means investigate-before-bids — −25% value-per-click says page/price/feed broke; bid tuning won't fix it.

*MCV flag:* campaign on Maximize Conversion Value = Google auto-bidding with **no tROAS target at all** — outside the entire bidding-control system (nothing to tighten/loosen; every tROAS exercise silently skips it). Links to the no-tROAS standing table.

**B2 glossary (semantics, added 2026-07-09 — the sheet carries the same text):**

*Architecture:* opposite of B1 — the POF engine does the admitting, so columns split into **gate receipts** (prove the alert is real) and **innocence checks** (must ALL fail before the row earns "UNEXPLAINED").

*Why CM1/conv:* the composite tripwire — moves when any money-mechanic moves (TR, sell price, discounting, mix, CPC). RPC = evidence lens, not trigger (resolved CONFIRM #1).

*Gate receipts — each kills one false-positive class:* 28d baseline **excludes last 3 days** (a spike can't contaminate its own baseline and un-alert itself) · SDLW ±25% (day-of-week control — Tuesdays vs Tuesdays) · 7d-roll ±25% (catches grinds no single day breaches) · 3-day persistence ≥15% same direction (a whale booking or tracking hiccup is an event; three days is a state) · CV ≤0.50 (a chronically wild CE has no meaningful baseline — excluded but **counted**) · volume floors ≥10 conv/day + ≥500 clicks/35d (3→5 conversions is +67% and pure noise).

*Innocence checks, in order — each hit re-routes away from mystery:* (1) bid change in window → `input-induced (expected)` · (2) supply/availability broke → `supply-linked` → Ops · (3) TR step or (4) price/guest step (change-point windows) → `commercial change` → SP. All four miss → **UNEXPLAINED** — the $38K class, the only rows where "investigate" means nobody knows.

*Lifecycle:* daily engine → weekly digest (alert age, still-breaching vs recovered — a recovered alert closes itself) · down stays here, up routes to B4 ⚡ only if structural revenue ≥ 0 · Known-cause writeback feeds next week's register so the same cause never reads unexplained twice · gray-zone counter (Immersive Theatre missed the gate at −24.9% vs −25 and was NA's #2 problem).

**B3 glossary (semantics, added 2026-07-09 — the sheet carries the same text):**

*Architecture:* the only **forecasting** bucket — B1/B2 report what happened; B3 makes a falsifiable prediction ("ends the month ≥1 band lower"). Columns are: the forecast (band now on trailing-3mo run-rate · projected band = MTD ÷ LY-month daily-shape share, weekday-corrected · weeks-on-pace ≥2 — one week of projection is weather, two is a trend, and the rule absorbs MTD week-1 thinness) · the cause (cascade) · the credibility check · the sizing.

*Cascade order is the intelligence (first match):* 1 **dormant** (clicks 4w YoY <−85%) first, because dead campaigns make every downstream metric meaningless → revive [Perf] · 2 **inputs** (RPC <−20%) — each click worth less: LP/feed/pricing → [Growth/SP]; the TR 4w YoY column keeps TR-caused RPC falls routed to commercial, not an LP hunt · 3 **paid optimization** ((ROI YoY +20pp & >120%) OR >160%) — volume traded for efficiency, partly self-inflicted → loosen [Perf] · 4 **manual** — a human owes a diagnosis, starting at the Shapley top-2 layer.

*Credibility columns:* 🍂 seasonal = tag + sort last, never exclude (real dollars, expected cause) · **Band Peak** — a fall on a once-5xHero CE (proven demand) reads differently from a barely-Pro one · **comp same-CE trend** = the differential: GYG falling with us = demand problem (don't burn spend); GYG holding while we fall = share loss (fight).

*Sizing & lifecycle:* rank by **cumulative structural loss over the streak** (dollars already lost rank; forecasts qualify) · manual-arm action derivation via the Turbulence writeback (flag set → [Perf] awaits; RPC cliff no flag → [Growth] submits input; stable no flag → [Growth] structural investigation) · row retires with handoff note when monthly confirms — B3 is a feeder, and its precision is graded against the monthly transition matrix (band-explorer port, with the cohort header "N of Pro+ universe" and the on-pace-to-RISE counter).

**B4 glossary (semantics, added 2026-07-09 — the sheet carries the same text):**

*Architecture:* B1–B3 hand out homework; B4 hands out **budget** — so the burden of proof runs the other way and the columns form a gauntlet: prize → lane (proof) → pre-checks → sizing → exit.

*The prize:* structural gain > **max($500, 0.5% of trailing-4w weekly market rev)** — flat arm stops tiny-market blips, proportional arm stops big-market noise.

*Three lanes, three burdens of proof:* **(a) slow** — 80%-gains set ≥2 wks + ROI ≥ target+margin → full-size scaling (strongest proof) · **(b) ⚡ NEW WAVE** — B2 up-alert enters immediately (POF's gates already killed spikes) IF structural revenue ≥ 0 (Louvre guard: margin-up + rev-down = pricing/TR investigation, never scale) → **probe-capped +~20%** until stickiness earned — speed bought with a smaller bet · **(c) 🔄 LOADING [pending perf]** — ROI improving ≥2wks, crossing 110%, CVR rising toward/past category bench (separates loading from recovering-from-terrible); exempt from the above-target gate (it isn't above target *yet* — that's the point); probe-capped.

*The gauntlet — each check stops one way of burning cash:* **ROI headroom** (scaling always dilutes — Kualoa 183→128% at +54% spend; headroom = what you can give back on the way up) · **SIS <40%** (own the auction already → loosening pays more for the same customers; action flips to "check constraints") · **supply headroom** (never advertise a sold-out calendar) · **CVR-vs-bench + RPC-vs-median** (does traffic quality support more volume, or is the gain a mix fluke?).

*Sizing & context:* est. incremental via two lenses — naive SIS-gap, and **RPC Upside = (CVR_bench − CVR_actual) × clicks × AOV_net** (primary for 🔄) — crude is fine, it only ranks · **gain driver**: CVR-led = solid ground, AOV/mix-led = fragile (reverts) · **monthly tag**: wave on a Losing-Ground CE = recovery play.

*Exit:* **acting files a tracker item → the CE reappears in B5** — B4 rows are the only ones that create their own accountability by construction. Zero-spend flip: spend=$0 → "launch campaigns", never "scale".

*Logic ports:* B1 sort = movement class, then recommendation severity (Pause→Investigate→Transition), then CM2 asc; Investigate sub-order Chronic+new → Input-induced → Recent entry · B3 manual-arm action derivation: turbulence present → [Perf] await Growth; RPC cliff + no flag → [Growth] submit turbulence input; stable + no flag → [Growth] structural investigation · B4 **zero-spend flip** (spend=$0 → "launch campaigns", never "scale") + **RPC Upside** sizing = (CVR_bench − CVR_actual) × clicks × AOV_net (primary for 🔄 rows) · **one shared constants file** in `scripts/ce_buckets/` imported by both cadences (CHRONIC_WEEKS=6, RPC_CLIFF=−25%, RPC_GRADUAL=−10%, PAUSE_FLOOR=20, TRANSITION_FLOOR=70, ROI floor=100, SIS_GATE=40; weekly adds 30pp-drop, gain floor, hysteresis) — cross-cadence consistency mechanical, not aspirational.

---

## 6. Pacing (dissolved Gap, weekly form)

- Grain: market headline + targeted CEs/groups only (tabs-1–3 population). Silent on deliberately un-targeted CEs (Pari's United Parks rule — she tracks those as a group instead).
- **Adjusted RR, not linear** (her Goals DB computes both; adjusted is the trusted one): month-shape from LY daily distribution → expected-to-date → attainment; gap as **required $/day (her native unit)** for the remainder.
- Filters ported from monthly: drop if attainment ≥90%; drop below $ floor; render only while ≥2 weeks remain (then hand to monthly Gap columns).
- **Feasibility flag:** required rate >~1.5× best recent week → "reforecast", not "push harder".
- Gap attribution: which bucket rows explain the gap ("70% = 2 B1 CEs + 1 B3 CE"); gap with no sick CEs ⇒ target problem.
- **Weekday-aligned YoY everywhere** (her YoY tab): LY windows align by weekday; holiday-anchored weeks (Jul 4) anchor to the holiday. Applies to flows expectations too — headline structural claims depend on it.

---

## 7. Deliberate-action register (false-positive firewall)

One table of "we did this on purpose": tROAS/bid changes (phases, campaigns touched), PPC restrictions, holiday flouting (actioned / reverted / **revert-by date**), supply/pricing actions. Sources: perf change logs + ingest of PPC-Restrictions-style tabs. Every B1/B2 row joins against it → tag *input-induced (expected)* vs *unexplained*. June proved this is load-bearing: the tROAS easing would otherwise flood B1 with known causes; the genuinely alarming class was the **$38K CM2 from campaigns with NO bid change**. Free derived alerts: **flout past revert-by and not reverted** + **untracked-actions counter** (register/Google-Ads change history rows with no tracker item — 2026-07-09, guards B5 starvation). The A/B run (§14b) proved the register's value by inference alone: historized tROAS diffs found the Jun-23/24 broad raise (19 campaigns, ~$32K/wk) that explained the week's whole B1 cliff cluster — a cause the blind free-form analyst missed entirely.

## 8. Data & infra prerequisites

| Item | Why | Status |
|---|---|---|
| `ce_weekly_transitions` (state history self-join) | weeks_in_bucket, entries/exits/escalations — B1 is movement-only ONLY with this (NA backtest: without it, 26 rows instead of ~11) | build |
| `market_weekly_flows` (G/L, 80% sets, week type, per group) | header + routing + themes | build |
| `ce_groups` + seed fixtures | L2; NA seed = Pari's taxonomy | build |
| Band milestone columns (first week each band crossed → launch/Pro/Hero month) | new-Pro+ celebration table (Pari Jul-6 spec: Type Mature/GEL · launch date · ROI1 · rolling L6M monthly rev · CE-health link), launch cohorts | derive from history |
| Tracker one-click filing | B5 starves without it; biggest adoption risk | build |
| Notes schema: per CE×week, **two fields (WoW note, YoY note)** + status + group-level notes; provable round-trip | her Running Notes shape; "what happens to the notes I add here?" | build |
| **Validity gates** (metric sanity bounds before render) | old reports shipped 207% CVRs; backtest burned 2 rounds on unpopulated CM1 columns | build, non-negotiable |
| CM1 column = `sum_conversion_value_offline_contribution_margin` (google_ads_campaign_stats); `calculated_` variant unpopulated | ROI/CM2 correctness | verified in backtest |
| No-tROAS table: `current_campaign_target_roas` NULL/0 + ENABLED + spend floor | POF ask; NA has 25 such campaigns incl. 3/5 on Niagara US | column exists |
| Weekly SIS pull | B4 gate | deferred; "n/a" until then |
| MMP list in BQ | B5 auto-spawn from monthly Iteration | deferred |
| Slack digest prioritization matrix | Hero+ CE × revenue-impact topic (campaigns/LP/CVR/TR) | build |

**One-clock rule:** buckets = trailing-4w vs LY (weekday-aligned); bridge/flows = WoW; pacing = MTD vs target. Never cross-wire (the v4 monthly bug; Pari caught a live instance Jul-6: "flags YoY, data below MoM — hard to triangulate").

## 9. [CONFIRM] status

**✅ Original three — RESOLVED 2026-07-09 (bucket-by-bucket review, decisions in the sheet changelog):**
1. **B2 metric:** detection = POF CM1/conv as-built; RPC = evidence column, not trigger.
2. **B3 projection basis:** MTD-extrapolated, weekday-corrected (reconciles with the band sheet; ≥2-wks-on-pace absorbs week-1 thinness).
3. **B1 floor:** **100%, shared constant with monthly** — the bleed formula spend×(ROI−1) is only negative below 100; a 110 floor put profitable rows in "Burning". Plus: the 30pp-drop trigger now requires landing < target.

**Open — pending perf team:**
4. **🔄 LOADING arm (B4 lane c):** drafted — ROI improving ≥2wks AND crosses 110% AND CVR rising, probe-capped, exempt from above-target gate. Confirm mechanism + constants.
5. **B1 hysteresis exit constant:** §12b validated enter<110/exit>115 before the floor moved to 100; proposed enter<100/exit>105 sustained 2wks — exit level unvalidated at the new floor.
6. **B4 lane-a gate vs fresh tROAS raises (§14b F2):** gate vs market ROI constant (145%) or pre-raise tROAS for ~2wks post-raise — the Jun-23 NA raise produced 0 lane-a rows in a week with 4 fundable winners.

## 10. Build order

1. **Phase 1:** transitions model + flows model + validity gates → B1, B2, header, no-tROAS table. (Parag's explicit, dollar-quantified asks; he's a ready consumer.)
2. **Phase 2:** tracker + one-click filing + notes round-trip → B5 + follow-up section. (The habit-forming loop; prove writeback early.)
3. **Phase 3:** B3, B4, pacing (Adjusted RR), ce_groups + NA seed, group-first rendering.
4. **Phase 4:** theme threshold calibration backtest, Slack digest, per-geo rollout (mine each market's sheets → seed → same one-week backtest + BGM walkthrough as NA).

## 11. Backtest evidence (NA, week 2026-06-29)

Raw net +$11K masked a structural "Mostly loss" week: $37K gains vs $265K losses vs July-4 expectation; losses concentrated (7 CEs = 80% → the deep-dive list), gains diffuse (20). Caught: Kennedy −34pp ROI on $31.5K/wk; Immersive Theatre CM1/order −25% on $16K/wk (cross-confirmed by flows); Hawaii Luaus +$4.5K @169% ROI (B4); 25 enabled no-tROAS campaigns; Six Flags masking (+$831/−$1,649, Carowinds) — **via custom group only** (below automatic theme floors, confirming L2). Madame Tussauds NY: Parag's Jun-24 flag → spend $0 this week = the B5 story. Gaps found = infrastructure (state history, tracker seeding, goals join, validity gates), not taxonomy. Themes emitted: "Cruises-Sightseeing 49% of losses on 12% of revenue (4 CEs)"; gains over-represented in Long-Tail-2025/DNE-2025 cohorts (new entrants working).

## 12. What this is NOT (unchanged from Jun-5)

Not a how-to-fix recommender — it prioritizes what to look at; depth comes from /perf-audit, /ce-rca, and the humans. An action line must cite evidence from its own row or say "needs manual RCA" — no generic "full CE audit" filler.

## 12b. Robustness guards (validated on 4-market amended run, 2026-07-08)

1. **B1 matured-window ROI** — measured: NA week's CM1 grew +1.0% in ONE day of maturation (per-CE up to +18%). Rule: generate off data ≥3 days matured (POF's own convention), or lag-adjust. Monday-morning generation off Sunday data is prohibited.
2. **B1 hysteresis** + movement-only rendering: NA B1 26 rows → 4 NEW + 8 escalated + 10 exited + "13 standing" count-line. Exits are rendered — they're good news. ⚠ Constants rebased 2026-07-09 with the 100% floor: proposed enter <100% / exit >105% sustained 2wks (validated values were 110/115 — exit level pending perf, §9.5).
3. **Long-tail burn line** (sub-floor aggregate): NA 14 CEs / $1.5K/wk, Oceania 8 / $1.1K/wk — real money the floor was hiding.
4. **B2↑→B4 routing guard (refined on this run):** a B2 up-swing routes to B4 **only if structural revenue ≥ 0**; margin-up + revenue-down (Louvre: CM1/order +30% while struct −$4.6K) is NOT a scale signal — it renders as "efficiency/mix shift — investigate pricing/TR", separate action class.
5. **B4 dual gate** (abs $ floor AND sticky-gainer-or-B2↑): entry no longer depends on the week's distribution shape.
6. **Sub-Pro erosion sweep (monthly companion):** validated — caught Madame Tussauds NY (609→78 $/wk), Parag's exact CE, which the weekly buckets structurally cannot see once spend stops. Plus Bernina Express, Baseball-NY.
7. Near-threshold gray zone: borderline flapping observed (Immersive Theatre B2 at exactly −25% between pulls) — render "N CEs within 5pp/5% of triggers" count.

## 13. Coverage lenses — known gaps and their disposition (added 2026-07-07, reaffirmed post v2-baseline redo)

**Into v1:**
1. **Channel cut** (#1 blind spot): flows + deep-dives decompose by paid/organic/other (`ga_contribution_pct`, `sum_organic_session_order_value`, attribution model). Organic-led losses route to [SEO/Growth], not [Perf]. Restores the dropped "Organic vs Paid" section. Also gives organic-only CEs a diagnostic home.
2. **Supply/funnel wiring**: CR/OSR/availability columns into B1 ops-arm + Top-CEs strip (`int_ce_weekly_funnel`). The France heat-wave week shows ROI symptoms without this; the Italy report's best catches were all this class.
3. **Events/seasonality registry** — upgraded role: not just header annotation ("this week contained Jul 4") but **baseline selection input**: blend by default, holiday-aligned single-LY-week when a major event is in-window (blending across a holiday dilutes the holiday week's own expectation). Registry = public/school holidays by origin+destination + one-offs; always WebSearch-verify dates.
4. **TGID mini-bridge** in deep-dive cards (reuse old generator) + single-vendor-concentration flag. CE-flat can mask top-TGID swap — same masking logic, one grain lower.
5. **Zero-revenue transition flag** ($3K→$0 is categorically different from −30%).
6. **Tracking/platform-health gate** + **cross-market concordance meta-gate**: market-wide metric shift beyond historical bounds → "verify tracking first"; all markets emitting the same week-type → "verify methodology/platform before narrating" (the v1-baseline incident is the case study).

**Into v1.1:**
7. **Forward-bookings lens** — the tie-breaker for "under-ramping" verdicts: forward-booked revenue for next 1–2 weeks vs LY same point (fct_bookings experience dates). Under-ramping + forward book healthy = lead-time shift; + forward book down = real demand problem. Makes Jacopo-style lead-time analysis systematic.
8. **Origin-geo/language paid cut** (campaign_language × campaign_targeting_location): cross-CE one-liners ("German campaigns dropped market-wide").
9. **Outlook/base-effect line**: next-week expectation + Parag's easier-comps list.
10. **Unmanaged winners** surfacing (revenue growth, zero spend, no owner) below the 80%-gains threshold.

**Consciously excluded from weekly:** competitor price/assortment monitoring (monthly-grade, lagged data), customer repeat/LTV cuts (quarterly), standing LP2S/S2C/C2O sub-funnel sections (drill-down material behind cards).

## 14. Gap classification (3-market claim-by-claim tests: NA vs Pari's review · Italy vs FabriGPT+team · Oceania vs monthly bot+team, 2026-07-08)

**Headline: across ~40 ground-truth claims in 3 markets, the bucket set never failed to DETECT a money-mechanics issue. No missing bucket found. The gaps are ~15% bucket thresholds, ~20% framework glue, ~65% beyond-bucket attachments.**

### Tier 1 — In-bucket (threshold-level, small)
1. B4 gate misses "loading" CEs improving through 110% w/ rising CVR (Veiled Christ) → **🔄 LOADING arm DRAFTED 2026-07-09 (§5 B4 lane c), [CONFIRM w/ perf]**.
2. Near-threshold blindness (Immersive Theatre −24.9% vs −25% gate = NA's #2 problem) → gray-zone counters **added to B1/B2 columns 2026-07-09**.
3. B2 driver split TR/AOV/CPC behind CM1-per-conv swings (Blue Grotto template) → **design closed 2026-07-09**: TR + RPC evidence + Shapley swing-driver column in B2.

### Tier 2 — Framework glue (selection/aggregation rules)
4. **Focus selector ranks across flows + buckets** — biggest structural losers (Vatican/Kennedy/Chicago) are often bucket-less; bucket-only ranking mis-prioritized 2 of 4 markets.
5. **Materiality floors scale to the GROUP, not the market** (Carowinds: market noise, Six Flags headline).
6. **Flows-per-group is framework-core** (5 of Pari's 10 review statements are group-level facts) — which groups = config; that the engine runs per group = contract.

### Tier 3 — Beyond the buckets (attachments; every "unexplained" bucket row had its cause sitting elsewhere)
7. **Pacing/goals join — unanimous #1** (Pari "hitting their numbers" · FabriGPT %RR-vs-plan per CE · Oceania "56% of gap = 3 CEs").
8. **Deliberate-action + constraints register** (GBR ROI crash = known commission expiry; Rottnest = API outage; NGV = supplier bidding restriction; tROAS phases; Merlin/Pilatus commission wins incoming).
9. **Availability/funnel join** (Beetlejuice & Bruny zero-inventory explain the losses; Hobbiton LIC→OSR; Titlis C2O; Colosseum CR).
10. Events registry + outlook (school holidays/Matariki — monthly already annotates; Wharf-6 closure = forward risk on our own B4 picks).
11. TGID sub-grain (Sphere inside Immersive; St. Peter's single-vendor TGID).
12. Tracker seeding for B5 (Vesuvius discount, MMP iterations happen weekly, unverified).
13. Channel cut (organic-led losses route nowhere) → **anchors interim-covered 2026-07-09** by the strip's channel-agnostic 🟡 trigger; full paid/organic split in flows stays v1.
14. **Metric-scope config (NEW)**: Italy excludes "new categories" from July — engine must share each market's scope or every number drifts from the team's.

**Build directive: stop iterating bucket logic (3 threshold tweaks aside). Value order voted by the markets: pacing → action/constraints register → availability/funnel → events/outlook.**

## 14b. Agent A/B test (blind free-form analyst vs bucket framework · NA week 2026-06-29 · run 2026-07-09)

Two parallel agents, mutually firewalled: a free-form analyst (raw BQ only, no bucket vocabulary — 19 claims) vs the finalized framework (full data layer + 29-item approximations log). Artifacts: `thoughts/shared/bucket-vs-freeform-test/` (freeform / bucket / alignment files).

**Scoreboard:** 12 caught · 2 overlay-only · 1 missed · 4 disagreements. **Zero detection failures on $-material CEs** — consistent with the 3-market headline. Overlay-only cases = 4 fresh confirmations of gap #4 (Chicago Cruises, the market's #1 structural loser at −$31K, has no bucket home; likewise ITLV, LV Shows, Hawaii Luaus).

**Bucket-side unique catch:** the inferred register (historized tROAS diffs) found the **Jun-23/24 broad tROAS raise (150→155–167, 19 campaigns, ~$32K/wk)** that plausibly explains the entire B1 cliff cluster (Kennedy −32pp, SUMMIT −33pp, High Roller −55pp, USO −35pp) and the B2 up-swing cluster. The free-form analyst, with identical data, diagnosed every CE independently and never saw it. Systematic beat intuition exactly where §12b cluster detection predicted. Corollary: free-form's price stories (Kennedy +15% price/guest Jul-1; High Roller TR 20→32% Jun-26) are **confounded** with the raise — arbitration items for Pari/perf, plus the Hawaii Luaus baseline flip (+48% raw WoW vs −$5.2K structural).

### New gaps from the A/B run
15. **TR evidence window masks mid-window jumps** (Tier 1): High Roller's +12pp TR step reads as −1.4pp on 4w-vs-prior-4w averaging → change-point window (last-7d vs pre-change baseline). The B4 guard still routed the action correctly — the evidence column failed, not the routing.
16. **B4 lane-a gate self-defeating after broad tROAS raises** (Tier 1) **[CONFIRM w/ perf]**: the Jun-23 raise put every sticky gainer "below target+margin" → 0 lane-a rows in a week with 4 fundable 125–137% ROI winners → gate vs market ROI constant or pre-raise tROAS for ~2wks.
17. **Strip health ignores pacing** (Tier 2): ITLV rendered 🟢 (single-week structural dip) at 59% July attainment, −$86K projected gap → add attainment <~70% as 🟡 trigger.
18. **B1 recommendation cascade non-exhaustive** (Tier 1, small): cliff-above-100% and 20–70 non-chronic rows match no branch → fell back to "Monitor"; add branches.
19. **Silent-exit blind spot** (Tier 1): a CE whose spend stops entirely never renders a B1 EXIT (ROI incomputable on sub-$50 weeks) → zero-SPEND transition flag (cousin of §13's zero-revenue flag).
20. **Price/guest evidence missing from B1/B2** (Tier 1): Kennedy's +15% price/guest step was invisible (TR stable — sell-price change); the framework's final word on the market's #1 leak was "Monitor" → price/guest Δ column next to TR.

**Also validated live:** #8 register (inference recovered most of its value — input-induced tags on 4 cliff rows), #12 tracker (B5 STARVED, 27 untracked tROAS changes found), #9 availability (Steamboat checkout drop undiagnosed, supply check n/a).

**Cross-cadence validation note:** Oceania confirmed the stock/flow law live — Scenic World (already-fallen) correctly appears monthly-only; Kuranda (monthly 39%-vs-plan 🔴 + weekly B4 241% ROI) resolves via the monthly tag into "scale to close the plan gap"; Sydney Whale contradiction row (top grower + CM2 burner) found identically by both cadences.

## 15. CE-level opportunity flag catalog
Full catalog (base 12 flags + 9 Slack-mined additions with evidence, lanes, data sources, phase fit): `thoughts/shared/weekly-opportunity-flags-slack-mined.md`. Detection architecture: RPC + CM1/order are the composite detectors; driver split (CVR/AOV/TR/CR) routes to lanes; `RPC < CPC` is the standing no-diagnosis-needed flag. Quarterly ritual: re-mine mkt channels for manually-flagged opportunity types the weekly doesn't yet automate.
