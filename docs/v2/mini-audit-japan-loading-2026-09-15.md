# Mini Audit loading investigation — 15 September 2026

## Observed failure

Japan's TeamLab Planets Tokyo (CE 4054) and Universal Studios Japan (CE 1651),
week 2026-09-06, reproduced intermittent unavailable/loading states. Vercel
recorded read attempts timing out at 20 seconds and requests failing after two
attempts. Other attempts returned non-contract HTML/404 responses. In the same
window, visible Apps Script v21 executions completed in roughly 1–3.6 seconds.
Those execution records cannot be correlated one-to-one with proxy requests;
they do not establish a slow Sheet query or the exact failing network hop.

One confirmed UI defect amplified failures: every Retry reloaded all four CE
resources. Retrying discussion could leave suggestions unavailable, and a
pending unrelated resource delayed recovery. The suggestions Retry also used
the thread Retry control ID.

## Targeted changes

- CE reads have independently scoped in-flight records and success timestamps.
  Retry notes, discussion, suggestions and threads fetch only that resource.
  Duplicate retry clicks coalesce; healthy resources remain visible and cached.
- A full refresh after a mutation waits for older reads then refreshes the
  affected resources. Week/market switches invalidate stale results. The
  confirmed-note version guard remains in place.
- The proxy logs a server-generated request ID and safe timing/status at each
  response-header hop and final read body. No identities, signed URLs, secrets,
  note content or response bodies are logged.
- Redirect response bodies are canceled before the next request. This repairs
  a definite connection-resource lifecycle omission. Node's fetch implementation
  [requires consuming or canceling response bodies](https://github.com/nodejs/undici#garbage-collection);
  this is not yet proof that the omission caused the observed production stalls.
- Existing access/signature checks, two-attempt GET budget, no automatic POST
  replay, durable note IDs and Slack idempotency are unchanged. Backend v21,
  metrics, buckets, snapshots, schedules and alerts are not modified.

## Verification and release status

Final local suite and baseline: 399 tests pass. Runtime cases cover independent
failure recovery while another resource remains pending, duplicate retry clicks,
week-switch stale responses, post-mutation refresh, preservation of confirmed
notes, safe redirect cleanup and credential-free diagnostics.

Candidate complete notebook:
`.cache/weekly_report/japan_retry_fix_2026-09-15/notebook`.
Base: `.cache/weekly_report/review_redirect_complete_2026-09-14/notebook`,
deployment `dpl_9VYZq6fHfkXXLgjD5u82t3ZqE5Sk` (retained rollback).
Only the exact view asset in 105 HTML pages and `api/review.js` change.
Reverse replacement restores original report bytes; all other files match.
The adjacent preservation and browser manifests record the candidate.

The final production status is recorded below. The UI repair is live, but the
backend transport repair is incomplete; this is not a full end-to-end pass.

## Response-path evidence and recovery

The first diagnostic release was `dpl_45gHGMoTuCYJfDWNnauQJZRiVsp6`.
It reproduced a CSEE work-read failure after the UI repair. Request
`254ca7d8-f2fe-4d24-a986-129faba70eed` received Apps Script headers in 1,837ms,
then stalled waiting for headers from `script.googleusercontent.com` for
18,165ms until the shared read budget expired. Thus response-body cleanup alone
was not sufficient.

A fresh HTTPS connection isolated the next stage without shared fetch pooling
(`dpl_9yfVb6kUM8v4E4zLfbuGp6pmKUYL`). DNS, TCP and TLS completed in 9–25ms
in the observed samples; some content response headers still never arrived.
This rules out a slow TLS handshake or pooled-connection reuse as a sufficient
explanation. It does not establish the internal cause within Google's service.

The read-only follow-up retains normal HTTPS certificate verification and retrieves only
the allowlisted one-time response URL. That **GET response retrieval** gets up
to three fresh connections, each with a 3-second header deadline. Successful
samples returned content headers in 85–137ms. The original 20-second overall
GET-attempt deadline still bounds both headers and body; no timeout was raised.
The parent signal stays connected until body completion/cancel, and all timers
and listeners are cleaned up. A timed-out response does not automatically
re-execute a mutation. The final implementation explicitly excludes original
POST requests from the short response-retry path: mutation acknowledgements
retain their original deadline and existing durable-ID reconciliation. No
mutation is replayed automatically.

Final artifact: `.cache/weekly_report/japan_read_recovery_2026-09-15/notebook`.
Production deployment: `dpl_BHtacc1P4A1ZuCiwuGrGgRmAVacj`,
`https://market-notebook-invp5pjyz-headout.vercel.app`, aliased to
`https://market-notebook.vercel.app`.
Only `api/review.js` changes after the first UI candidate; preservation manifests
for each stage retain the complete artifact chain.

## Final live checks and remaining blocker

- Signed-in browser verification passed for all 40 manifest routes: latest and
  September 6 dated reports plus the monthly and weekly notebook indexes.
  Script/style fingerprints match the final staged artifacts. Evidence:
  `.cache/weekly_report/japan_read_recovery_2026-09-15/browser_verified.json`.
- CSEE CE 3286 retained both saved note IDs and exact text after reload; no
  duplicates. The existing 758-character discussion summary remained identical
  (SHA-256 `5008a95575b4686f76c489726631132dba4c7c8e53bdf826417083716108cdb1`).
  Its notes, summary and action counts loaded on the final build.
- Japan CE 1651 loaded its existing discussion binding and action counts on
  the final build. CE 4054 still reproduced actions/suggestions failures after
  reload. Its notes and discussion loaded independently; a scoped retry
  recovered suggestions without reloading the healthy resources. Actions
  remained unavailable in that observation. Do not describe Japan as fixed.
- Live read response recovery was observed, e.g. request
  `15a21b78-d7fd-4dd9-9b1a-4275c99e57d1`: first content-header timeout,
  second content retrieval succeeded; total 5,619ms, HTTP 200. Other reads still
  stalled. Request `9edfa599-5f5a-4f54-ba60-5f80faf2cfd5` also stalled at
  the original Apps Script hop for 20 seconds before its second backend read
  recovered (24,133ms total). The remaining failure is not confined to the
  ContentService hop, and its internal cause is not established.
- No new note, Slack message, summary or action was generated by this test.
  Production log entries from unrelated user writes are not an agent-run
  end-to-end mutation test.

A region-isolation test for only `api/review.js` (Mumbai versus current Virginia)
was proposed to the user and remains unapproved. No region, backend deployment,
access rule, schedule, report metrics or alert delivery was changed. A small
three-request local denied-auth probe returned expected JSON in 1.6–2.4 seconds;
that is only a hypothesis-generating comparison, not equivalent to full data
reads or proof of a regional cause. Further infrastructure changes require the
user's direction. Preserve the existing stop-and-notify safeguards.
