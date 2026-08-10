# Archived worktree work (2026-08-10)

Patches saved when the weekly-report worktrees were pruned. Each was **not on main**
(unmerged commit) or **uncommitted WIP** at prune time. Recoverable with `git apply` (WIP)
or `git am` (format-patch commits) from repo root.

| patch | from worktree | what it is | status when archived |
|---|---|---|---|
| `0001-switch-paid-metrics-to-ads_campaign_stats-*.patch` | `all-ce-view` | switch paid metrics to `ads_campaign_stats` (Google Search + Bing Search) — ties to the ROI-reconciliation work | committed, **unmerged** (not on main) |
| `all-ce-view-UNCOMMITTED-wip.patch` | `all-ce-view` | further WIP on `build_snapshot` / `config` / template | uncommitted |
| `0001-Add-structured-Slack-context-cards-*.patch` | `SLACK` | structured Slack context cards with ce_id + scope routing | committed, **unmerged** (related `slack-port` merged a different piece) |
| `diagnostics-UNCOMMITTED-wip.patch` | `diagnostics` | scratch edits to `alerts.py` + template on already-merged code | uncommitted (likely throwaway) |

To reapply a committed patch: `git am path/to/0001-*.patch`
To reapply a WIP diff: `git apply path/to/*-wip.patch`

The `diagnostic` worktree also had ~22 untracked scratch scripts (diag/build/render
experiments, mockups) that were NOT archived — throwaway. Its one real spec was preserved
separately as `cm2-loss-eroding-bucket-spec.md`.
