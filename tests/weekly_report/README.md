# Weekly Report V1 baseline contracts

This directory freezes the observable V1 behavior before Weekly Report V2 work.

The deterministic synthetic fixture exercises the current HTML renderer, Slack alert builder and
delivery normalization, Weekly Flagged Sheet row export, and Weekly Ledger series/matrix renderer.
`contracts/snapshot-v1-baseline.json` records the producer envelope observed at the start of V2.

Run the no-write verification from the repository root:

```sh
python3 scripts/weekly_report/verify_baseline.py
```

Generated files exist only inside an OS temporary directory. The verifier does not build snapshots,
query BigQuery, open a browser, read or write Sheets, post to Slack, publish the Ledger, touch
`.cache`, or write under `thoughts/`.
