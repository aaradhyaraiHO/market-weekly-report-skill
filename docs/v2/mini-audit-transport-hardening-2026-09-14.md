# Mini Audit transport hardening — 14 September 2026

## Evidence and diagnosis

The earlier live test captured an intermittent backend identity-verification
error and a later failed suggestions read; both succeeded on explicit retry.
The historical authentication rejection had no action-level diagnostic log, so
its precise cause is not established. Do not retroactively describe it as a
proven signing-key or permission defect.

The next signed-in test loaded notes, work and suggestions and completed a
summary request without errors. The Apps Script execution page showed recent
read executions typically completing in 1–4 seconds. Filtering Failed and Timed
Out showed no matching executions in the displayed seven-day window. These
statuses do not prove that every returned application-level result was `ok`.
The CLI execution-list API lacked scopes; the same history was read through the
user's already-authorized browser, without changing access.

One definite proxy gap was reproducible in tests: an HTTP 200 HTML error or
non-JSON 404 from the upstream transport was returned directly instead of using
the existing bounded GET retry. Google documents ContentService's
[one-time redirect response URLs](https://developers.google.com/apps-script/guides/content#redirects).
The nonce/no-cache change protects against redirect reuse; caching is a possible
transport explanation, **not a proven cause of the historical auth error**.

## Changes and invariants

- Each backend request has a new server-generated, HMAC-covered nonce. Each GET
  attempt is re-signed with a fresh timestamp and nonce and uses `no-store`.
- GETs retry once for transport/network failures, rate limiting, 5xx responses,
  and non-JSON/non-contract responses other than HTTP 401/403.
- Real JSON access/validation errors and HTTP 401/403 are not retried. Explicit
  backend identity rejection still fails closed with its diagnostic code.
- Two 20-second read attempts remain within the existing 45-second UI budget.
- All normal client reads now receive that budget by default, including review
  status and receipts. Previously these still inherited a 15-second timeout.
  Explicit short note-recovery probes retain their existing deadline.
- Mutations are sent once only. Note-save durable-ID reconciliation and all
  business idempotency keys remain unchanged.
- Safe logs contain only action, attempt, HTTP status, timeout flag or elapsed
  time; never credentials, signed URLs, identities or note content.
- Permissions, metrics, buckets, stored report data, weekly alerts and schedules
  are unchanged. Later diagnostic versions of the Review-only Apps Script
  deployment are recorded below; legacy deployments and project HEAD are preserved.

## Local verification

397 weekly tests and baseline verification passed. New runtime regressions use
the actual proxy and actual Apps Script canonicalization/signature verifier,
with mocked I/O only. They cover fresh nonces, valid and tampered signatures,
expired signatures, HTML 200/404, rate limiting, explicit access failures,
bounded failures and no automatic POST replay.

The tests run on the integrated checkout, which retains separate uncommitted
Monday-generation changes. This is not an isolated-commit test count.

## Release record

Backend staging: `.cache/weekly_report/review_transport_fix_2026-09-14/notebook`.
Only `api/review.js` differs there from the preceding production artifact; all
230 HTML pages and unrelated files are byte-preserved. The adjacent
`notebook_receipt.json` records that preservation check.

That backend-only build (`dpl_2ZZdLMijgyayqnpscsU9ZLzz5VnX`) was canceled before
completion so it cannot supersede the complete client/proxy repair.

Complete staging: `.cache/weekly_report/review_read_complete_2026-09-14/notebook`.
The exact client asset was additionally replaced in 105 HTML reports; reversing
the replacement restores every original byte, including all report JSON.
The adjacent `preservation.json` records that check. No data was regenerated.
This was deployed as `dpl_8cyJgXCZasVzGdwR6vyc1JNZ9wfj`. All 40 browser routes
matched, with actual observations saved in the adjacent
`browser_observations.json`; aggregate fingerprint
`66499c01b383e528770bd61cf47147ebb973b367f37a556cda1a6798ef13f0b0`.
Rollback for the preceding release remains `dpl_At9XbWMTf5DYWFuhK9uub2t3GzpF`.

### Live reproduction and response-path repair

The new-source test reproduced `review_backend_auth_failed` on
`review_weekly_sync` at 13:53 IST (22,175 ms). This disproved the claim that the
read-only transport changes alone fixed the authentication symptom.

Review-only Apps Script versions 20 and 21 added safe rejection diagnostics:
missing field, expired timestamp, or signature mismatch. The HMAC verifier,
five-minute validity window, access rows and permissions are unchanged. Each
version was frozen from the existing deployed v19 source plus this small change;
the distinct original project HEAD was restored and checked byte-for-byte.
No original deployment other than the isolated Review endpoint was changed.

The next fresh test reply was independently present in Slack exactly once, yet
the browser reported `authenticated BGM identity required [missing_field]`.
Thus the mutation succeeded but its response was not successfully delivered to
the caller. This is not evidence of a wrong browser identity or signing secret.
It narrows the failure to the response/redirect path; the internal Google cause
of the substituted or missing-context response is not independently observable.

The follow-up proxy explicitly handles ContentService redirects. Every hop is
`no-store`; only the HTTPS `script.googleusercontent.com` content host is
accepted. A POST body/headers are never forwarded to a redirect, 307/308 POST
redirects fail closed, and no mutation is automatically replayed. An opaque
nonce distinguishes original POST URLs without putting identity, text or secrets
in a URL. Safe rejection reason codes are mapped to the existing service-error
UI rather than a browser sign-in loop.

Staging `.cache/weekly_report/review_redirect_complete_2026-09-14/notebook`
changes only `api/review.js` from the 40-route-verified artifact; all 230 HTML
pages and 247 other files match. Its `preservation.json` records the comparison.
The final proxy deployment is `dpl_9VYZq6fHfkXXLgjD5u82t3ZqE5Sk`, aliased to
`https://market-notebook.vercel.app`, with isolated Review backend version 21
(`acf385524eee199eb3dd3bf034a7e2224ae6d5b6bd341adfb301ce9ebd490f1d`).
The original project HEAD was restored after freezing that version. Backend
rollback is version 19 on the same deployment; website rollback is retained
above. A rollback never deletes notes or Slack messages.

### Final live verification

Test: CSEE CE 3286, Temple of Poseidon & Cape Sounion, report week 2026-09-06.
All new test material was explicitly labelled verification-only, with no business
findings or requested CE work. No weekly alert parent was sent or replayed.

- A fresh-source summary completed and saved at 14:10 IST.
- A new, separate dummy note saved at 14:11; the existing 12:40 note remained.
- The new saved note was sent as one reply to the existing CE Slack discussion;
  the UI confirmed delivery without an authentication/read error.
- Summarizing this genuinely new reply produced a new persisted summary at
  14:12. It included the final transport-save observation.
- Reload retained both notes and the exact summary. Repeating summary with no
  new source retained the same text/timestamp and created no duplicate work.
- Actions loaded: Needs review 0, Open 0, Completed 0. One test-only AI check
  from the preceding diagnostic summary was dismissed, not approved as work.
- The entire prior-week Mini Audit text (notes, summary and work state) matched
  the pre-deployment capture exactly.
- Independent Slack read-back found exactly one occurrence each of the
  transport, signature-diagnostic and final-save test replies in the
  [existing CE thread](https://headout.slack.com/archives/CSQ10TALA/p1789016453095459).
- All 40 routes were freshly opened again on the final deployment. Actual
  observations (URLs, fingerprints and timestamps, 08:42–08:44 UTC) are saved in
  `.cache/weekly_report/review_redirect_complete_2026-09-14/browser_observations.json`.
  All matched the staged assets; aggregate fingerprint remains
  `66499c01b383e528770bd61cf47147ebb973b367f37a556cda1a6798ef13f0b0`.
- The final deployment's available warning logs showed zero warnings during
  this verification window. Normal request logs confirmed explicit 302 handling
  from POST/GET to Google's content host.
- Final full suite: 397 passed; baseline verification: 397 passed;
  `git diff --check` passed.

This is a verified live repair and bounded failure handling, not a guarantee of
Google/Slack availability. The exact internal Google cause behind the original
missing-context response remains unobservable; do not claim a proven key mismatch
or expired user session. Genuine authorization failures still fail closed, and
uncertain writes are never automatically reposted.

The deployed Apps Script version 19 was fetched read-only and matched the local
source used by the signature tests exactly (SHA-256
`eae194565967050fe27963e6a3b8daddc6c0eaacd2515f72ddc038b5cf0e6d18`).
