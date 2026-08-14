# Golden outputs

`manifest.json` was captured from the untouched V1 consumers at commit `d6e4a69` on
`codex/weekly-baseline-contracts`. Each value hashes a complete canonical output, not a sample:
rendered report HTML, Slack payload, normalized Block Kit, Sheet header/rows, and Ledger state/matrix.

`captured_manifest.json` extends this with minimized, pseudonymized sparse, dense, and global
fixtures plus a sparse+dense multi-market render. `browser_smoke_result.json` is the dated record of
the manually executed pre-sanitization in-app browser check with identifiers omitted. The sanitized
fixture has not been rerun in-browser. The automated suite validates that evidence record; it does
not execute a browser test.

Do not refresh a hash merely because a test fails. First inspect the full output difference and confirm
that the behavior change is intentional and approved; this baseline exists to expose changes to report
structure, calculations/bucket results, Sheet output, Slack payloads, and URLs.
