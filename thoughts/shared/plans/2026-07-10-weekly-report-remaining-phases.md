# Weekly Market Report — Remaining Build Phases (frozen 2026-07-10)

**Status:** cascade DONE (ecc27ae2 + ee1bac09). This plan sequences everything left, per the usability debate (session 2026-07-10). One phase per fresh session; ledger `thoughts/ledgers/weekly-report-v1.md` is the resume point. All work in `wt-weekly-buckets` (single full-pipeline worktree: data + render). Local commits only, NO push.

**Companion docs:** gap audit `thoughts/shared/weekly-report-v1/bucket-logic-gap-audit.md` · spec `~/analytics/thoughts/shared/market-report-weekly-v1-spec.md` · skill reference `~/growth-reviews/.claude/skills/market-monthly-review/`.

---

## Phase 1 — Multi-market Monday skill  ← NEXT (user priority)
Goal: `/market-weekly-report <market|all> [<week-Monday>]` runs end-to-end for NA/Italy/Oceania by Monday.
1. `scripts/weekly_report/weekly_market_report.py` orchestrator: resolve default week (`config.latest_complete_week()`) → `build_snapshot` per slug → one `render.py` call (multi-snapshot = tabbed HTML, already supported) → print/open path.
2. `.claude/skills/market-weekly-report/` — SKILL.md (frontmatter + Usage + numbered workflow S1 resolve → S2 orchestrate → S3 Slack digest → S4 QA/open) + plugin.json. Mirror market-monthly-review exactly.
3. **52w-percentile week-type calibration** (replaces $-floor) — rollout-critical: fixed floor mislabels small markets (Italy/Oceania). Percentile G/L thresholds from trailing 52w per market.
4. **Slack digest as a skill step** (NOT producer — needs Slack MCP): reuse monthly S3 pattern + channel map (NA=CNSHDD2H1, Oceania=CHKRLFDPU+…, Italy=C045L2WQ79P; globals #tf-bugalert, #pod-live-entertainment). Hero+ CE × revenue-topic prioritization. Output = §4 standing digest + row context.
5. Run + validate all 3 markets: NA `--validate` PASS (hard gate) + Italy/Oceania spot-check headline rev vs Omni; eyeball bucket sanity per market.
Gate: one command → 3-market tabbed HTML, all sections sane.

## Phase 2 — Cheap correctness columns (producer, data on hand)
1. **Zero-spend transition flag** (closes the silent-EXIT hole: paused CE vanishes — Madame Tussauds case). Zero-rev flag only alongside it, marked "verify if expected".
2. **B1 long-tail burn line** — sub-$1k/4w bleeders aggregate ("N CEs · $X/wk below floor") — we created this hole raising the floor.
3. **Gray-zone counters** (B1/B2): "N CEs within 5pp/5% of a trigger" count line (Immersive −24.9% case).
4. **Action-register (tROAS part)**: promote existing `alerts.bid_changes()` into a §4 standing table (campaign · CE · old→new · date · spend) + **untracked-actions drift counter**. PPC-restrictions/holiday tabs deferred until user provides sheet IDs.
Gate: NA --validate PASS; each new line renders + degrades.

## Phase 3 — Per-bucket sparklines (render polish; bump earlier if Monday = demo)
B1 RPC+CM2 8w · B3 Rev'26+Rev'25 grey 10w+4 fwd LY · B4 Rev+RPC 10w. `sparkline()` helper exists; series mostly in `ce.weekly`/`weekly_ly` (B3 needs the +4 forward LY weeks — LY fetch already extended +7d, need +28d).

## Phase 4 — Daily-source diagnosis columns (the quality investment)
New daily fetches (daily completed-GBV, price/guest) + change-point windows (last-7d vs pre-change baseline) →
**TR-vs-pre-change** + **price/guest Δ** on B1/B2 (the Kennedy +15% price-step class — prevents wrong "Monitor" on the top leak) + **B3 TR-4w-YoY**. Flag thresholds: |ΔTR| ≥ 2pp, |Δprice| ≥ 10%.

## Phase 5 — Blocked items (plan/unlock one-by-one; each needs a data dependency)
| Item | Dependency to unlock | Value |
|---|---|---|
| **B5 Action Verdicts** | tracker data store + one-click filing (biggest; the "did our actions land" loop — Job #4) | Highest |
| **OV2 Gap/Pacing** (Adjusted RR) | `revenue_goals` join | High (leadership) |
| **OV1 Top-CEs strip** | none hard — build after cascade settles | Medium |
| **ce_groups + NA seed** → group-first rendering + masking detection | Pari's 8×24 taxonomy import | High for BGM adoption |
| PPC-restrictions + holiday register | sheet IDs from perf | Firewall completeness |
| B4 SIS/CVR-bench gates + RPC-Upside | weekly SIS pull + cohort benchmarks | Medium |
| In-bucket cluster collapse | none (edge-triggered; cap-10 partially covers) | Low-medium |

## Phase 6 — Ship
Merge `wt-weekly-buckets` → main (local; one `build_snapshot.py` hand-merge vs wt-weekly-data if it committed) → host on `market-notebook.vercel.app` `/weekly` route (need repo path) → ledger links the URL. Then Phase-D Airflow weekly cron (separate).

## Deliberately NOT doing
dbt re-platform (Path A locked) · native shadcn rebuild (static HTML route first) · B2 detection changes (validated, frozen) · metric-definition changes (canon locked).
