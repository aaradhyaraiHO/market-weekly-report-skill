# Weekly Collection Review — implementation plan

Baseline: canonical `main` at `a0fb19c`. The product contract is
`docs/v2/review-mode.md`. The isolated Review store remains additive and the
weekly analytics, legacy publisher, diagnostic actions, and BigQuery producers
remain unchanged.

| Slice | Live baseline | Current-main-only | This integration | Backend migration | Tests / Preview gate | Decisions |
|---|---|---|---|---|---|---|
| 1. Candidate and shortlist | Alert-derived queue, manual additions, `review_set`, treatments | Responsive CE browser, local status/reason/category filters, far-queue navigation | Present Candidates, Selected this week, Skipped/deferred, and Reviewed using existing treatments; advisory 3–5 count; selected-first Next flow | None | UI contracts, full suite, dense/sparse/global Preview | Limit remains advisory. Nomination cutoff and owner/task-force authority remain product decisions. |
| 2. Slack-first workspace | One stable CE thread, weekly starter, separate Slack composer | Compact Slack status, immediate feedback, drafts | Explicit continue-existing (recommended) versus new-parent choice; new-parent reason and confirmation; linked binding history | Append lifecycle columns to isolated `ce_threads`; run storage installer before backend promotion | Backend/UI contracts, signed read-only Preview checks, controlled mutation only with approval | Reason taxonomy is free text for pilot; governed options remain a product decision. |
| 3. Outcome and completion | Treatment and receipt | Exact treatment guidance and sticky completion state | Not implemented until outcome types and no-discussion contract are confirmed | Additive outcome/approval fields likely required | Completion contracts and authenticated workflow QA | Required: allowed outcome types and who may confirm completion. |
| 4. Timeline and backlog | Notes, Slack summaries, work, receipts, historical comments/performance history | CE Memory fail-soft loading and deduplicated action inbox | Preserve current behavior; chronological unified event projection and ageing views remain missing | Prefer shared sidecar/API projection; no Sheet rewrite | Sparse/dense/duplicate/missing-history contracts | Required: overdue/stale thresholds and authoritative owner/task-force source. |
| 5. Guarded automation | Granola suggestion/reconciliation substrate | Exact-match and approval boundaries | Deferred beta; no automatic Slack writes | Separate service credentials and retention policy | Suggestion-only/idempotency/ambiguity tests | Required: pilot scope, transcript retention, approvers, access policy. |

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
