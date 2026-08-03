# Plan — two-layer actions system + weekly export + Thursday ping

Worktree `worktree-actions-ping` (off `main` c2f74ce). Build here; **post / Sheet-writes / deploy from main only.**
Refines `thoughts/shared/weekly-report-v1/HANDOFF-ping-and-sheet-export.md` with the 2026-08-03 decisions.

## Decided flow (locked)
```
GM   → §4 bucket action + comment  (Losing Money AND RPC/CM1 fluctuation buckets)
        saveAction(bucket)            [write-through + sync badge — ALREADY LIVE]
PERF → same report, reviews GM reco, marks FINAL action + comment
        saveAction(bucket+'_perf')    [NEW lane, reuses the same path]
Weekly Sheet → CE data + GM action/comment + PERF action/comment            (Phase 3)
Thursday ping → reads both layers → closed · perf-pending · needs-GM · deviated  (Phase 2)
```
- CE-drawer notes = general comments; prior-week history ALREADY renders (`historyFor`). No build.
- Perf granularity = **CE-level v1** (campaigns named in the perf comment). Per-campaign structured = v2 (needs report to expand CE→campaigns; deferred).

## Phase 1 — Perf lane in the report  *(upstream dependency for 2 & 3)*
File: `scripts/weekly_report/template/report_template.html`
- Add a **perf selector + perf comment** per row in the actionable buckets (Losing Money + Fluctuations),
  writing `saveAction(ceId, '<bucket>_perf', {status, note})`. Same dropdown vocab as GM + mandatory comment.
- Render the Action cell as **two lines**: `GM: <reco> — <comment>` / `Perf: <final> — <comment>`.
- Two-layer read: `actionSyncPull` already pulls all actions for the market-week — key by bucket so both
  `<bucket>` and `<bucket>_perf` load. Prev-week (−7/−6d) pull already handles the Sun→Sat key straddle.
- Reuses SYNC machinery (write-through, `updateSyncBadge`, `syncStatus`) — nothing new to build there.
- Rollout after merge: rebuild → publish → deploy → tell perf to use the lane.

## Phase 2 — Thursday ping  *(Aug-6 deadline)*
Files: `alert/thursday_actions_ping.py` (scaffolded), a Thursday sweep runner, `posted_ledger.json`
- Extend the join to **both layers** (GM `<bucket>` + Perf `<bucket>_perf`) across Losing Money + Fluctuations.
- States → sections: ✅ **closed** (GM+perf) quiet · ⚠️ **perf-pending** (GM reco, no perf) loud · ⚠️ **needs-GM**
  (flagged, no GM reco) loud · 🔀 **deviated** (perf ≠ GM) highlight.
- Wire POST (`post_message.post_message_chunked`, token env, `market_channels.json`), ledger dedupe,
  cron (one Thursday-evening IST sweep alongside the Monday runner), main-checkout guard.
- Integration test: one real v2 snapshot build (`weekly_market_report.py italy --no-open`) first.

## Phase 3 — Weekly Flagged Sheet export (Task 2)
Files: new exporter + hook in `scripts/weekly_report/publish_weekly.py` (main only)
- One weekly Sheet in perf's layout: identity + 4 weekly metric blocks (W0-first) + new_existing/tier +
  v2 extras (criteria, flag_streak, sort_delta, tROAS l4w/now, cm2_90d, launch, driver) + GM action/comment
  + perf action/comment (both layers joined from the store).
- Write via `gws sheets spreadsheets values update` (batch by market) or an Apps Script `flagged_upsert`.
- GUARD: never write the shared Sheet from a worktree build.

## Sequencing vs the Aug-6 deadline
1. **Phase 1** (perf lane) — needed for the ping's two layers. Build + merge + deploy first.
2. **Phase 2** (ping) — by Thu Aug 6. If Phase 1 slips, ping ships **GM-only** (degrade gracefully),
   perf-pending/deviated added right after.
3. **Phase 3** (export) — follows Aug-6 (kills perf's manual rebuild; not the announced deadline).

## Open / deferred (not blocking)
- Blindspots pass (`losing-money-blindspots.md`): own-target ROI gate (waiting on Adi), global build untested with v2 schema.
- Author-name prompt (`todo-prompt-author-name`, Option A) — attribution on perf/GM tags.
- Dormant CE list + ROI-bucket tracker (separate workstream).
