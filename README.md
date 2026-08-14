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
