# V2 input contract

The schema-v2 `headlines` payload produced by `codex/v2-market-headlines` is the source of truth for KPI and mover figures. Reject the V1 `markets` payload.

## Headline

Select the latest matching `headlines[]` record by `market_slug`. The builder reads:

- Revenue: `revenue`
- Versus last week: `wow_pct`
- Versus the same week last year: `yoy_pct`
- Projected target attainment: `monthly.forecast_attainment_pct`
- Projected revenue and goal: `monthly.forecast_revenue`, `monthly.monthly_goal`

The remaining approved Alert 1 KPI lines come from `detail.metrics`, indexed by `key`:

- Overall ROI: `roi1`
- AOV: `aov`
- Take rate: `tr_pct`
- Paid ROI: `paid_roi`
- Paid clicks: `paid_clicks`
- Paid CVR: `paid_cvr`

For each metric, use `w0` as Actual, `delta_pct` as versus last week, and producer-supplied `yoy_pct` as versus the same week last year. `headline_v2.py` derives `ly_w0` and `yoy_pct` from the report's aligned `detail.metrics[].series`; the alert must not recalculate them. Preserve unavailable values as `—`. Revenue is the only table with a target column. Overall and Paid each use a three-comparison-column table with no target column.

`monthly.state` must be `current`. Missing or stale target data is fatal for Alert 1.

## Top 5 and Bottom 5

Use these V2 arrays without reranking:

- `movers.gains[:5]`
- `movers.drops[:5]`

Each mover must contain:

- `ce_id`, `ce_name`, `revenue`
- `wow_abs`: W0 minus last week
- `delta_4w`: W0 minus trailing-four-week average
- `yoy_pct`: percentage growth versus the same week last year
- `target_mtd_attainment_pct` when `monthly_target` is present

Match the V2 report display: LW and L4W are signed dollar movements; LY is a percentage; target is MTD attainment against calendar-prorated target pace. If `monthly_target` is null, display `No target` rather than inventing one.

## BGM configuration

`alert/v2/market_bgms.json` stores real Slack user IDs:

```json
{
  "markets": {
    "italy": {"slack_user_ids": ["U123", "U456"]}
  }
}
```

An empty mapping blocks generation.

## OKR results

`alert/v2/build_market_okr_results.py` writes same-week market results separately from the tracker/config:

```json
{
  "schema_version": 1,
  "week_start": "2026-08-02",
  "week_end": "2026-08-08",
  "markets": {
    "italy": [
      {
        "id": "grow_cumulative_pro_plus_ces",
        "label": "Grow cumulative Pro+ CEs",
        "current": "21 CEs",
        "detail": "L92 predicted revenue ≥ $10K",
        "value": 21
      }
    ]
  }
}
```

The alert rejects a sidecar whose `week_start` differs from the selected headline. Market targets are absent by design because the approved tracker targets are company-level.

The Alert 1 headline links to `https://central-tracking.vercel.app/okr-tracker`. The sidecar retains `detail` for auditability, but the main Slack message omits methodology prose and displays only the shortened label, current value, `reached` count when present, target when present, and status.
