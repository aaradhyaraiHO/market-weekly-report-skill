# Mini Audit live repair — 14 September 2026

## Status and boundary

The Actions read-timeout mismatch is fixed and deployed. A genuine new-note,
Slack-reply, new-summary and reload cycle passed on CSEE CE 3286. This is **not a
claim that intermittent backend failures have been eliminated**: one summary
attempt returned a backend identity-verification error, and a later suggestions
read failed before succeeding on explicit retry. Neither failure lost the saved
note or summary. The authentication failure's cause remains unconfirmed.

No BQ regeneration, metric/bucket edits, weekly alert replay, scheduling change,
Apps Script deployment, or historical report-data rewrite was performed by this
repair. Unrelated Monday generation changes remain separate.

## Confirmed defect and change

`review_client.js` previously gave `work()` the generic 15-second read deadline,
although the proxy permits two 20-second GET attempts. A regression using the
actual client reproduces the premature abort. Work reads now allow 45 seconds,
including each paginated request. An explicit retry bypasses cached pages.

The Actions view displays the actual escaped error and retry progress; a failed
refresh retains previously loaded work. Backend signature rejection now logs
only the action name and elapsed time. Authentication checks and mutation retry
rules are unchanged; no request bodies, credentials, or identities are logged.

## Live evidence

- Report: [CSEE CE 3286, week 6 September](https://market-notebook.vercel.app/weekly-report-csee-nordics-2026-09-06?view=review&ce_id=3286&market=csee&week=2026-09-06).
- Existing test thread: [Slack discussion](https://headout.slack.com/archives/CSQ10TALA/p1789016453095459).
- One explicitly labelled `MA-0914` dummy note saved at 12:40 IST. Its initially
  slow acknowledgement was reconciled by a durable-ID read, not another POST.
- Two distinct test replies were sent, each exactly once. Independent Slack
  thread read-back found one initial test reply and one follow-up, with no more
  pagination. Existing replies were retained.
- After the initial summary error, explicit approval succeeded. A subsequent
  genuinely new follow-up was summarized and automatically approved at 12:53
  IST, with the observation and decision present in the saved summary.
- Reload preserved the exact current note and saved-summary text. Repeating
  summarization with no new source left the saved summary unchanged.
- One test-only suggested check was dismissed, not approved as business work.
  Final loaded Actions state: Needs review 0, Open 0, Completed 0.
- The prior-week CSEE CE 3286 Mini Audit's complete rendered main text matched
  its before-test text exactly, including the September 10 notes and summary.

## Deployment and preservation

- Original Monday deployment / rollback: `dpl_772Uu7ugvSoQKseNW1Xy67ZNvfTp`.
- Client/view repair deployment: `dpl_Ew85JM74rVCFj5tgZyKW9H5fSXma`.
- Current deployment including safe backend-auth diagnostics:
  `dpl_At9XbWMTf5DYWFuhK9uub2t3GzpF`.
- Frozen notebook: `.cache/weekly_report/action_load_diagnostics_2026-09-14/notebook`.
- Two exact inline assets were replaced in 105 report HTML files. Reversing
  those replacements recovered the original bytes, preserving all report data.
  Preservation receipt: `.cache/weekly_report/action_load_fix_2026-09-14/preservation.json`.
- The diagnostics-only deployment retained all 230 staged HTML pages byte for
  byte. Receipt: `.cache/weekly_report/action_load_diagnostics_2026-09-14/notebook_receipt.json`.
- Fresh signed-in browser checks covered 40 routes: index, weekly, and current
  plus dated routes for 17 markets, Headout and the shared CSEE/Nordics page.
  Every observed route and payload/code/style fingerprint matched the staged
  browser manifest. Observed 07:23:13–07:26:50 UTC on 14 September, after the
  final deployment. SHA-256 of the sorted `[file, fingerprint]` pairs:
  `d36d9a02edc0b51a2a1ea1fbb42b247614d05eabd48bb727686d7732676cabdf`.
  This is an aggregate browser verification record, not a replacement for a
  new-delivery release manifest or authorization to send alerts.

## Verification limits

All 397 weekly tests passed on the integrated checkout, and baseline verification
and `git diff --check` passed. The integrated checkout includes unrelated local
Monday changes; this count is not presented as an isolated-commit test count.

The regression suite validates deadlines, pagination, cache bypass, read-only
retries, source errors and retention of existing work. Live evidence validates
the completed test cycle, not zero future service errors. Do not label Mini
Audit 100% reliable while the intermittent backend read/authentication failures
remain unexplained. No retry of a mutation should be added without durable
reconciliation and idempotency verification.
