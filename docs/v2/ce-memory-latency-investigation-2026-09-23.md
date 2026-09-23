# CE Memory latency — 23 September 2026

Status: confirmed server-side delay; the approved **proxy-only Mumbai region test was deployed and retained** after bounded live verification. See [release evidence](ce-memory-proxy-region-release-2026-09-23.md). The UI release itself was not a backend reliability fix, and the region improvement is not a guarantee against latency/failures.

## Measured evidence

Read-only Vercel runtime-log inspection of production deployment `dpl_HAaCLGngR4HBwzVzk4GFGYpXkc8n` found these `review_memory` requests from the live UI verification:

| Request ID | Total | Evidence |
| --- | --- | --- |
| `625b8425-cb08-4722-a385-4d2c8a649696` | 4,340ms | Apps Script headers 4,175ms; content headers 162ms; success |
| `7c7e1b8a-8209-4f5f-b9af-94858c99580b` | 6,346ms | Apps Script headers 6,250ms; content headers 94ms; success |
| `3c338220-f797-4831-867c-7d81f0ddca8e` | 13,933ms | First content retrieval timed out, subsequent response redirected back to script.google.com and was rejected by the existing allowlist; fresh signed read succeeded |
| `c7637ce1-4ca0-42a4-a945-f6ba8b3e153c` | 28,017ms | First Apps Script header wait timed out at 20,001ms; second attempt took 7,913ms plus 100ms content retrieval; success |

Other `/api/review` reads returned HTTP 502 in the same window. The previous error-level-only log query returned no entries, but that filter did not cover failures logged with `console.warn` or requests represented at info level. It must not be treated as a clean backend-health result.

The measured waits are upstream of the browser rendering. DNS/TCP/TLS for the content response completed in 8–11ms in the slow samples. This establishes the delay location, not Google's internal cause. Repeated Sheet reads may contribute to clean-read duration; there is not yet a per-service-call profile proving their share. Do not infer a regional cause from these samples.

## Controlled experiment

A Mini Audit proxy-only Mumbai (`bom1`) versus existing Virginia (`iad1`) test was proposed previously. The user approved it with “yes” on September 23. The following safeguards were used; authentication, API code, data storage, permissions and timeouts were not changed.

Approved test plan:

1. Re-resolve production and its matching complete artifact. Current rollback pair is `dpl_HAaCLGngR4HBwzVzk4GFGYpXkc8n` and `.cache/weekly_report/ce_memory_ux_release_2026-09-23/notebook`.
2. Verify the supported per-function region setting; affect only `api/review.js`, preserving all other functions and all notebook files.
3. Collect a fixed, small set of signed-in read-only CE Memory and notes reads before/after, for the same CE/week identities. Do not replay any POST, create test notes or send Slack messages.
4. Compare total latency, original Apps Script hop, content redirect failures, retries and failed reads; inspect the actual deployed region. Successful faster samples alone do not prove reliability.
5. Check preserved source-record text, actual report/UI hashes and authentication behavior. Roll back if latency/error behavior is worse or the change does not isolate the intended proxy.
6. Retain a change only if evidence supports it; otherwise report the failed hypothesis. A larger move away from Apps Script's interactive response path requires a separate backend/storage design, authorization and migration plan, not an improvised bypass.

The initial diagnostic step made no deployment changes. The subsequent approved experiment changed only `vercel.json`'s per-function region for `api/review.js`; all 265 other notebook files remained byte-identical. Eight new CE Memory reads completed in 5.0–8.1 seconds versus four fresh Virginia reads at 7.3–39.1 seconds. One Mumbai content timeout was recovered by the existing retry logic. This small sequential sample supports retaining the improvement, not claiming causality is proven or that every future request will succeed.
