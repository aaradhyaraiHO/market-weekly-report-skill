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
- Current NA counts: **1 full-waste · 7 bleeders · 4 paused · 0 feed-gap · 16 sub-$1k burn.** (The 4
  "feed-gap" CEs from the first pass are all `spend_wk==0` → **paused**, not feed-gapped — see addendum.)

## Status: MOCKUP FINAL ✅ — cleared to build
Aaradhya signed off (2026-07-16). ROI = dual WoW·4w locked. No open design decisions on Losing Money.

## Review addendum (2026-07-16) — spend Δ4w base LOCKED
Reviewed the mockup's per-metric delta bases against the committed source (`bcfef89`). Finding:
- All five ratio/volume Δ columns (ROI, RPC, CPC, Clicks, TR) use `vs_prior` with base = **`wk[-5:-1]`**
  (prior 4 weeks, **current week excluded**).
- **Spend was the lone exception** — it used `mean(wk[-4:])` (prior 4 weeks **including** the current
  week), a self-referential base that dampens ramps. Verified on NA: Seattle Whale reads +60% with the
  old base vs **+166%** with the prior-4 base; Schlitterbahn +89% → **+239%**.

**Decisions (locked):**
1. **Spend Δ4w base → `wk[-5:-1]`** (prior-4, current-excluded), matching the other five. This is a
   correctness fix, not a preference — the mockup was internally inconsistent. Applied to `lm_mockup.py`.
2. **Spend stays %-only (Δ4w), no 4-week $ total.** The original report showed `(4w $10.6K)` (a cumulative
   sum); the redesign intentionally replaced it with the ramp % because **CM2 bleed already carries the
   4-week dollars burned** (`−$2.6K 4w`) — a spend total would be redundant. Keep spend = ramp signal.
3. **Null weeks in the spend base are skipped** (mean ignores `None`), i.e. "vs weeks it actually spent."
   Schlitterbahn prior-4 `[null, null, $146, $623]` → base $384 → +239% (not +578% if nulls counted as $0).
   Consistent with how `mean()` treats every other metric. Locked as-is.

Also applied to the mockup in this review (kept — low-risk, no layout change): **tier chip** (Hero/Pro) on
the CE cell, and the **PAUSED vs tracking-gap split** — `spend_wk==0` → "paused, confirm intentional" (the
4 NA null-ROI CEs are all paused, not feed-gapped); only `spend>0 & roi None` → "verify tracking" (0 this
week). When wiring §A, carry these into `buckets.py`.

**DELIBERATELY NOT changing (keep simple / habituated — do not "fix" these):**
- **All Δ4w stay mean-of-weekly, NOT spend-weighted pooled.** The whole existing report (live `rpc_vs_4w`)
  already uses mean-of-weekly; switching one bucket to pooled would be the only place doing different math
  and would read inconsistently. Accepted cost: on a few low/uneven-spend CEs (e.g. Seattle Whale) Δ4w can
  look steeper than a pooled view; the `ESCALATING` WoW-cliff chip is the acute signal, Δ4w is context.
- **`full_waste` stays `ad_conversions_4w == 0`** ("spend, 0 paid conversions" — one clear mental model).
  Not adding revenue/orders branches. Latent edge (documented, not fixed): a CE with 0 paid conversions but
  organic orders would still read FULL WASTE; no such case in current data (Mendenhall is orders=0/rev=0).
- **Thresholds are conventions, not calibrated** ($1k/4wk, −$200, ROI 100 = true breakeven, 30pp cliff,
  6w chronic, ramp >25%+$100). Verified `roi_pct == 100·cm1/spend`, so the gate and the CM2 figures share
  one profit definition and `/wk` matches the 4w sum exactly on all current bleeders.

## BUILD STATUS — §A + §B DONE ✅ (2026-07-16)
Both wired and verified. Not yet committed.
- **§A `buckets.py::losing_money`** — rewritten: prior-4 base on every Δ4w, three-way split
  (full_waste/paused/tracking_gap), new fields, `cm2_bleed_wk` hardened to direct `cm1−spend`, metric
  bundle shared so full_waste renders the full row, `_active` gate moved to burn-only. Verified: 36
  market×week sweep states + 9 adversarial fuzz CEs → 0 violations, 0 NaN, NA counts 1·7·4·0·1·16.
- **§B `report_template.html` renderBleeders** — rebuilt to the mockup layout: value-over-Δ cells
  (`lmVD`/`lmRoi`/`lmSpend`), dual-ROI, CM2 `/wk·4w`, spend ramp ↑, Clicks neutral, `$` RPC/CPC, new
  `cm2Spark()` sparkline (zero line + per-point hover), full-waste red band + `FULL WASTE` tag,
  how-to + status legend, paused/feed-gap/burn footnotes (burn hover = names). Added `.lm*` CSS.
- **Verify method (reproducible):** splice `losing_money()` output into a cached snapshot's
  `buckets_final.defend`, `python3 render.py <snap>`, then headless Chrome `--dump-dom` to confirm the
  built DOM. Ran NA (full table faithful to mockup), IT (9 bleeders, no waste band), OC (paused footnote).
  `build_snapshot.py:957` calls `build_buckets`, so a real pipeline run regenerates the new schema — the
  cached snapshots' baked `buckets_final` is stale (old `suppressed`) and only used for this splice-test.
- **Remaining:** regenerate the real market JSONs via the live pipeline + commit. `render.py` still reads
  `LM.suppressed` nowhere now; old key is gone from the engine.

## ORIGINAL PLAN (for reference — both sections now done)
Two files:

**A. `buckets.py::losing_money`** — add per-bleeder fields (all computable from `ce["weekly"]`).
**Every Δ4w base = `wk[-5:-1]` (prior-4, current EXCLUDED)** — see Review addendum. No metric uses `wk[-4:]`.
- `cm2_bleed_4w` = Σ(cm1−spend) last 4wk · `spend_dvs4` (spend vs **prior-4wk** avg %, nulls skipped) ·
  `spend_wow` (+ ramp when >25)
- `cpc_v4`, `clicks_v4`, `tr_v4` (vs prior-4wk avg; TR in pp) — RPC vs4w already exists (`rpc_vs_4w`)
- ROI: `roi_dpp` (WoW pp — already in the engine) **and** `roi_v4` (vs-prior-4wk-avg pp — new) for the dual cell
- `cm2_series` (weekly CM1−spend, last 12) for the sparkline
- Spend = **%-only (Δ4w), no 4-week $ total** (decision #2). `spend_4w` may still be computed for the
  full-waste "$X (4w)" sub-line, but bleeders render the % only.
- Reclassify: split `suppressed` into **full_waste** (`ad_conversions_4w==0`), **paused**
  (`spend_wk==0`), and **tracking_gap** (`roi None & spend_wk>0`); add `orders_4w`/`adconv_4w`.
  Order matters: full_waste → paused → tracking_gap → bleeder. Apply the `cm2_4w ≤ −$200` floor.
- Add CE names to `burn_line` (for the hover).
- Add `tier` chip field (Hero/Pro) to the row.
- Drop `yoy` from the row (or just stop rendering it).

**B. template `renderBleeders`** (in `report_template.html`) — rebuild to the mockup layout: value-over-Δ
cells, ROI "current · was X%", CM2 /wk+4w, spend ramp ↑, Clicks neutral, `$` RPC, CM2-trend sparkline with
per-point hover, full-waste top band + `FULL WASTE` tag, how-to-read + status legend, paused + feed-gap +
burn footnotes (burn hover = full names). Reuse the mockup's helpers (`vd`, `roi_cell2`, `spend_cell`, `spark`)
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
