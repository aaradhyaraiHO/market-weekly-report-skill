# Recurring weekly release closeout — 15 September 2026

## Scope and evidence

The user authorized committing/pushing Monday's two recovery fixes, verifying
the next-run notebook base, and replacing the one-off Codex task with recurring
Monday 07:00 Asia/Kolkata runs. No reports are regenerated or deployed, and no
Slack alerts are sent as part of this closeout.

- Headout now builds the local CE lookup before attaching market labels after
  finalization. Tests preserve metric values, bucket rows and ordering.
- A genuine zero prior-week revenue gets factual amounts/dates and explicit
  N/A WoW/driver attribution. Missing or non-finite source data does not receive
  this treatment. Positive baselines retain the shared diagnosis engine.
- Mini Audit client/proxy repair is already committed in `e0f82b5` and deployed.
- The September 6–12 supervised release was recovered and its 40 exact-week
  routes verified. Final fresh Slack read-back verified all 18 destinations:
  36 parents and 167 RCA replies, no missing/failed RCA. Receipts are in
  `.cache/weekly_report/v2_package_2026-09-06/` (`live_verification.json` and
  `final_slack_readback.json`). The original failed runner receipt is preserved,
  not relabelled as a clean unattended pass.
- Completion was 12:20 IST on September 14, later than the 11:00 target. The
  latest Mini Audit repair passed a separate genuine new-source live test;
  see `mini-audit-transport-hardening-2026-09-14.md`.

## Verified initial preservation base

On September 15, read-only Vercel inspection resolved the production alias
`https://market-notebook.vercel.app` to ready deployment
`dpl_9VYZq6fHfkXXLgjD5u82t3ZqE5Sk`.

Its complete local artifact is:

```
/Users/aaradhyarai/market-weekly-report-skill/.cache/weekly_report/review_redirect_complete_2026-09-14/notebook
```

It contains 230 HTML pages, including 105 with the exact current Review client.
Its `api/review.js` equals the repository's proxy byte-for-byte, SHA-256
`ba56478cf97d19ba0aba3fafeafd4f54a3c149468c4b1b79753f486f07d76113`.
The adjacent `preservation.json` records the final repair's unchanged pages.
Publishing stages the current repository proxy and Mini Audit client; it does
not require another backend deployment to retain the existing backend v21.

This is the **initial** baseline, not a permanently pinned old notebook. Before
every run, resolve the current production deployment and its verified complete
artifact. If production has changed, use the newer artifact only when its
deployment/preservation receipts establish the match. If the matching complete
artifact cannot be established, stop; never silently use this older base.
After a successful run, retain its artifact and deployment/verification receipts
so the next run preserves that notebook, including any intervening monthly work.

## Recurring Codex task contract

Update the existing thread-attached task
`weekly-market-reports-monday-readiness`, not a second scheduler. Run Mondays at
07:00 Asia/Kolkata, starting September 21. The Mac must be awake, connected,
with Codex running and the user's signed-in browser available. An expired
session or access failure stops for user attention, not an authentication bypass.

For each scheduled Monday, compute and pin the most recently completed
Sunday–Saturday report week using Asia/Kolkata. September 21 therefore reports
September 13–19. Never fall back to an older week or treat a partial preview as
completed. Late retries retain their originally pinned week and frozen package.

Use the canonical no-write plan first, with the verified production base and a
separate empty staging destination. Then run the user-authorized generation,
full-notebook deployment and all-market plus Headout alerting through
`run_v2_release.py --deploy --post-alerts`. Preserve CSEE/Nordics' current shared
page/two-dataset behavior. Do not change metrics, buckets, source formulas or
historical reports; do not make unreviewed code fixes during scheduled runs.

Require baseline/parity, source availability, Google/Bing current/comparison
field checks, all required RCA preparation, preservation, exact-artifact browser
verification and final Slack read-back. Optional unavailable source fields remain
explicitly unavailable; missing required evidence fails closed. Use real browser
observations, never copied proof from a previous release.

After the browser handoff, resume the receipt's verification and immutable
delivery commands, not generation/deployment. Keep locks, ledgers and journals.
Reconcile uncertain writes; never force-repost or clear state. For an already
completed week, verify existing evidence and exit without new sends. A concurrent
run, unknown partial state, code divergence, expired access or failed gate stops
with the precise blocker and preserved recovery state. Routine unchanged status
is quiet; completion, failure or required user action is reported. Completion
includes per-market parent/RCA coverage and elapsed time against the 11:00 target.

## Local verification

The two targeted test modules pass (5 tests). The complete weekly suite and
baseline verification pass (397 tests each). `git diff --check` passes.
A no-write September 13 plan includes all 17 markets plus Headout, the repaired
base, browser verification and frozen delivery in order; its destination does
not exist yet. This plans the September 21 run only; it does not execute the
currently incomplete September 13–19 week early.
