# CE Memory UX production release — 23 September 2026

Status: **deployed and verified** for the approved CE Memory UI scope. No generation, scheduling changes, alert posting, note writes, summary generation, formula changes or bucket changes were performed.

## Release

| Field | Verified result |
| --- | --- |
| Production | https://market-notebook.vercel.app |
| Deployment URL | https://market-notebook-8uo7svts2-headout.vercel.app |
| Deployment | `dpl_HAaCLGngR4HBwzVzk4GFGYpXkc8n` |
| Target / status | Production / Ready; canonical alias confirmed after deployment |
| Source commit | `46c4d2f4eb44aba23d29c0c37dc142e8a6778c1c`, pushed to `origin/main` |
| Framework | Static HTML plus existing serverless APIs |
| Build duration | 31 seconds; complete-notebook upload took additional time |
| Published report week | 13–19 September 2026, unchanged |
| Rollback deployment | `dpl_9UFjfeRxkNDwyrDz9H1R2cupp1Qs` |

The changes label historical passages with source/author/date, give each citation its own exact-record navigation and focus, improve touch targets/wrapping, and provide memory-specific refresh progress/success/failure feedback. Different saved records remain distinct. Implementation and preview evidence: [CE Memory UX patch](ce-memory-ux-fix-2026-09-21.md).

## Preservation and future-run baseline

Before release, production was freshly resolved to the prior deployment and its complete verified artifact, `.cache/weekly_report/v2_package_2026-09-13/notebook`.

The new verified complete production artifact is:

`/Users/aaradhyarai/market-weekly-report-skill/.cache/weekly_report/ce_memory_ux_release_2026-09-23/notebook`

Its sibling receipts are `deployment_receipt.json`, `preservation.json`, `artifact.json`, `browser_observations.json`, and `browser_verified.json`. Retain this complete artifact as the matching baseline while this deployment is production; if production advances, resolve the newer matching complete artifact instead. Do not seed from the older September 21 pair after this release. This is a preservation record, not a scheduling change.

- 123 existing current/historical weekly pages received only the canonical view JavaScript/CSS replacement.
- Strict before/after comparison removed those exact UI blocks and proved the remainder byte-identical.
- All other 143 notebook files were byte-identical, including APIs, Headout pages and monthly content. The file set is unchanged.
- Snapshot/report data, history stores, comments, CE Memory source records, delivery locks, retry journals and alert ledgers were not modified.
- CSEE + Nordics retains the existing shared-page/two-dataset behavior.
- The canonical generator imports the committed view assets, so future generation uses the same patch.

## Verification

- Fresh full suite: **401 passed**.
- Fresh baseline verifier: **401 passed**.
- Diff whitespace check: passed.
- Fresh signed-in Chrome checks: **40/40 canonical routes** matched their staged data/UI component fingerprints, with visible market/week evidence. Includes 17 markets, Headout, shared CSEE/Nordics, latest and exact-week links, monthly home and weekly ledger.
- `release_integrity.py browser` accepted all observations and wrote `browser_verified.json`.
- Real CE Memory: Nordics CE **7416, Tromso Cable Car**, current week September 13, history week September 6. All three original records remained byte-identical in DOM text before/after deploy, after explicit Refresh, after reload and in the small-screen check. SHA256 of the serialized three-record text array: `41a733ec545953cf8e3a6508cb4322c2580dc5976b2566ed98923aed72b9d3cd`.
- Source 2 selected the actual second record, opened its Sources disclosure, focused `Source 2 · Note` and displayed the purple focus outline; the two different notes and revision were preserved.
- Explicit Refresh displayed “Refreshing CE history… Previously loaded records remain below.” then “History updated”. It did not clear previously loaded records.
- Small-screen live check: measured CSS viewport **520px**, document scroll width **520px**; no horizontal overflow. Source text wrapped, exact citation focus worked, citation buttons measured 44×44px and Refresh 76×44px. The requested 390px override maps to 520 CSS pixels under this browser's current scaling; this result is not represented as a live 390px test. The earlier isolated preview separately verified 390px. Temporary viewport override reset.
- Browser error capture returned no errors for the verification tab. Deployment error-level log scan over the prior hour returned no entries. This bounded scan is not a guarantee of long-term reliability.

## Monitoring and limits

The fresh memory reads succeeded, but displayed loading states before completion. This UI-only patch does not claim to eliminate backend latency or outages. Failure preservation/retry and stale-response isolation were covered by runtime tests; a production failure was not deliberately induced. No new-save-to-memory, Slack-send or AI-summary mutation was performed during this release.

Vercel build emitted an existing edge-runtime deprecation warning in middleware; it did not fail the build and was left unchanged. Observability drains were not inspected or changed. Recommended follow-up is to monitor real memory read failures/latency during normal use; no new monitor or schedule was created.

The unrelated untracked `alert/posted_ledger.lock` was left untouched. Rollback, if separately authorized, must use the complete previous deployment, not a report-only artifact.
