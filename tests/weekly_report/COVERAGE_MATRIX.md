# Weekly Report V2 pre-refactor coverage matrix

Status meanings:

- **Verified** — exercised automatically against checked-in fixtures with assertions on output. No production I/O.
- **Manually checked** — executed interactively in a browser; the automated suite validates only the stored contract and dated evidence.
- **Structurally checked** — imports, schemas, routing, command construction, or pure transformations are checked; the external side effect is not executed.
- **Untested** — requires production credentials, data, or a deployment and is intentionally outside this safety net.

| Path / consumer | Status | Evidence and boundary |
|---|---|---|
| `build_snapshot.py` market producer | Structurally checked | Sanitized sparse/dense shapes satisfy the V1 contract; BigQuery production is untested. |
| `build_global.py` Headout producer | Structurally checked | A sanitized global shape verifies `n_markets`, CE cap, market breakdown, partial-window metadata, and consumer compatibility; BigQuery production is untested. |
| `weekly_market_report.py` orchestration | Structurally checked | Target resolution, output naming, and render hand-off are covered; producer subprocesses are not run. |
| `render.py` single-market HTML | **Verified** | Synthetic plus sanitized sparse/dense/global fixtures render and preserve embedded payloads. |
| `render.py` multi-market tabs | **Verified** | Sparse + dense bundle order, deduplication, tab payload, and report naming are asserted. |
| Report embedded JavaScript | **Manually checked before sanitization; evidence validated automatically** | The Codex in-app browser check covered boot, All-CE rows, search, drawer open/close, bucket collapse/restore, and console errors. Identifiers are omitted from evidence. The sanitized fixture has not been rerun in-browser. The Python suite validates `browser_smoke_contract.json` and the dated evidence record; it does not launch or control a browser. |
| `run_weekly.py` report stage | Structurally checked | Market selection and producer/render command construction use mocks only. |
| `run_weekly.py` publish stage | Structurally checked | Sidecar/no-sidecar and render/publish commands use mocks only. |
| `run_weekly.py` alert dry-run/live stages | Structurally checked / Untested | Paths, week boundary, payload/RCA filenames, and command chain are inspected; RCA BigQuery and Slack delivery are untested. |
| `publish_weekly.py` market publish | **Verified** | A sanitized market fixture produces report/state/archive/current aliases and a matrix in a temporary deploy directory. |
| `publish_weekly.py` Headout hero | **Verified** | The sanitized global fixture publishes the Headout hero and `n_markets` state in a temporary directory. |
| Vercel deployment | Untested | No deployment or network operation is permitted. |
| `export_perf_sheet.py` row mapping | **Verified** | Synthetic edge cases plus sanitized sparse/dense fixtures; header/units/actions remain frozen. |
| `export_perf_sheet.py` Sheet reads/writes | Untested | `gws`, GM-action fetch, campaign-category BigQuery, and live Sheet mutation are not invoked. |
| `export_flagged.py` CSV exports | **Verified** | Sanitized market fixtures write both CSV shapes under a temporary directory. The V2 shape currently yields a header-only legacy Losing Money CSV; that compatibility fact is asserted. |
| `export_full_lm.py` ungated engine/export rows | **Verified** | `build_rows` runs against a sanitized sparse fixture with external enrichment maps explicitly isolated to `{}`. Live enrichment and `write_tab` are untested. |
| `perf_history.py` ingestion | **Verified** | Header-row discovery, mixed legacy/current columns, CID deduplication, priority, ordering, and sidecar output run with mocked captured tab-shaped values. Live Sheet read is untested. |
| Render Slack/perf sidecar ingestion | **Verified** | Sidecar merge behavior is tested with temporary snapshot-adjacent JSON files. |
| `weekly_alert.py` report → Slack payload | **Verified** | Sanitized fixture reports produce payloads and RCA ID sets without BigQuery. |
| `post_message.py` normalization/chunking | **Verified** | Payload validation, Block Kit expansion, thread resolution, and chunk limits are pure-tested. |
| `post_message.py` Slack post/update | Untested | No Slack API calls or ledger writes are made. |
| `weekly_rca_helper.py` | Untested | Requires BigQuery; only its `$rca` hand-off contract is covered. |
| `bucket_diff.py` | **Verified** | Same-fixture and changed-bucket comparisons use sanitized reports. |
| `thursday_actions_ping.py` | Structurally checked | Sanitized fixture flagged-row ordering and message construction are pure-tested; notes fetch/post are untested. |
| `update_posts_weekly.py` | Structurally checked | Ledger resolution and header extraction are pure-tested; Slack reads/updates are untested. |
| `run_market_alert_sweep.py` | Structurally checked | Deploy-vs-fresh gate delegates to verified `bucket_diff`; hard-coded `/tmp` sweep and Slack updates are untested. |
| `alert/post_followups.py` and other Slack delivery scripts | Untested | Network delivery is excluded; they do not consume the weekly snapshot/report contract directly. |
| Notes Apps Script / GM actions | Untested | No Apps Script reads or writes are permitted. |

The fixture shapes were derived offline from existing repository artifacts, then minimized and
pseudonymized. No source hashes, paths, original mappings, or production narratives are retained.
