# Weekly Collection Review — implementation plan

Baseline: canonical `main` at `a0fb19c`. The product contract is
`docs/v2/review-mode.md`. The isolated Review store remains additive and the
weekly analytics, legacy publisher, diagnostic actions, and BigQuery producers
remain unchanged.

| Slice | Live baseline | Current-main-only | This integration | Backend migration | Tests / Preview gate | Decisions |
|---|---|---|---|---|---|---|
| 1. Candidate and shortlist | Alert-derived queue, manual additions, `review_set`, treatments | Responsive CE browser, local status/reason/category filters, far-queue navigation | Implemented in `b0283e6`: Candidates, Selected this week, Skipped/deferred, and Reviewed use existing treatments; advisory 3–5 count; selected-first Next flow | None | Contracts and full suite pass; complete local artifact preflight passes | Limit remains advisory. Nomination cutoff and owner/task-force authority remain product decisions. |
| 2. Slack-first workspace | One stable CE thread, weekly starter, separate Slack composer | Compact Slack status, immediate feedback, drafts | Implemented in `b0283e6` and `224be69`: explicit continue-existing (recommended) versus new-parent choice; reason and confirmation; linked history; Slack-first layout | Append lifecycle columns to isolated `ce_threads`; run storage installer before separately approved backend promotion | Backend/UI contracts pass; authenticated mutation gate waits for backend promotion approval | Reason taxonomy is free text for pilot; governed options remain a product decision. |
| 3. Outcome and completion | Treatment and receipt | Exact treatment guidance and sticky completion state | Implemented in `7a0e1b4`: additive approved CE/week outcome, explicit no-discussion decision, server-enforced suggestion triage and work carry-forward gates | New `review_outcomes` tab plus appended work fields; run isolated storage installer only after approval | Backend/UI contracts pass; authenticated mutation QA awaits paired backend/Preview approval | Pilot UI exposes neutral types; final allowed outcome taxonomy and completion-evidence approvers remain product decisions. |
| 4. Timeline and backlog | Notes, Slack summaries, work, receipts, historical comments/performance history | CE Memory fail-soft loading and deduplicated action inbox | Implemented in `c9f5089`: shared stable-ID timeline projection, read-only history events, seven backlog views, explicit overdue/stale/carry-forward foundations, nomination reason/event, conditional owner/task-force filters | New `review_timeline_events` tab and appended work fields; no historical Sheet rewrite | Sparse/dense/global, duplicate and missing-history contracts pass | Stale is explicit until a threshold is approved; authoritative owner/task-force metadata remains optional. |
| 5. Guarded automation | Granola suggestion/reconciliation substrate | Exact-match and approval boundaries | Implemented safely in `451c77b`: additive provenance/idempotency, human-approved measured-outcome event contract, fail-soft pilot telemetry; Granola remains inactive and cannot auto-post Slack | New telemetry tab and additive source columns; credentials/activation remain separate | Exact-match, ambiguity, idempotency, no-auto-Slack and telemetry contracts pass | Required: pilot scope, transcript retention, approvers, access policy, and automation activation approval. |

## Release state labels

- **Live:** isolated Review backend currently deployed from `d69c51d` and the
  previously deployed complete report.
- **Current-main-only:** reviewed code in canonical main but not production.
- **Missing:** intentionally not guessed from the final product contract.
- **Preview gate:** always a complete 17-market plus Headout current-and-dated
  Market Notebook V2 artifact; never an isolated Review artifact.

## Hard release boundaries

- Do not couple Review to `publish_weekly.py`.
- Do not modify `scripts/weekly_report/notes/apps_script.js`, `/api/actions`,
  `action_upsert`, or `action_delete`.
- Do not regenerate analytics merely to test Review.
- Isolated backend promotion and production site deployment require separate
  explicit approvals.

## Additive isolated-backend migration

Before any paired Preview activation, update only the isolated Review Apps
Script, then run `installReviewStorage()` once. It appends/creates
`review_outcomes`, `review_timeline_events`, `review_pilot_telemetry`, CE-thread
lifecycle columns, work/backlog fields, and source-provenance fields. Existing
rows and legacy Notes/actions storage are not rewritten. Rollback is code-level:
the prior isolated deployment remains selectable and additive Sheet columns can
remain unused without affecting old readers.
