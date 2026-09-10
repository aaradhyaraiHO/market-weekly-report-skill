# Review proxy read retry

Prepared locally for the coordinating release task; not deployed by this task.

The live read-safe UI recovered via Retry after an intermittent upstream failure. The proxy previously attempted each read only once with no server-side deadline. This update gives GET requests one retry on network/body-read failure, timeout, or HTTP 5xx. Each attempt uses a 20-second AbortController deadline covering both fetch and response-body consumption; the two upstream attempts have a combined 40-second budget inside the client's 45-second selected-CE read timeout. Cold start and client-to-proxy transit are outside that upstream budget.

HTTP 4xx and application-level errors are returned without retry. After two transport/5xx failures, the proxy returns HTTP 502 with `ok: false` and the existing explicit “review backend unavailable” error. Success/error responses are not cached. POST behavior remains single-attempt, including network failure and HTTP 5xx, so the retry cannot duplicate note saves, Slack posts or action changes.

JWT verification, domain restrictions, action allowlist, actor identity/HMAC signing, selected-week parameters, credentials, backend endpoint and POST-only automation bypass remain unchanged. Both read attempts use the same signed URL. No Apps Script, Sheet, HTML, or production deployment changes were made for this patch.

## Evidence

- Proxy SHA256: `b316d0b9bacfe3425641f20225eba2ed0f3850e7498f2ebfc9bed0434ba9242d`.
- `tests/weekly_report/js/review_proxy_runtime.cjs` executes the actual proxy handler with mocked network/JWT boundaries and real HMAC signing. Covers first-network-failure recovery, 5xx recovery, permanent failures, connection/body-read deadlines, timer cleanup, 4xx/application-error nonretry, POST-once behavior, actor-spoof rejection, server-only bypass, auth failures, domain denial, whoami, action allowlist and invalid configuration.
- New unittest wrapper includes these cases in the canonical baseline.
- `verify_baseline.py`: 321/321 passed.
- Proxy syntax and `git diff --check`: passed.

Files: `scripts/weekly_report/notes/review_proxy_api.js`, the two focused runtime test files, and this document. The release coordinator owns API-only staging and deployment while preserving the verified HTML artifacts byte for byte.
