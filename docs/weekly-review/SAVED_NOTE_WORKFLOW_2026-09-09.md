# Saved notes in the selected week's audit

Local follow-up to the coordinated September 9 release. Production was not changed.

Saving a writeup now replaces the editor with the saved note, author, time, Edit,
and Discuss in Slack. Edit saves to the same comment ID; Cancel restores the
saved state. Discuss opens that note in the shared composer for an explicit
Slack send, with the existing continue/new-thread choice. It does not save a
second note. Additional notes remain separate records. Notes from multiple
reviewers remain visible; imported notes retain source attribution and links.

The approved, correctly bound Slack summary is shown directly under Discussion.
The selected week's visible notes, current summary, and actions are excluded
from the repeated memory account. Other current-week context stays accessible;
other weeks remain in collapsed CE memory. Existing records are not moved or
rewritten by this presentation change. Comment reads are scoped to the selected
week and paginated; full CE memory still reads the historical record.

## Backend requirement

Deploy the changed `review_apps_script.js` together with this frontend update.
The existing comment upsert route retains the old text as a `comment_revision`
event in the existing timeline tab before replacing it. Note ID, market, CE,
review week, source attribution, and creation time are retained. An expected
update timestamp and a second check inside the locked upsert reject stale or
concurrent replacement. Failed saves keep the editor's draft. Retries do not
create duplicate revisions. Revision events remain in source history, rather
than appearing as new conclusions in weekly prose.

No new Sheet, tab, schema columns, credentials, or migration are required.
Production v16 can save notes but does not provide the new revision/conflict
behavior; it is not the release target for the completed edit workflow.

## Files changed by this follow-up

- scripts/weekly_report/review/review-view.js
- scripts/weekly_report/review/review-view.css
- scripts/weekly_report/notes/review_client.js
- scripts/weekly_report/notes/review_apps_script.js
- tests/weekly_report/js/mini_audit_runtime.cjs
- tests/weekly_report/mini_audit_preview_server.py
- tests/weekly_report/test_mini_audit_contract.py
- tests/weekly_report/test_review_p0_core_contract.py
- tests/weekly_report/test_review_backend_contract.py
- This note.

These files already contained integrated release work; that work is preserved.
No commit, production deployment, live note edit, Slack message, or Sheet write
was performed for this follow-up. Preview interactions used only local in-memory
service fixtures. The preview injector also refreshed local staged API assets;
no production routes were changed.

## Verification

- `python3 scripts/weekly_report/verify_baseline.py`: all 317 tests passed.
- JS syntax checks for the view, client, and backend: passed.
- `git diff --check`: passed.
- Runtime regressions cover same-ID edits, original text retention, attribution,
  immutable week, replay deduplication, stale/concurrent rejection, failed-save
  draft retention, one composer, selected-week/CE isolation, and inline findings,
  decisions, and open questions. Existing Slack-binding tests still pass.
- Local browser: saved note replaces textbox; Edit loads original text; Save
  changes updates the displayed note; reload retains it; Discuss prepopulates
  the composer; simulated Slack send leaves the saved note intact; simulated AI
  failure/retry retains the note and then renders the approved summary inline.
- Responsive browser inspection: 1280px desktop split layout and 390px mobile
  saved/edit states. Page width matches viewport at both sizes; no horizontal
  overflow. Mobile Save/Cancel controls are 44px tall. Viewport override reset.
- Note and summary metadata use the existing muted text token. No animations,
  icon changes, new styling framework, or extra storage layer were introduced.

Preview: http://localhost:8783/weekly-report-north-america-2026-08-30.html?view=review&ce_id=3111&market=north_america&week=2026-08-30

Live verification of the new edit/revision behavior remains for the next
coordinated release. Existing real records were not used as mutation fixtures.
