# Losing Money redesign — start here

> **SUPERSEDED 2026-08-03** — v2 is built and committed on this branch (C1–C4 criteria,
> Existing/New via prior-4Q Pro+, Sun–Sat weeks, weekly micro-rows + toggle, triage chips,
> actions backfill). Next session: `thoughts/shared/weekly-report-v1/HANDOFF-ping-and-sheet-export.md`.
> The plan below is the ORIGINAL pre-meeting design — historical context only.

Worktree: `worktree-losing-money` (off `main` @ dbb13fb). **Do NOT publish from here** — publish only from main.
Full spec + mockups: `thoughts/shared/weekly-report-v1/losing-money-redesign.md`, `losing-money-mockup.html`, `losing-money-ab.html`.

## The redesign in one line
Kill the 6 sub-lists + derived-field soup. Two states: **Bleeding** (CM2 < 0, +2-wk persistence) and
**Eroding** (CM2 positive but dropped vs its 4-wk average). Baseline = plain `AVERAGE(prior 4 weeks)`.
Show the metric **trends** (CM2·ROI·Spend·Clicks·CVR·CPC), not decoded deltas.

## Files, in order
1. **`scripts/weekly_report/buckets.py` → `losing_money()` (L133)** — the engine.
   - Replace bleeders/eroding/full_waste/paused/tracking_gap/recovered lists + `cm2_improve_pct`/
     `recovering`/`status` strings with the two-state split.
   - Baseline = `AVERAGE(cm2 prior 4 wks)`, current week excluded. Delta = W0 − avg.
   - Emit per row: `cm2_series` (already computed, just expose), `marginal_roi = ΔCM1/ΔSpend`,
     `wks_neg` (consecutive CM2<0). Keep `dominant_driver` (argmin — already there).
   - Flag off CM2-$ drop: ≤ −2000 🔴 · ≤ −1000 🟠 · else 🟢 (this is EROSION severity, not sign).
2. **`config.py`** — flag thresholds (−1000 / −2000), keep named/tunable.
3. **`template/report_template.html`** — the LM table. CSS ~L128/161; row render + action dropdown ~L671–682.
   **Display = LOCKED to `losing-money-mockup.html`** (sparkline version): one row per CE, every metric a
   sparkline + this-week value, split Bleeding/Eroding, "Show weekly numbers" toggle for exact figures.
   Minor build note: drop **CM1** (redundant with CM2+Spend) — the mockup still shows it.
4. **`export_flagged.py`** — emit the raw weekly series → kills Perf's manual sheet rebuild (the smoking gun).
5. **`fetch.py`** — SIS rank/budget-lost = net-new fetch. DEFER to a follow-up; don't block the redesign on it.

## Build / preview loop
```
python3 scripts/weekly_report/weekly_market_report.py italy --week 2026-07-13 --no-open
```
Italy has real bleeders (Vatican/Colosseum eroding, Ibiza-adjacent). Build → open the HTML → iterate.

## Open design decisions (decide before locking)
- Header framing: "Losing Money" vs **"Defend / CM2 at risk"** (Eroding CEs are still profitable).
- Display: sparkline / raw weekly grid / hybrid.
- Sort: |CM2 drop vs 4-wk avg| (analytical) vs WoW + persistence (Perf's execution lens) — carry both.

## Don't
- Don't fabricate SIS/headroom/suggested-action — not fetched yet.
- Don't touch the legacy `bucket_b1` reads blindly — `troas` map + cascade are still load-bearing (see memory `legacy-b1-cleanup`).
