# Weekly Market Report V2 — autonomous runbook

## Contract

`scripts/weekly_report/run_v2_release.py` is the canonical release entry point.
It packages the V2 presentation around the established V1 measurement engine;
it does not replace or recalculate V1 bucket, mover, Shapley, or weekly metric
logic.

The default run is safe: it may read BigQuery and create repository-local build
artifacts, but it cannot deploy, post Slack alerts, or write Sheets.

## Safe full run

```sh
python3 scripts/weekly_report/run_v2_release.py --week YYYY-MM-DD
```

The week must be a Sunday. The command stops on the first failed gate and writes
a receipt even when it fails.

Order of operations:

1. Run the complete no-write baseline test suite.
2. Build fresh V1 and V2 reports for every configured market.
3. Build the Headout global report.
4. Run one combined V2 parity gate across all snapshots.
5. Validate V2 alert configuration.
6. Stage a self-contained notebook without Sheet writes.
7. Dry-run the complete V2 market-alert batch.

Artifacts:

- V1 reports: `thoughts/shared/weekly-report-v1/`
- V2 reports: `thoughts/shared/weekly-report-v2/`
- full manifest: `.cache/weekly_report/v2_release_full_<week>.json`
- staged notebook: `.cache/weekly_report/v2_package_<week>/notebook/`
- run receipt: `.cache/weekly_report/v2_run_<week>.json`

## Preview the plan

```sh
python3 scripts/weekly_report/run_v2_release.py \
  --week YYYY-MM-DD --plan
```

This prints JSON and makes no filesystem or external changes.

## Production cutover

After reviewing the staged reports:

```sh
python3 scripts/weekly_report/run_v2_release.py \
  --week YYYY-MM-DD \
  --notebook-dir ~/analytics/market-notebook-v2 \
  --deploy
```

Only after the alert dry run is approved:

```sh
python3 scripts/weekly_report/run_v2_release.py \
  --week YYYY-MM-DD \
  --notebook-dir ~/analytics/market-notebook-v2 \
  --deploy --post-alerts
```

`--post-alerts` requires `--deploy`, so alerts cannot precede a successful report
deployment. The alert stage preflights the entire market batch before any Slack
write. Headout is intentionally not an alert target.

## Failure and rollback

- A failure stops every later step and marks the receipt `failed`.
- V2 enrichments fail or omit independently where their contracts allow it.
- V1 reports are built from the same fresh snapshots and remain the rollback.
- Do not bypass a failed parity gate to publish V2.
- Re-running the same week is safe for local report generation; live alert
  duplicate protection remains enforced by the existing delivery ledger.
