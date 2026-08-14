# Golden outputs

`manifest.json` was captured from the untouched V1 consumers at commit `d6e4a69` on
`codex/weekly-baseline-contracts`. Each value hashes a complete canonical output, not a sample:
rendered report HTML, Slack payload, normalized Block Kit, Sheet header/rows, and Ledger state/matrix.

Do not refresh a hash merely because a test fails. First inspect the full output difference and confirm
that the behavior change is intentional and approved; this baseline exists to expose changes to report
structure, calculations/bucket results, Sheet output, Slack payloads, and URLs.
