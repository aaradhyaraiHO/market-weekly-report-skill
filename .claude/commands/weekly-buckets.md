---
description: Resume the Weekly Market Report bucket work in this worktree from the latest handoff
---
You are resuming the **Weekly Market Report — Defend/Compound buckets** work in this worktree
(`.claude/worktrees/diagnostic`). The design is LOCKED — do not re-derive it. Continue from the handoff.

## 1. Load state (read these, in order)
- Latest handoff: the newest file in `thoughts/shared/handoffs/weekly-report-v1/` — currently
  `thoughts/shared/handoffs/weekly-report-v1/2026-07-13_16-39-46_buckets-final-defend-compound-engine-built.md`.
- Production engine: `scripts/weekly_report/buckets.py` (`build_buckets(snap)` is the source of truth).
- Renderer: `scripts/weekly_report/render_report.py`.
- Project memory: `~/.claude/projects/-Users-aaradhyarai-market-weekly-report-skill/memory/weekly-bucket-redesign-v2.md`.

## 2. Verify it still runs (all from `scripts/weekly_report/`)
- `python3 buckets.py /tmp/na_snap.pkl` → engine summary.
- If `/tmp/{na,it,oc}_snap.pkl` are missing (they live in /tmp, may not persist), regenerate only what you need:
  `python3 -c "import datetime,build_snapshot,pickle; pickle.dump(build_snapshot.build_market('north_america',datetime.date(2026,6,29),with_availability=False),open('/tmp/na_snap.pkl','wb'))"`
  (needs bq/gcloud ADC auth). Then `python3 stress_test.py /tmp/na_snap.pkl` to confirm 0 anomalies across markets.

## 3. Report status, then continue
Give a ~5-line status: what's BUILT (engine + wired to pipeline + renderer + New CEs/Iteration + stress-tested 3 markets),
and the OPEN items from the handoff, split into **decisions** and **build/data**. Key open items:
- Decisions: rename Seasonality → "Fluctuations"; component Δ$ display (fold driver in); Scale-Up strictness; B3 in/out; availability-as-trigger.
- Build/data: New Pro+ 4-quarter gate (band-explorer — replaces the 12wk proxy); report shell (§0/overlays/B5); PP + seasonality info-tag (Aditya's levers sheet); integrate the diagnostic lens.

Then: if I passed an item as an argument, start on it. Otherwise ask which open item to pick up.

Constraints: reuse the existing engines (buckets.py, alerts.py POF, ce_buckets); don't hit BigQuery unless a fresh
snapshot is required; match surrounding code style; flag the known data-quality gaps (null-ROI funded CEs, bad tROAS) if relevant.

Argument (optional open item to start on): $ARGUMENTS
