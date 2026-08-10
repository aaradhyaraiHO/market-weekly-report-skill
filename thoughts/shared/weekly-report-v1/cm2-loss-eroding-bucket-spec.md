# Losing Money bucket — CM2-loss / Eroding redesign (spec)

**Status:** logic locked 2026-07-23 · validated NA + Italy · pending wiring into
`buckets.py` + `template/report_template.html`.
**Owner:** Aaradhya · **Reference implementation:** Shreyal's manual "ROI Alert 🚨"
posts on the market channels (Jul-21), reproduced by this engine within 1–4pp.

---

## 1. Why — the gap this closes

The current Losing Money bucket gates on **ROI(W0) < 100%**. It catches chronic
small losers but is **structurally blind to high-ROI CEs that shed large absolute
CM2**. Diagnostic run (all 10 markets, W0 2026-07-13): **78 CEs / ~$150k weekly CM2
decline sat above 100% ROI** and never surfaced — e.g. Vatican Museums (ROI 129%,
−$5.1k/wk), Niagara Falls (128%, −$3.8k), Antelope Canyon (118%, −$2.7k).

The fix completes a **state × direction** matrix — the current engine covered three
quadrants; **Eroding** fills the fourth:

|                    | Worsening                         | Improving                 |
|--------------------|-----------------------------------|---------------------------|
| **ROI < 100**      | **Bleeding** (existing)           | Recovering → recovered    |
| **ROI ≥ 100**      | **ERODING** ← *new*               | healthy → Scale-Up bucket |

**Principle preserved:** weekly = *change*, not state (see `bucket-architecture-v2.md`).
Bleeding is a state read; Eroding is a this-week change read. The bucket is the
**union** of both — additive, it never drops or alters the existing bleeding rows.

---

## 2. Basis & windows (consistent for every metric)

- **Basis:** Google-Search Paid only — `ads_campaign_stats`, `ad_platform='Google Ads'`,
  `campaign_advertising_channel_type='SEARCH'`. (Bing excluded — matches the report's
  "Paid ROI" decision, 2026-07-17.) **Must be noted in the alert/footnote:** dollar
  magnitudes run ~30% below all-paid CM2, so they won't tie exactly to Shreyal's
  all-paid numbers.
- **W0** = last completed week (report week).
- **Baseline** = trailing 4 weeks *before* W0 (**W-1…W-4**), current week EXCLUDED —
  the same "vs prior-4" convention already used across the report's Δ4w columns.
  Ratios pooled (Σ/Σ); levels mean-of-weekly.

### Field definitions (all Google-Search)
```
cm1_g   = Σ offline contribution margin (post-2025-09-01; calc fallback pre)
spend_g = Σ sum_spend
clicks_g= Σ count_clicks
conv_g  = Σ conversions (offline post-Sep; online fallback)
cm2_g   = cm1_g − spend_g
ROI     = 100 × cm1_g / spend_g
RPC     = cm1_g / clicks_g          (contribution per click)
CVR     = conv_g / clicks_g
Val/conv= cm1_g / conv_g
CPC     = spend_g / clicks_g
Identity (reconciles to CM2):  cm2/clk = RPC − CPC ;  RPC = CVR × Val/conv
```

---

## 3. Detection logic (LOCKED)

Two **test types**, each with exactly one definition — this is the consistency rule:
- **LEVEL test** ("am I unprofitable now?"): `ROI(W0) < 100%` — single week, absolute.
- **DROP test** ("did I get worse?"): everything measured **vs the 4-week average**.

```
FUNDED (both branches):  Σspend_g 4wk (W0…W-3)  >  $1,000
                         (sub-$1k bleeders → existing burn_line aggregate, unchanged)

BLEEDING (state) — precedence cascade, first match wins:
   full_waste    conv_g 4wk == 0                         (spend, 0 conversions = total loss)
   paused        spend_g(W0) == 0  (was funded 4wk)      (stopped this week → footnote)
   tracking_gap  ROI(W0) null with spend > 0             (CM1 feed gap → footnote, verify)
   bleeder       ROI(W0) < 100  AND  cm2_4w (Σ W0…W-3) ≤ −$200

ERODING (change) — new, additive, ANY ROI level:
   CM2 weekly decline ≥ $1,000
   where  decline = mean-weekly CM2(W-1…W-4) − CM2(W0)

FLAGGED = BLEEDING ∪ ERODING.   A CE tripping both is labelled by ROI level (→ §5).
```

**Windows differ by design** (document, don't unify):
- Bleeder material floor `cm2_4w` = Σ **including W0** (trailing state).
- Eroding baseline = mean **excluding W0** (before→after change).

---

## 4. Ranking — "CM2 lost /wk vs healthy"

One unified sort key = how far below its healthy baseline the CE's weekly CM2 sits:

| Row type | Healthy baseline | `CM2 lost /wk`               |
|----------|------------------|------------------------------|
| Bleeder  | breakeven ($0)   | `−CM2(W0)` (this week's loss) |
| Eroder   | own 4-wk avg     | `decline` (drop vs 4-wk avg)  |

Sort **descending by CM2 lost** (worst first). `full_waste` pinned to the top
(urgent — total loss). Both cases render as a **negative red** number — no positive
value ever appears in the loss column. This reproduces the old `/wk · 4w` format
exactly for bleeders while catching eroders.

---

## 5. Status taxonomy — ONE plain-word tag per row

The group/table conveys "these are losses"; the ROI column conveys the drop; so
Status stays a single word (no severity, duration, or "nature" chips — those were
tried and cut as clutter 2026-07-23):

| Tag           | Rule                                   | Chip     |
|---------------|----------------------------------------|----------|
| `Full waste`  | conv_g 4wk == 0                        | red      |
| `Bleeding`    | ROI(W0) < 100                          | red      |
| `Eroding`     | ROI(W0) ≥ 100                          | amber    |

- Duration (NEW/CHRONIC/weeks-bleeding) is **not** a status chip — it reads off the
  **CM2 trend sparkline** (long red run = chronic). Removed the cryptic "5w/4w" tags.
- **ESCALATING re-based & demoted:** the "ROI dropped > 30pp" idea is no longer a
  status. The actual drop is shown in the **Paid ROI column for every row**, measured
  consistently vs the 4-week average (not WoW). One drop definition, everywhere.
- **Recovering / recovered:** keep as the improving-direction states.
  - `Recovering` (green chip, still bleeding but healing, pushed to bottom of bleeders):
    still a bleeder (ROI(W0) < 100, cm2_4w ≤ −$200) but the weekly CM2 loss has
    at least halved vs the prior-3-week average.
    `improve% = (CM2(W0) − avg CM2[W-1,W-2,W-3]) / |avg CM2[W-1,W-2,W-3]| × 100`,
    computed only when that prior-3wk avg was negative; `Recovering` iff improve% ≥ 50
    (`RECOVER_CM2_IMPROVE_PCT = 50`; +100% = back to breakeven).
  - `recovered` (green footnote exit, not a row): `ROI(W0) ≥ 105` AND bled ≥ 2
    consecutive weeks immediately before W0 (`RECOVER_ROI = 105` — 5pp hysteresis so
    99↔101 doesn't flip; `RECOVER_MIN_BLEED = 2`).
- **No severity bands.** There is no CRITICAL/SEVERE/MODERATE tier — magnitude is
  conveyed solely by the ranking (worst-first) and the red `CM2 lost` dollar value.

---

## 6. Drivers — "where the loss is coming from" (reconciling)

Decompose the weekly CM2 change into four factors that **sum exactly** to it
(sequential swap, baseline→W0; verified residual $0.00):
```
Clicks   = (V_c − V_b)·(CVR_b·VPC_b − CPC_b)
CVR      = V_c·VPC_b·(CVR_c − CVR_b)
Val/conv = V_c·CVR_c·(VPC_c − VPC_b)
CPC      = −V_c·(CPC_c − CPC_b)
```
`dominant_driver` = the most-negative factor. Rendered by **highlighting that
factor's existing column cell** (reuse the template's `.fxdom` root-cause highlight)
— no separate driver column. RPC displayed as the contribution-per-click headline;
`RPC = CVR × Val/conv`, `cm2/clk = RPC − CPC`.

---

## 7. Column layout + tooltips (GOOD PRACTICE — carry forward verbatim)

Table lives in **§4 Diagnostic buckets → 🛡️ Losing Money** collapsible `_bucketBlock`
(`stat = N CEs`, `val = −$X/wk`, `?`-tooltip). Sticky first column, sticky header,
value-over-delta cells (`.lmv` / `.lmd` gp/gn/mut), rounded `.tablewrap` card — all
existing components, unchanged. **Every column keeps a `title=` tooltip** (existing
convention). Row order: Full waste (pinned) → rest by CM2 lost desc.

| # | Column | `title=` tooltip (hover) |
|---|--------|--------------------------|
| 1 | Combined Entity (stick) | *(none — name + [id] + New/Existing chip + season tag)* |
| 2 | Status | `Bleeding = ROI < 100% (losing money) · Eroding = ROI ≥ 100% but CM2 dropping vs its 4-week average · Full waste = spend with 0 conversions.` |
| 3 | Paid ROI `vs 4wk` | `Google-Search Paid ROI. Δ = last week vs the trailing-4-week average, in pp.` |
| 4 | CM2 lost `/wk · 4w` | `CM2 lost per week vs a healthy baseline. Bleeder: this week's CM2 loss (baseline = breakeven) + 4-week accumulated loss. Eroder: the drop vs its own 4-week average. Table is sorted by this.` |
| 5 | Spend `Δ4w` | `Weekly Google-Search spend. Δ vs the prior-4-week average weekly spend — green = pulled back, red = ramping.` |
| 6 | RPC `Δ4w` | `Contribution revenue-per-click (cm1/click). Δ vs 4-week avg. Highlighted cell = dominant driver of the CM2 loss. RPC = CVR × Val/conv.` |
| 7 | CVR `Δ4w` | `Paid conversion rate (conversions/click). Δ vs 4-week avg.` |
| 8 | CPC `Δ4w` | `Cost per click. Δ vs 4-week avg — up is bad.` |
| 9 | Clicks `Δ4w` | `Google-Search clicks — context/volume (neutral). Δ vs 4-week avg.` |
| 10 | CM2 trend | `Weekly CM2 (CM1 − spend) over ~10–12 weeks; dashed line = breakeven. Duration of red = how chronic.` |
| 11 | Action | `Your call, saved per week: Pause / Scale down / Intentional.` |

### How-to block (`.lm-howto`) — verbatim
> **How to read:** every CE losing CM2 this week, **worst first**. **CM2 lost** = how
> much weekly CM2 dropped vs its healthy baseline (bleeders vs breakeven, eroders vs
> their own 4-week average) — the ranking signal. **Status:** Bleeding (ROI < 100%) ·
> Eroding (ROI ≥ 100% but dropping) · Full waste (spend, 0 conversions). **Paid ROI**
> shows last week and its drop vs the 4-week average. The **highlighted column** is the
> dominant driver of the loss. The **CM2 trend** sparkline shows how long it's been
> negative (chronic = long red).

### Footnotes (below table, existing `.lm-legend` style)
- `⏸ N paused (was funded 4w): <names + $4w>` — spend stopped; confirm intentional.
- `⚠ N null-ROI feed gap: <names>` — spending & converting, CM1 didn't populate; verify tracking, not waste.
- `✅ N recovered: <names + ROI + was-bleeding wks>` — exited the bleed.
- Basis note: *Google-Search Paid only (Bing excluded) — magnitudes ~30% below all-paid; same window & definition as the manual ROI-Alert on the market channel.*

---

## 8. Constants (add to `buckets.py`)
```
BLEED_ROI          = 100.0     # existing
BLEED_SPEND4W      = 1000.0    # existing
BLEED_CM2_FLOOR_4W = -200.0    # existing material-bleed floor
ERODE_CM2_DECLINE  = 1000.0    # NEW — weekly CM2 decline gate
ESCALATE_ROI_DROP  = 30.0      # RE-BASED: pp vs 4wk-avg (was WoW)
RECOVER_ROI, RECOVER_MIN_BLEED, RECOVER_CM2_IMPROVE_PCT = 105.0, 2, 50.0   # existing
# NO severity bands — magnitude = ranking + the CM2-lost dollar value.
```

---

## 9. Validation gates (must hold before ship)
1. **Driver reconciliation:** Σ(Clicks+CVR+Val/conv+CPC) = CM2(W0) − CM2(4wk-avg-wk),
   |residual| < $1 at full precision. *(passed: $0.00 across 65 rows.)*
2. **Shreyal reproduction:** ROI 4wk→wk matches her Jul-21 posts within ~4pp; ≥ 8/11
   in-scope CEs reproduced. *(passed: 8/11; 3 misses are $883–$952, just under the
   $1k gate on the Google-only basis.)*
3. **Metric identity:** `RPC ≈ CVR × Val/conv` per row. *(passed.)*
4. **NA cross-run:** cross-market engine reproduces the NA-only script (13 flagged:
   6 eroding + 7 bleeding-family). *(passed.)*
5. **No regression:** the existing bleeding/full_waste/paused/recovered sets are
   byte-identical to current production (eroding is purely additive, 0 overlap on NA).

---

## 10. Implementation notes
- **`buckets.py::losing_money()`** — add the eroding branch after the bleeder test;
  compute `decline`, `lost_wk`, per-row driver impacts; re-base ESCALATING to 4wk-avg;
  set `status ∈ {bleeding, eroding, full_waste}` by ROI level; return `lost_wk` as the
  sort key. Keep `recovered`/`paused`/`tracking_gap`/`burn_line` outputs unchanged.
- **`template/report_template.html`** — extend the `lm*` renderers: `lmCm2` → the
  `CM2 lost` cell (adaptive bleeder/eroder, never positive); status = 3-word chip;
  drop the severity/week sublines; keep Action dropdown; apply `.fxdom` to the
  dominant driver cell; update `lmHead` tooltips (§7) and `.lm-howto` (§7).
- **Reference mock-ups:** `scripts/weekly_report/docs/{north-america,italy}-cm2-bucket-mockup.html`
  (generator: `na_mockup_final.py <Market> [week]`).
- **Diagnostics kept:** `diag_cm2_final.py` (cross-market + verification),
  `diag_na_validate.py` (current-vs-new), `diag_cm2_drop.py` (the exploratory sheet).

---

## 11. Decisions made (don't re-litigate)
- Rank by **CM2 dollars**, not ROI-drop pp (a 2pp drop worth $10k beats a 100pp drop worth $100).
- **Relative-vs-absolute:** the eroding gate is an **absolute $1k**, but the *sort* is
  "CM2 lost vs healthy" which is inherently CE-relative; small markets naturally show
  fewer/smaller rows rather than being penalised by a % rule. (Considered a %-drop
  gate; rejected — a −12% drop on a $165k-spend CE like Vatican is still $5k, must catch.)
- **Google-Search only** (report-consistent), not all-paid — noted in the alert.
- **ESCALATING → 4wk-avg** basis (consistency with eroding + Shreyal), demoted from a
  status chip to just the ROI-column delta.
- Status = **one word**; duration → sparkline. No Efficiency/Scale/Mixed, **no
  severity tier at all** (CRITICAL/SEVERE/MODERATE were an invented threshold, cut),
  no week-count chips.

## 12. Open / parked
- **Thin-margin watchlist** (ROI ~100–110% on material spend, e.g. Blue Lagoon Malta
  ROI 101%, stable) — deliberately NOT in this bucket (it's neither a loss nor a
  decline). Parked as a possible separate low-threshold view; do not dilute Losing Money.
- Spend Δ colour uses the bleeder convention (up = red) on **all** rows incl. eroders
  (option 1, simplicity); revisit only if eroder false-alarms appear.
