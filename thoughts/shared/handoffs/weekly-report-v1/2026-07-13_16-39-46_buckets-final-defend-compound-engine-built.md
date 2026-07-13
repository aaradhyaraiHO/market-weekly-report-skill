# Handoff — Weekly Report Buckets: FINAL Defend/Compound engine built + rendered

**Date:** 2026-07-13 · **Worktree:** `.claude/worktrees/diagnostic` · **All paths below relative to** `scripts/weekly_report/`

## TL;DR
The weekly bucket set was **reset** from an over-engineered decomposition design back to **Aditya's B1/B2/B4 organized under Defend/Compound**, then built as a production engine (`buckets.py`), wired into the pipeline, stress-tested on 3 markets (0 anomalies), and rendered to self-contained HTML. Core bucket logic + metrics are **done and validated**. Open work is a few design calls, two data-dependency wirings, and the report shell (§0/overlays/B5).

## The FINAL bucket structure
```
DEFEND (top losers)                      COMPOUND (top gainers)
  • Losing Money (CM2 bleed)               • Scale-Up (ROI≥155% ≥3-of-4wk, not-cliffed)
  • Fluctuations ↓ (−ve seasonality)       • Fluctuations ↑ (+ve seasonality)
LIFECYCLE (separate group)
  • New CEs (New Pro+ + on-run-rate-to-Pro)   • Iteration (MMP: no-traction / traction-no-MMP)
PARKED: Prepurchase (supply lever) · Seasonality info-tag  (both need Aditya's levers sheet)
```
- **Losing Money** REPLACES the old "B1 / ROI-CM2 Movement." Movement (NEW/CLIFF/ESCALATION/EXIT) is now a **Status column**, not a separate bucket. Proven: B1-losers ⊂ current bleeders with 0 exceptions across 3 markets; B1 was ~half recoveries.
- **Fluctuations** = ONE table (CM1/conv · RPC · CVR daily-POF swings), split by direction into Defend↓/Compound↑. Detection matches the linked POF spec sheet exactly (CM1/conv detects, RPC = evidence).

## Key files
- **`buckets.py`** — FINAL production engine. `build_buckets(snap)` → `{defend:{losing_money, seasonality_down}, compound:{scale_up, seasonality_up}, lifecycle:{new_ces, iteration}}`. Pure; runs on a raw snapshot. **This is the source of truth.**
- **`build_snapshot.py`** — pipeline (`build_market`); now emits `snapshot["buckets_final"] = buckets.build_buckets(snapshot)` right before return (verified live from BQ).
- **`render_report.py`** — self-contained HTML renderer → `docs/weekly-report-<market>.html` (NA/IT/OC generated).
- **`stress_test.py`** — 3-market validation harness (scorecard + anomaly flags).
- `experiment.py` — the earlier v3–v11 exploration (decomposition/Slipping/Funnel-Bleed). **Superseded by buckets.py**; keep for reference only.
- Cached raw snapshots: **`/tmp/{na,it,oc}_snap.pkl`** (build_buckets is pure — runs on these, no BQ needed).

## Locked decisions / thresholds (in buckets.py constants)
- Losing Money: `ROI<100 & spend_4w>$1k`; rank by CM2 bled `spend×(ROI/100−1)`; Status NEW(1w)/Nw/CHRONIC(≥6w)/ESCALATING(Δ<−30pp); RECOVERED = sustained ≥2wk bleed → now >105.
- Fluctuations: ROI gate **>140 (+ve) / <120 (−ve)**; existing CEs only; cause-aware recommendation — `unexplained→investigate`, `input-induced→verify (bid change)`, `supply-linked→route Ops`, else `±15%/7d`.
- Scale-Up: **ROI≥155% in ≥3-of-4 weeks**, not cliffed (−30pp WoW), tROAS clamped [80,400]; rank by est incremental/wk; pp>+20 → +ve seasonality flag.
- Gain floor = `max($500, 0.5% trailing-4wk mkt wk rev)`.

## Table refinements made (this session)
- **Losing Money:** time-window labels + legend; `cost`→**Spend/wk** + added **Spend 4w**; swapped `RPC vs cat` → **RPC vs 4w** (yield decay, cliff<−25%/gradual−10..−25 coloring) + added **CPC** (cost side of ROI); Tier · YoY columns; Suppressed line (funded null-ROI CEs — data-check); Long-tail burn line.
- **Fluctuations/Seasonality:** merged Signal+Swing → **`Swing (vs 28d)` = "RPC ↓81%"**; **Δrev driver** = full revenue decomposition (traffic+CVR/AOV/CR/TR), direction-aligned, $ (e.g. `↓ CVR $4.4k`); dropped `RPC vs cat` (structural, wrong lens for a swing); added Spend/wk; component levels CVR·CR·AOV·TR; cause-aware recommendation.
- **Scale-Up:** keeps `RPC vs cat` (structural headroom — correct here); tROAS/pp-gap.

## OPEN — decisions (user's call)
1. **Bucket name:** recommended **Seasonality → "Fluctuations"** (title=detection; seasonality=the recommendation). NOT yet applied — pending confirm.
2. **Component change display:** show each of CVR/CR/AOV/TR with its **Δ$** (Shapley) so the cell shows *change* not just levels — recommended, would make the standalone Δrev-driver column redundant (fold in, bold the top). NOT applied.
3. **Scale-Up strictness:** ≥3-of-4 ≥155 locked (2/2/3 per mkt); could loosen to 4wk-aggregate (4–6). 
4. **B3 "Losing Ground — On Pace"** (forecasting bucket, Pro+ projected to fall a band) — in or out? NOT built.
5. **Availability as a standalone trigger** — §3 says "OR availability changes"; currently availability is only a `cause` tag (supply-linked), not an entry path. Partial.
6. B2 "keep all columns" (Aditya) vs prune (Aaradhya) — leaning prune; mostly done.

## OPEN — build / data
- **New Pro+ true 4-quarter gate** — currently a **12-week proxy** ("was below Pro earlier in window"); over-flags (OC 24/25 graduated). Needs band-explorer quarterly history (`~/analytics/scripts/band_dashboards/`, `ce_buckets/bands.py`).
- **Report shell** — §0 Week Header/themes, overlays (Top CEs, Gap/Pacing), Standing Tables (no-bid campaigns), **B5 Action Verdicts** — not built (all specced in Aditya's sheet).
- **Diagnostic lens** (factor movers, read-only) — built in `render_lens.py` earlier, not integrated into the main report.
- **PP + seasonality info-tag** — blocked on Aditya's "Seasonality & Levers" sheet.

## Data sources & flags
- MMP (Iteration): `~/analytics/scripts/ce_buckets/sources.py::fetch_mmp_sheet()` → "MMP Execution Data" gsheet — **works** (475 rows; matched by numeric ce_id prefix). Guarded in `_mmp_map` (falls back to {} on failure).
- Category benchmarks: computed intra-market from the snapshot (coarse for small cats; firmer = data add).
- **Data-quality issues surfaced (flag to whoever owns bucket_b1/CM1 feed):** null-ROI funded CEs (Madame Tussauds ×2, Boston Duck, Dorney Park — spending, no CM1/conversions → suppressed line); bad tROAS source values (Gornergrat 1062 → clamped).

## Stress-test result (NA / IT / OC, 0 anomalies)
Losing Money 13/14/14 bleeders · Fluctuations ↓13↑12 / ↓16↑13 / ↓9↑9 · Scale-Up 2/2/3 · New CEs 37/20/25 · Iteration 43/40/39.

## Reference sheets
- **Output + locked spec:** docs.google.com/spreadsheets/d/1oLcLt7WMVhO7zwlRlZGhoYYClySYJkkUBC7Cpyqk1bg (tabs: FINAL — Locked Spec 07-13, Buckets & Metrics, RPC & Click Landing, Diagnostic Lens, Why).
- **Aditya's finalized spec (B1–B5, overlays, shared anatomy):** docs.google.com/spreadsheets/d/17xVzKYKb8hfSYVNoj_Sf6lEV_C_LTFPa-GICFqzHoFY
- **POF detection spec (the Fluctuations engine):** docs.google.com/spreadsheets/d/1CR84MV1vTQoFfgWWdZkPXEoVFzSTfXL8mp_OpJRCNzY

## How to run
```bash
cd .../scripts/weekly_report
# refresh a cached snapshot from BQ (bq/gcloud ADC auth required):
python3 -c "import datetime,build_snapshot,pickle; pickle.dump(build_snapshot.build_market('north_america',datetime.date(2026,6,29),with_availability=False),open('/tmp/na_snap.pkl','wb'))"
python3 buckets.py /tmp/na_snap.pkl          # engine summary
python3 render_report.py /tmp/na_snap.pkl     # → docs/weekly-report-north-america.html
python3 stress_test.py /tmp/na_snap.pkl       # 3-market validation
```

## Recommended next step
Apply the two pending display calls (rename → Fluctuations; component Δ$ / fold driver), then pick one build item — **New Pro+ band-explorer wiring** is the highest-value (fixes the one non-proxy gap in a live bucket). The report shell (B5/overlays) is the biggest remaining chunk.

## Memory
Design rationale + locked decisions persisted at `~/.claude/projects/-Users-aaradhyarai-market-weekly-report-skill/memory/weekly-bucket-redesign-v2.md`.
