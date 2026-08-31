# Review UI-first control inventory

Scope: deterministic local fixture only. No control in this artifact calls an API, Apps Script, Slack, Sheets, Preview, or production. CE Memory is intentionally retained unchanged as the future read-only history surface.

## CE queue and nomination

| Visible control | BGM intent | Local behavior | Classification |
| --- | --- | --- | --- |
| Search CE name or ID | Find a queued or unlisted market CE | Filters the queue and a deterministic market CE directory immediately by partial name or stable CE ID; it never nominates an ambiguous first match | Working locally |
| Available to add result | Find a CE not yet in the review queue | Shows the exact matching CE with stable ID, prior-review context, and its own Add CE action | Working locally; fixture-backed |
| Add CE on a candidate | Nominate that exact CE | Moves the explicit stable-ID row to Selected this week and opens it | Working locally |
| CE row | Open a CE workspace | Changes the selected CE without navigation or network work | Working locally |
| Defer on selected CE | Remove from this week's shortlist | Moves CE to Skipped / deferred without deleting it | Working locally |
| Reopen on deferred CE | Return it to the shortlist | Moves the exact CE back to Selected this week | Working locally |
| Review-history line | Understand recency and ownership | Shows Last reviewed date + BGM, Reviewed date + BGM, or Never reviewed | Working locally; fixture-backed |
| Browse/search CEs / Close | Use the queue at narrow width | Opens and closes the local CE browser | Working locally |
| Clear search | Restore the complete queue after name/ID/zero-result search | Clears explicit local query state immediately while preserving CE selection, URL CE context, and CE-scoped drafts | Working locally |

## Review path and Slack discussion

| Visible control | BGM intent | Local behavior | Classification |
| --- | --- | --- | --- |
| Review path select | Choose live/async/follow-up/skip treatment | Updates finish readiness locally | Working locally |
| Retry | Retry failed thread discovery | Shows checking, then deterministic prior-thread result | Working locally |
| Start Slack discussion | Begin the first CE thread | Opens a working message composer; no post occurs | Working locally |
| Continue Slack discussion #N | Add a message to the exact bound thread | Opens a working message composer and updates the numbered discussion locally | Working locally |
| Start a new discussion | Create a new parent discussion | Opens reason + message + channel/mention preview + confirmation | Working locally |
| Cancel composer | Leave Slack draft flow | Closes composer without creating a discussion record | Working locally |
| Add message / Confirm new discussion | Simulate posting | Creates or updates numbered local discussion records | Working locally, zero writes |
| Slack discussion link | Inspect source thread | Uses a local fragment placeholder in the fixture | Local demonstration only |
| Summary Approve/Edit/Save/Cancel/Dismiss/Retry/Regenerate | Review the discussion summary | Transitions summary states locally | Working locally |
| Discussion-bound summary | Identify the exact evidence source | Every summary carries discussion ID, stable CE ID, market and week; an older approved summary remains previous confirmed context | Working locally |

Deterministic states: `loading`, `failure`, `none`, `prior`, `current`, `startnew`, and `multiple` via `?scenario=<state>`.

## BGM observation

| Visible control | BGM intent | Local behavior | Classification |
| --- | --- | --- | --- |
| BGM observation · Optional | Keep optional context visible without competing with Slack | Always-visible compact surface directly beneath summaries | Working locally |
| Add observation | Create BGM context | Opens and focuses the local editor in one click | Working locally |
| Save observation | Keep the note | Renders note with fixture author and time | Working locally, zero writes |
| Edit | Change saved context | Reopens saved text | Working locally |
| Cancel | Abandon current edit | Restores the previously saved note | Working locally |
| Historical Performance/BDM notes | Inspect compatibility history | Native read-only disclosure | Working locally; read-only fixture |

## Actions and follow-ups

| Visible control | BGM intent | Local behavior | Classification |
| --- | --- | --- | --- |
| Needs review / Open / Later / Completed tabs | Inspect one work state | Switches local lists immediately | Working locally |
| Suggestion Approve | Commit an AI/Slack suggestion | Moves complete suggestion to Open or Later | Working locally |
| Suggestion Edit | Correct text/owner/date before approval | Opens one inline editor | Working locally |
| Suggestion Reject | Decline suggestion | Removes it from Needs review only | Working locally |
| Suggestion Save & approve / Cancel | Commit or abandon edits | Creates committed local work or restores suggestion | Working locally |
| + Add action | Draft manual BGM work | Opens the native inline editor directly below the trigger without moving document scroll; opening creates zero rows | Working locally |
| + Schedule check | Draft a future check | Opens the same below-trigger editor with Later semantics | Working locally |
| Create action / Schedule check | Commit manual work | Validates text and owner, then creates exactly one local row | Working locally, zero writes |
| Manual Cancel | Abandon creation | Closes editor without changing counts | Working locally |
| Committed-work Edit | Change text/owner/date/status | Opens inline editor inside the row | Working locally |
| Save changes / Cancel | Apply or abandon work edits | Re-groups by status or restores prior row | Working locally |
| Checkbox | Complete work | Moves row to Completed; checked control becomes Reopen | Working locally |
| Reopen | Undo completion | Moves row back to Open | Working locally |

## CE Memory and finish

| Visible control | BGM intent | Local behavior | Classification |
| --- | --- | --- | --- |
| Open CE Memory | Inspect read-only history | Opens the existing fail-soft drawer | Preserved, working locally |
| Close CE Memory | Return to Review | Closes drawer without changing Review state | Preserved, working locally |
| Finish checklist links | Resolve remaining treatment/suggestion blockers | Focuses the actual local control | Working locally |
| No-discussion reason | Finish without Slack when explicitly justified | Opens only from the finish blocker, validates a concise reason, and remains CE-scoped | Working locally |
| Finish review | Complete the fixture review | Requires treatment, Slack or explicit exception, and suggestion triage. Open/Later work is managed through each row’s owner, date and status; there is no bulk acknowledgement. | Working locally |
| Overview / All CEs rail items | Preserve authentic report-shell context | No alternate fixture views are built | Deliberately nonfunctional shell reference |

## Removed as nonessential in this phase

- Market backlog and Monday reconciliation disclosure and its seven filters.
- Redundant queue status filters that were not part of the nomination workflow.
- The vague bulk `Manage / carry forward` acknowledgement and its completion blocker. It did not prove that individual work had a valid owner, date, or status.
- The no-Slack exception fixture from the core UI walkthrough; it remains a later finish-policy decision, not default workflow chrome.

CE Memory, historical read-only notes, the authentic report rail, and the locked visual treatment were retained.
