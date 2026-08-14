# Weekly Market Review (skill)

Source of truth for the Headout weekly market report — pipeline, template, spec, and final builds.
Imported 2026-07-12 from `~/analytics` safepoint branch `weekly-report-v1` (1c0b55d0).

- `scripts/weekly_report/` — pipeline: `python3 weekly_market_report.py <north_america|italy|oceania|all> --week YYYY-MM-DD`
- `thoughts/shared/market-report-weekly-v1-spec.md` — locked spec (buckets B1–B5, validation, gap classification)
- `thoughts/shared/weekly-report-v1/` — final rendered builds + gap audit
- `dbt/` — reference copies of the ce_weekly_* models; canonical home = analytics repo, PR from safepoint branch `weekly-report-v1`
- Sibling pattern: ~/market-monthly-review-skill (sync-skill.sh mirrors into analytics)

## V2 baseline verification

Phase 1 freezes the observable V1 producer/consumer boundary with synthetic edge cases,
minimized and pseudonymized sparse/dense/global snapshot shapes, snapshot contracts, downstream
coverage, manual browser-smoke evidence, a coverage matrix, and golden outputs under
`tests/weekly_report/`.
The verification path is local and no-write with respect to the checkout and every production
integration:

```sh
python3 scripts/weekly_report/verify_baseline.py
```

## V2 Market Headlines preview

The V2 headline is an isolated, no-publish renderer over the existing schema-v1
snapshot. It does not change the V1 report, bucket engines, Slack payloads,
Sheets, publishing, or sidecar loading.

```sh
python3 scripts/weekly_report/render_v2.py \
  tests/weekly_report/fixtures/snapshot_north_america_2026-08-02.json \
  --out /tmp/weekly-v2-headline.html
```

An optional approved goals sidecar may be supplied with `--goals`. Its top-level
shape is `{"markets":{"market_slug":{...}}}`. A usable market record requires
`month`, `monthly_goal`, `mtd_revenue`, `forecast_revenue`, and `as_of`; otherwise
the report explicitly shows that the target comparison is unavailable.

The V2 All-CE view reads the complete Overall/Paid weekly metric set,
TY/LY trajectories, metadata, customer-country composition and current
`buckets_final` membership directly from the same snapshot. It supports
snapshot-backed search and multi-select filters, sorting, top-mover order,
grouping, ratio-safe subtotals, contribution context and expandable
W0/W-1/change/WoW/YoY evidence. BDM and Growth regions are never inferred from
management type or lifecycle stage. They can be attached with
`--ce-dimensions` using this optional shape:

```json
{
  "markets": {
    "market_slug": {
      "ce_id": {
        "bdm_region": "BDM region name",
        "growth_region": "Growth region name"
      }
    }
  }
}
```

When this approved mapping is absent, the two organizational filters remain
disabled while all snapshot-backed portfolio controls, evidence and CE detail
continue to work. Saved views, watchlists, custom groups, notes and action
persistence remain separate migration slices and continue to live in V1 until
their V2 contracts are implemented.
