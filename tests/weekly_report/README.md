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

## V2 visual and engine boundaries

Every V2 surface must use the Oak/Eevee foundation defined in
`scripts/weekly_report/template/report_v2_template.html`: Halyard text/display families, the Eevee
semantic color variables, the 8/16/20 px radius scale, and the shared elevation tokens. New V2
components should extend these variables instead of introducing a second font, palette, or shadow
system. The automated contract rejects the previous one-off purple and unrestricted
`transition: all` declarations.

V2 is a consumer of the existing V1 weekly engine. Mover order and last-year seasonality tags come
from `market_summary.headlines.week_header`; V2 preserves them without independently recalculating
their thresholds. Older snapshots use the existing raw WoW mover lists as a documented fallback.
Internal dual-clock, structural-flow, concentration, and provenance evidence is deliberately not
shown in the market drawer because it does not help the weekly reader decide what to investigate.

The V2 market-detail drawer preserves the V1 evidence contract: the ordered 12-metric table,
legacy Orders/AOV/Avg-CM1 backfills, W0/W-1/absolute/percentage deltas, aligned TY/LY sparklines
with weekly hover values, and the five-factor WoW Shapley result. Monthly target pacing stays on
the overview because repeating it in the evidence drawer would create two competing summaries.
