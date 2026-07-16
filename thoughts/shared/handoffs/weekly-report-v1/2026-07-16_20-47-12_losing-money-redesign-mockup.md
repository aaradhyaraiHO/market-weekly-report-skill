# Handoff — Losing Money cohort redesign (MOCKUP, ready to wire)

**Date:** 2026-07-16 · **Worktree:** `.claude/worktrees/diagnostic` · **Paths relative to** `scripts/weekly_report/` unless noted

## TL;DR
Redesigned the **Losing Money** bucket (DEFEND) from Aaradhya's 10-point brief, iterated live as a
standalone **mockup** with real NA data. Design is settled; **not yet wired into the real report**.
Next step = port the mockup into `buckets.py` (new fields) + the template's `renderBleeders`.

- **Mockup (open this):** `thoughts/shared/weekly-report-v1/losing-money-mockup.html`
- **Generator (persisted from /tmp):** `scripts/weekly_report/lm_mockup.py` — reads
  `.cache/weekly_report/snapshot_north_america_2026-06-29.json`, writes the mockup HTML. Regenerate:
  `python3 scripts/weekly_report/lm_mockup.py` then hard-refresh Chrome.
- Uses the report's real tokens (Figtree `@import`, `--ink/--green/--red/--amber/--rule`), so it
  matches the live report visually.

## The redesigned Losing Money table (final mockup spec)
Ranked worst-first by **4-week CM2 bled**. Columns (value-over-delta, image-#24 style: value bold on
top, colored Δ below):

| Col | Content | Δ basis / notes |
|---|---|---|
| Combined Entity | name · `[id]` · season chip (☀/❄/◐, from seasonality_llm) | — |
| Status | chip + "Nw bleeding" sub | NEW(1w) / 2–5w / CHRONIC(≥6w) / ESCALATING(ROI −30pp WoW, orthogonal) |
| **Paid ROI** | **current + BOTH deltas** — `WoW` (vs last week, acute) and `Δ4w` (vs 4-week avg, structural), each **labeled in-cell** | e.g. `71%` / `−23pp WoW` / `−84pp 4w`. This is the ONLY metric with two deltas (acute + structural tell different stories); all others single `Δ4w`. FINAL. |
| CM2 bleed | `−$964/wk` + `−$2.6K 4w` | weekly rate + 4-week total (= Σ weekly CM1−spend) |
| Spend | value + Δ4w · **↑ amber flag** if WoW jump >25% (`SPEND_RAMP`) | up = bad (red); ramp flag = acute over-investment on a bleeder |
| RPC | `$` value + Δ4w | up = good (green). **$ prefix** (dollars/click) |
| CPC | `$` value + Δ4w | up = bad (red) |
| Clicks | value + Δ4w | **NEUTRAL gray** — volume isn't good/bad on a bleeder (a +223% on a full-waste CE must not read green) |
| TR% | value + Δ4w (pp) | up = good (green) |
| CM2 trend 12w | sparkline of weekly CM1−spend, dashed zero line, **per-point hover** (date + CM2) | 12 weeks (matches snapshot); green/red by direction |

**Above the table:** a **"How to read (BGM)"** line + a **status legend** (one-liner per tag). Guideline
text baked in: *"3–4 weeks bleeding with no recovery lever → scale down within the week."*

**Footnotes (below):**
- `✅ N recovered` (sustained ≥2wk bleed → now >105%).
- `⚠ N null-ROI — CM1 feed gap (has bookings, verify): name (K orders, $X 4w)` — see data note below.
- `+ N sub-$1k CEs bleeding −$X/wk` — **hover shows the full list** (all names, no "+N more").

## Locked design decisions (with rationale)
1. **Δ basis:** every metric Δ is **vs the prior-4-week average** (`Δ4w`), labeled in the header. **ROI is
   the exception → shows BOTH `WoW` (vs last week) and `Δ4w` (vs 4-week avg)**, labeled in-cell. CM2 uses
   `/wk` (rate) + `4w` (total). Clarified for the record: `/wk` = a *rate* (per-week amount of a flow —
   only for CM2/Spend); `WoW` = a *change* (this week vs last week). ROI is a ratio so it has no `/wk` —
   only WoW / 4w / level. Every "week" label is now explicit, no bare ambiguous deltas.
2. **Delta coloring = favorability for a *losing* CE:** RPC/TR up=green; CPC/Spend up=red; **Clicks neutral**;
   a delta that rounds to 0 → neutral gray "0pp" (no sign, no color — fixed the "−0pp red" bug).
3. **Materiality floor:** keep a bleeder only if **4-week CM2 bled ≤ −$200** (≈ $50/wk). Data showed 2–4
   near-breakeven noise rows/market (e.g. Country Music Hall of Fame −$5/wk) that this removes. Applied to
   the 4-wk bleed, NOT single week (single week is volatile).
4. **Dropped YoY column** (state metric, noise in a change/action table).
5. **Sparkline → CM2 trend** (was revenue); 12w; per-point hover.

## Data facts learned (important — the null-ROI reframe)
- **"null-ROI" is NOT waste — it's a current-week CM1 feed gap.** Verified: the 4 null-ROI NA CEs
  (Madame Tussauds NY/Orlando, Boston Duck, Dorney Park) all have real orders + 4-wk CM1, but their
  **latest week `cm1=0`** → ROI computes null. They're converting, just feed-lagged. → footnote
  "verify tracking", NOT waste. (Before, all null-ROI were lumped in a "suppressed" footnote; the first
  mockup wrongly tried to call them "full waste".)
- **True FULL WASTE = funded CE (spend_4w>$1k) with `ad_conversions_4w == 0`** — spend, zero paid
  conversions = total loss. It shows as **ROI ≈ 0%** (e.g. Mendenhall Glacier $1,069, 0 conv), NOT null.
  Detected by conversions==0, surfaced at the top with a red `FULL WASTE` tag.
- So the classification (funded, spend_4w>$1k):
  `adconv4==0 → FULL WASTE` ; else `roi is None → tracking gap (footnote)` ; else `roi<100 & cm2_4w≤−200 → bleeder`.
- Current NA counts: **1 full-waste · 7 bleeders · 4 feed-gap · 16 sub-$1k burn.**

## Status: MOCKUP FINAL ✅ — cleared to build
Aaradhya signed off (2026-07-16). ROI = dual WoW·4w locked. No open design decisions on Losing Money.

## NEXT STEP — wire the mockup into the real report
Not started. Two files:

**A. `buckets.py::losing_money`** — add per-bleeder fields (all computable from `ce["weekly"]`):
- `cm2_bleed_4w` = Σ(cm1−spend) last 4wk · `spend_dvs4` (spend vs 4-wk avg %) · `spend_wow` (+ ramp when >25)
- `cpc_v4`, `clicks_v4`, `tr_v4` (vs prior-4wk avg; TR in pp) — RPC vs4w already exists (`rpc_vs_4w`)
- ROI: `roi_dpp` (WoW pp — already in the engine) **and** `roi_v4` (vs-4wk-avg pp — new) for the dual cell
- `cm2_series` (weekly CM1−spend, last 12) for the sparkline
- Reclassify: split `suppressed` into **full_waste** (`ad_conversions_4w==0`) vs **tracking_gap**
  (`roi None & ad_conversions_4w>0`); add `orders_4w`/`adconv_4w`. Apply the `cm2_4w ≤ −$200` floor.
- Add CE names to `burn_line` (for the hover).
- Drop `yoy` from the row (or just stop rendering it).

**B. template `renderBleeders`** (in `report_template.html`) — rebuild to the mockup layout: value-over-Δ
cells, ROI "current · was X%", CM2 /wk+4w, spend ramp ↑, Clicks neutral, `$` RPC, CM2-trend sparkline with
per-point hover, full-waste top band + `FULL WASTE` tag, how-to-read + status legend, feed-gap + burn
footnotes (burn hover = full names). Reuse the mockup's helpers (`vd`, `roi_cell2`, `spend_cell`, `spark`)
— they're all in `lm_mockup.py`.
- Then regenerate JSON (`buckets.build_buckets` on the /tmp pkls → `build_snapshot._write`) + `render.py`.

## Branch / commit state
On `worktree-diagnostic`. Committed so far (recent): PP hardening + stale flag (`08e8656`, `8e51c9c`,
`4d3490a`), PP bucket (`ddd69d0`), seasonality module (`e1186a1`), Iteration reason-cascade (`89895d9`).
**Uncommitted:** `scripts/weekly_report/lm_mockup.py` (new, the generator) + the mockup HTML (gitignored
report dir). The Losing Money wiring is NOT committed (not built yet).

## Also-open (unrelated, parked)
- **Descale** bucket (validated, not built) — see memory `weekly-bucket-redesign-v2`.
- **Revoke the leaked API key** (deleting `~/.zshenv` line ≠ revoking).
- Handoff + `/weekly-buckets` command still reference the deleted `render_report.py`.
