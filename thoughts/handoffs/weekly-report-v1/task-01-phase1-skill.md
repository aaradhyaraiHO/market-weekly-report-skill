# Handoff — Weekly Report V1, Phase 1 (multi-market Monday skill + 52w calibration)

**Date:** 2026-07-10 · **Worktree:** `wt-weekly-buckets` (branch `worktree-wt-weekly-buckets`) · **Commits local only, NO push.**

## What was built

Phase 1 of `thoughts/shared/plans/2026-07-10-weekly-report-remaining-phases.md` — the multi-market Monday skill, the 52w-percentile week-type calibration, and the acceptance run.

1. **Orchestrator** `scripts/weekly_report/weekly_market_report.py`
   - CLI: `python3 weekly_market_report.py <market|all> [--week YYYY-MM-DD] [--no-open] [--validate]`.
   - Resolves week (default `config.latest_complete_week()`), builds a snapshot per slug via `build_snapshot.build_market` + `build_snapshot._write` (reuses existing helpers — no duplicated logic), then calls `render.py` **once** with all snapshot paths → one tabbed HTML. render.py prints the `wrote: <path>`.
   - `--validate` runs `build_snapshot.validate_na` when `north_america` is in the set (aborts on FAIL); other markets get a "no reference gate" note.

2. **52w-percentile week-type calibration** (replaces the fixed $-floor in flows.py)
   - `fetch.market_weekly_revenue(market, start, end)` — new market-level trailing weekly-revenue fetch (SUM(predicted rev) grouped by DATE_TRUNC WEEK(MONDAY), mirrors existing query_df+params style).
   - `build_snapshot.build_market` pulls 52 weeks, computes p75 of `|WoW-Δ|` (`np.percentile`, needs ≥20 weeks else None), passes it into `flows.build_header(..., large_threshold=)`.
   - `flows.build_header` — new optional `large_threshold` param (default None → old `max($500, 0.5%·W0rev)` floor preserved). Emits `headlines.week_header.calibration = {method: "p75_52w"|"floor", threshold_usd}`.

3. **Skill package** `.claude/skills/market-weekly-report/`
   - `SKILL.md` — mirrors market-monthly-review: frontmatter (trigger-rich desc), Audience, Dependencies, Usage, 4-step Workflow (S1 resolve → S2 orchestrate+NA gate → S3 Slack digest as agent-only step → S4 QA+deliver), Engine notes (predicted-rev canon, movement-flow cascade B1>B2>B3>B4 cap-10, §5/§6 empty-state, p75-52w calibration).
   - `plugin.json` — name market-weekly-report, v1.0.0, category analytics, context_files → weekly_market_report.py + config.py, deps (bigquery/slack/python≥3.9), settings.auto_send_slack:false.

## Files

| File | Change |
|---|---|
| `scripts/weekly_report/weekly_market_report.py` | NEW — orchestrator |
| `scripts/weekly_report/fetch.py` | + `market_weekly_revenue()` |
| `scripts/weekly_report/flows.py` | `build_header` + `large_threshold` param + `calibration` emit |
| `scripts/weekly_report/build_snapshot.py` | 52w fetch → p75 threshold → build_header wiring |
| `.claude/skills/market-weekly-report/SKILL.md` | NEW |
| `.claude/skills/market-weekly-report/plugin.json` | NEW |
| `thoughts/ledgers/weekly-report-v1.md` | MASTER SEQUENCE: P1 done, [→] P2 |

## Commits (local, no push)

- `a94eea46` feat(weekly-report): multi-market orchestrator + 52w week-type calibration (orchestrator + flows + fetch + build_snapshot)
- `4d735232` feat(weekly-report): market-weekly-report skill package
- (ledger docs commit — see below)

## Validation — acceptance run

`python3 weekly_market_report.py all --week 2026-06-29 --validate --no-open` → exit 0.

**NA gate: RESULT: PASS** — CM1/conv alerts 5/5 MATCH (High Roller, Universal Studios Hollywood, American Museum of Natural History, Edge NYC, Arte Museum New York), all up-swing, CV-excluded 0/0.

One tabbed HTML: `thoughts/shared/weekly-report-v1/report_multi_2026-06-29.html` (15.8 MB, 3 markets).

| Market | rev_w0 | week_header | calibration | threshold | week_type | B1 | B3 | B4 | cascade | CEs |
|---|---|---|---|---|---|---|---|---|---|---|
| north_america | $580,316 | ✓ | p75_52w | $47,808 | Both large — losses beat by $42,839 | 12 | 3 | 11 | ✓ | 581 |
| italy | $327,005 | ✓ | p75_52w | $35,982 | Mostly loss | 11 | 10 | 5 | ✓ | 835 |
| oceania | $126,019 | ✓ | p75_52w | $12,659 | Both large — gains beat by $4,142 | 11 | 4 | 16 | ✓ | 516 |

All markets: revenue_w0 > 0, week_header + calibration present, bucket_b1/b3/b4 + bucket_cascade present, ces > 50. Italy/Oceania built without exceptions (no reference gate; spot-check rev vs Omni is an S4/skill step). NA $580K ≈ 5% below $615K actuals ref (expected — predicted basis).

## Deviations from the task

- None material. The orchestrator lets `render.py` print the output path (it already prints `wrote: <path>`) rather than re-printing it — satisfies "print the output path" without duplication.
- Calibration used the trailing 52 weeks ending at `w0_end` (inclusive of W0); all three markets had a full 52 deltas, so the ≥20-week fallback never triggered here. Behavior for a thin-history market is covered by the `< 20` guard (untested against real thin data).

## Phase 2 open issues (next session)

Per plan Phase 2 — cheap correctness columns (producer, data already on hand):
1. Zero-spend transition flag (closes the silent-EXIT hole; zero-rev flag alongside, "verify if expected").
2. B1 long-tail burn line — sub-$1k/4w bleeders aggregate ("N CEs · $X/wk below floor") — the hole created by raising the B1 spend gate to $1k.
3. Gray-zone counters (B1/B2): "N CEs within 5pp/5% of a trigger".
4. Action-register (tROAS): promote `alerts.bid_changes()` into a §4 standing table + untracked-actions drift counter. PPC-restrictions/holiday tabs deferred (need sheet IDs).
Gate: NA --validate PASS; each new line renders + degrades.

Deferred beyond P2: P3 sparklines, P4 daily TR/price columns, P5 blocked items (B5/pacing/groups), P6 merge→main + Vercel host. Vercel `/weekly` route needs the notebook repo path from the user.
