# CE Memory proxy-region experiment — 23 September 2026

Status: **retained in production as a measured latency improvement, not a complete backend reliability fix**. The user approved testing only the Mini Audit proxy in Mumbai with rollback if worse/inconclusive. No report regeneration, note creation, Slack delivery, summary generation, scheduling change, formula change or bucket change was performed.

## Deployment

| Field | Result |
| --- | --- |
| Canonical production | https://market-notebook.vercel.app |
| Deployment URL | https://market-notebook-ewwgr15tq-headout.vercel.app |
| Deployment ID | `dpl_89czAkUqH6eFBCtp6MGwxwMeS9ph` |
| Target/status | Production / Ready; canonical hostname freshly resolved to this deployment |
| Source release | `700e9e021aaee669e14afa346cb92b819e24db76`; application code unchanged |
| Framework / build | Static HTML plus serverless APIs / 27 seconds build time |
| Changed file | Only `vercel.json`: `functions.api/review.js.regions = ["bom1"]` |
| Runtime region | `/api/review` verified in `bom1`; inspected actions/auth functions remain `iad1` |
| Rollback | `dpl_HAaCLGngR4HBwzVzk4GFGYpXkc8n` / https://market-notebook-8uo7svts2-headout.vercel.app |

The supported [per-function region configuration](https://vercel.com/docs/functions/configuring-functions/region) isolates the proxy; [Vercel identifies `bom1` as Mumbai](https://vercel.com/docs/regions). No project-wide region change was made. The candidate was built with `--prod --skip-domain`, inspected, and then promoted. The existing middleware edge-runtime deprecation warning remains; it did not fail the build. Observability drains were not inspected or modified.

## Measured comparison

Same signed-in report UI, same September 13 report week, CSEE CE 3286 and Nordics CE 7416. Explicit Refresh requests fetch history afresh; a page reload was also checked. Durations are server request-completion timings, not estimates based on how long browser automation took.

| Proxy | CE Memory completed-request timings | Median | Longest |
| --- | --- | --- | --- |
| Virginia, fresh pre-switch sample | 7,280; 39,132; 8,621; 19,730ms | 14.2s | 39.1s |
| Mumbai, eight new reads | 5,741; 7,800; 7,468; 7,713; 5,025; 6,763; 6,771; 8,109ms | 7.1s | 8.1s |

Virginia request IDs: `7d7a7224-066c-4641-b12e-6d57c482d16d`, `11756bf9-afbd-4f69-ae43-d8c8e7182154`, `2d3f879b-c633-46bb-8c38-585c9be7a135`, `bec1fd07-71eb-48a7-a2ab-6a2844bcf99e`.

Mumbai request IDs: `d3873249-4cf0-48c9-893c-c37ff43f476a`, `af6070e6-f16d-40b8-be6d-90b1f5165b9b`, `afd58d7d-e0ae-44fa-9fed-b4aac3ca1b59`, `aa88341f-0506-4082-abe4-c9790e203fcb`, `4e9093fe-97cc-445d-bc3e-bfa961d9c88a`, `6f42d0fc-8488-42b7-b419-97b1691c8ea9`, `195231a0-ae58-4a50-bfc5-39efe2e4eb77`, `f329c6f3-99a8-42a0-a8b1-b252153f61be`.

All eight Mumbai reads visibly completed. One content-header timeout (`afd58d7d…`) still occurred and was recovered by the existing retry logic. One request's platform HTTP-status field was unavailable/zero even though the application recorded completion and the browser displayed success; it is not counted as an observed HTTP 200. An all-level/status API log scan found four failed HTTP reads in the pre-switch window and none in the candidate sample. These are different-sized, sequential windows, not a matched error-rate experiment.

The smaller latency spread across repeated reads supports retaining this narrow change. It does **not** establish Google's internal root cause, eliminate the 5–8 second read cost, prove write/Slack/summary behavior, or guarantee future reliability. Earlier clean Virginia reads were as low as 4.3 seconds, so do not claim every request became faster. If long stalls recur, the remaining investigation is Apps Script execution/content delivery, not more client retries or weaker authentication.

## Preservation and verification

- Complete notebook file set unchanged: **266 files; only `vercel.json` changed; other 265 byte-identical**. All report/UI/API source bytes and existing monthly/history pages preserved.
- Fresh signed-in browser observations: **40/40 canonical latest/exact-week report routes and ledger/home routes** matched actual DOM data/UI fingerprints and visible market/week. `release_integrity.py browser` accepted the saved observations.
- CSEE CE 3286: all **11 history records** remained identical in DOM text after repeated refreshes and reload.
- Nordics CE 7416: all **3 history records** remained identical to the earlier release's source-record fingerprint: `41a733ec545953cf8e3a6508cb4322c2580dc5976b2566ed98923aed72b9d3cd`.
- Unauthenticated API request still returned HTTP 302 to the existing sign-in route. Signed-in browser reads worked. No credentials were extracted; auth/redirect allowlists/timeouts unchanged.
- Full test suite and baseline verifier passed before the config experiment (401 tests each); no runtime source edits were made.
- A temporary seed/stage rehearsal copied the complete notebook with canonical `release_integrity.seed` and `publish_weekly.stage_v2_proxies`: all file hashes stayed identical and the proxy-only `bom1` setting survived. No report generation or external sends occurred.
- A Nordics deep link briefly displayed “Choose a CE” after its queue loaded; choosing the CE via the queue restored it. This also happened before the region switch and was not changed in this region-only experiment. It is a separate UI follow-up, not evidence that memory records are absent.

## Matching artifact for the next run

While the deployment above remains production, the matching verified complete artifact is:

`/Users/aaradhyarai/market-weekly-report-skill/.cache/weekly_report/proxy_mumbai_test_2026-09-23/notebook`

Despite the directory's test name, this is now the retained production artifact. Sibling receipts: `deployment_receipt.json`, `preservation.json`, `artifact.json`, `browser_observations.json`, `browser_verified.json`, `iad1_request_evidence.json`, `bom1_request_evidence.json`.

The canonical workflow seeds from the current verified complete notebook and checks preservation of `vercel.json`; this is how the region setting carries into later weekly runs. No automation prompt or schedule was changed. Always re-resolve production before the next run; if monthly/other work advances production, use its newer verified complete artifact rather than this one blindly. Preserve this artifact and the previous rollback artifact.

Normal UI telemetry remained enabled. Existing notes/history, snapshots, alert ledger, delivery locks and retry journals were not rewritten; the unrelated `alert/posted_ledger.lock` was untouched.
