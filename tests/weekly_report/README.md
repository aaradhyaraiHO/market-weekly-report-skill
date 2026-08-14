# Weekly Report V1 baseline contracts

This directory freezes the observable V1 behavior before Weekly Report V2 work.

The deterministic synthetic fixture exercises the current HTML renderer, Slack alert builder and
delivery normalization, Weekly Flagged Sheet row export, and Weekly Ledger series/matrix renderer.
`contracts/snapshot-v1-baseline.json` records the producer envelope observed at the start of V2.

Phase 1B adds minimized, pseudonymized gzip fixtures representing sparse, dense, and global
aggregation shapes. They use sequential synthetic identifiers and fixed synthetic narratives;
`fixtures/captured/fixture_manifest.json` records only their intended shapes. Consumer goldens live
in `golden/captured_manifest.json`. `COVERAGE_MATRIX.md` distinguishes verified, structurally
checked, manually checked, and intentionally untested paths.

The browser smoke was manually executed in the Codex in-app browser before fixture sanitization;
identifiers and source hashes are omitted from its evidence. The sanitized fixture has not been
rerun in-browser. The automated Python suite only validates the stored selector contract and dated
evidence; it does not launch or control a browser. Those records are
`browser_smoke_contract.json` and `golden/browser_smoke_result.json`.

Run the no-write verification from the repository root:

```sh
python3 scripts/weekly_report/verify_baseline.py
```

Generated files exist only inside an OS temporary directory. The verifier does not build snapshots,
query BigQuery, open a browser, read or write Sheets, post to Slack, publish the Ledger, touch
`.cache`, or write under `thoughts/`.
