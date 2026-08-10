# Archived worktree work (2026-08-10)

Patches saved when the weekly-report worktrees were pruned. Each was **not on main**
(unmerged commit) or **uncommitted WIP** at prune time. Recoverable with `git apply` (WIP)
or `git am` (format-patch commits) from repo root.

> **VERDICT (checked 2026-08-10): all three are REDUNDANT / OBSOLETE — kept only as a
> historical record, not pending work.** The `git cherry` "+" markers were misleading: the
> *commits* aren't ancestors of main, but the *content* is already on main (and has evolved
> past these patches).
> - **all-ce-view** (paid metrics → `ads_campaign_stats`, G+Bing SEARCH): main already does
>   this (`config.py` `ADS_STATS`, fetch.py `ad_platform IN (Google,Microsoft)` + `SEARCH`)
>   and went further — Google-only for pause/scale (2026-07-17), single-source funnel
>   (2026-07-20). The patch is dated 2026-07-13. Superseded.
> - **SLACK** (structured context cards): fully on main via the merged `slack-port` —
>   `market_review_context[]` + sidecar loader, CE-scoped cards routed into the drawer's
>   "Slack context" section, scope/ce_id in SKILL.md. Superseded.
> - **diagnostics WIP** (add `revenue_4w`, rank bucket1 by 28-day revenue): targets the OLD
>   bucket1 layout (Cause/Swing/Persist/CV) removed in the L3W fluctuation re-cut; the new
>   bucket already carries `stake_usd` for ranking. Obsolete — won't even apply cleanly.

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
