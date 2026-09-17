# Saved-note queue repair — 17 September 2026

## Scope and findings

The screenshot's Tromso Cable Car CE 7416 had stored notes, but the Mini Audit
queue previously used only diagnostic flags and explicit review-set entries.
Opening a CE added a browser-only row. Saving a note did not give it durable
queue membership. A second, independent problem remains: intermittent Google
Apps Script / ContentService response failures.

This change derives additional queue entries from active stored comments for the
exact market and report week. It does not write review-set rows or change flags,
bucket membership, rankings, metrics, attribution or report JSON.

- Existing comments are fetched through the existing authenticated, paginated
  comment-list endpoint; no new permissions, credentials or backend deployment.
- Flags/manual queue rows keep their precedence and order. Commented CEs are
  appended once with “Has saved notes.” The queue is no longer silently limited
  to its first 100 rows; all-CE search retains its existing 100-result limit.
- Successful saves update membership immediately; reload/new browser sessions
  reconstruct it from stored notes. No local storage is used for saved notes.
- Market/week changes discard queue loading state and old manual selections.
  Stale aggregate reads cannot overwrite a save confirmed while they ran or a
  more recent completed CE read. Failed reads retain prior confirmed content.
- Notes show a loading/refreshing state and distinguish “could not load” from
  “no notes.” Saved notes remain expanded. Queue-source failure is visible and
  independently retryable; no successful-fetch claim is inferred from a cache.

## Tests and observations

- 400 unit/runtime tests plus baseline passed before release. Coverage includes
  queue reconstruction in separate client states, deduplication, deleted notes,
  market/week scoping, failed refresh preservation and concurrent save protection.
- Local browser fixture: saved a clearly labeled local-only note on unflagged
  Tromso CE 7416; navigated away to a fresh report URL without a CE selection;
  opened the queue, found “Has saved notes,” selected it, and saw the same note.
  All local integrations were simulated; no test note was sent to production.
- Live before release: Tromso notes initially failed. A read-only Retry returned
  Abhibrata's two existing notes, IDs
  `cmt_92465998-ad43-4be3-a9fd-a4debc5da50a` and
  `cmt_288f7d74-cadf-436e-87f2-ccf11ca5ae2f`.
  Their text was captured through the signed-in DOM for after-release comparison.
- Live backend failures were reproduced on the September 15 deployment. Request
  `6d56cda3-aef2-4b59-87e0-9eb3a1f72bc3` (comment read) failed after 19,419ms;
  `5a89317c-c942-43a6-a225-0a0e09fcda65` (weekly read) after 37,707ms. Existing
  timed retry mitigation is not a complete transport repair.

## Release

Staged complete notebook: `.cache/weekly_report/queue_repair_2026-09-17/notebook`.
Rollback base: `.cache/weekly_report/japan_read_recovery_2026-09-15/notebook`,
deployment `dpl_BHtacc1P4A1ZuCiwuGrGgRmAVacj`.
Only the exact Mini Audit view asset in 105 HTML pages changes; all other 142
files match. Reverse replacement restores the original report bytes. The
adjacent preservation receipt and browser manifest describe this UI-only patch.

Deployed and aliased to production as `dpl_5Di2vJFteteBz29Hfq76FxwqUM82`
(`https://market-notebook-bd9v7uxhw-headout.vercel.app`). Fresh signed-in browser
observations passed fingerprint verification for all 40 manifest routes, including
latest and exact-week reports and both notebook indexes. Evidence is retained in
the adjacent `browser_observations.json` and `browser_verified.json` receipts.

On the new live release, opening the Nordics report without a CE selection loaded
seven commented CEs into the queue, including Tromso CE 7416. Selecting Tromso
showed the two original notes above; their IDs and rendered text matched the
pre-deployment capture exactly. Confirmed notes were expanded, not replaced by
an empty composer. The independent discussion read still timed out during this
test: the queue repair is live, but backend transport reliability is NOT resolved.

The proposed Mumbai-only proxy test still needs user approval; no region or
runtime/backend access configuration is changed here. No production notes,
Slack summaries, alerts, actions, scheduling or snapshots were mutated by this
test. A passing local fixture is not a real new-write end-to-end test.
