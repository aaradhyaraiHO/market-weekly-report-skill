# Mini Audit user-flow test — 9 September 2026

Tested the current saved-note hierarchy through browser controls, using the real report HTML and a separate local fixture server on port 8784. The user's port 8783 session and notes were left intact. No Slack messages, Sheet writes, AI calls, or deployments occurred.

## Browser results

| Journey | Result |
| --- | --- |
| All CEs → search Kennedy → CE drawer → Open Mini Audit | Passed; correct CE and data appeared alongside the audit. |
| Save note → edit → save changes | Passed; one card remained, edited text and attribution visible. |
| Saved note → Discuss in Slack → mention → new thread | Passed against simulated API; prefilled composer, mention preview, explicit new-thread choice and resulting discussion #2. |
| Add writeup → reply in existing thread | Passed routing/UI; default remained Continue #2 and no extra thread was created. See fixture limitation below for summary retention. |
| Summarize → simulated failure → retry | Passed; explicit unavailable message, enabled retry, preserved note, then inline fixture summary. |
| Paste transcript covering Kennedy and Hawaii | Passed UI routing; two CE-specific suggestion links. Extraction itself was simulated. |
| Approve meeting action → Open → Complete → Reopen → Complete | Passed; counts updated immediately and source/owner/due date appeared. |
| Leave CE, return through All CEs, then reload | Passed; edited note and two completed test actions persisted in the fixture process. |
| Chicago CE memory → week of 9 August | Passed; original note, discussion, Performance history with recorded status/owner/update date, and shared follow-through actions displayed. |
| Mobile composer at 390 × 844 | Passed; page width 390, textarea width 354, Slack select and send button both 44px high. Typed and cleared a draft through the UI. |

## Fixes made during testing

- Summary success now says “Discussion updated.” It previously claimed suggested actions existed even when Needs review was zero.
- Saving an action status replaces the previous audit confirmation with the latest result, such as “Marked complete” or “Reopened”. Previously “Approved · moved to Open” could remain after completion. Verified both transitions in the browser.

Only `scripts/weekly_report/review/review-view.js` changed for these fixes. The local preview HTML was refreshed.

## Limits and remaining connected checks

This is a browser workflow test against an in-memory fixture, not a live integration certification or testing with independent BGM participants.

- Real Slack delivery, human replies, permissions, AI summary accuracy, and durable Sheet persistence were not exercised.
- The fixture overwrites weekly summary state on a continued reply. The production handler preserves it unless `operation === new_parent`; this preview cannot certify that live behavior.
- Fixture-generated archive and imported-action records omit some production week/source metadata, producing “Week unavailable”. Historical memory rendering was verified with the richer Chicago fixture; new-thread archive provenance still needs a connected check.
- Repeat-import deduplication is covered by the executable backend/runtime regression suite, not this simplistic browser fixture, which recreates fixed suggestions on each import.
- Next-week generation was not rerun in this UI test. Existing packaging and runtime checks run as part of the full baseline suite.

No production release was performed. Test data is isolated in the port 8784 process and can be discarded by stopping that process.
