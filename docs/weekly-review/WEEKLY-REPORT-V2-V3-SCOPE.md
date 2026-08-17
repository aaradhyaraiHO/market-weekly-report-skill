# Weekly Report V2 / V3 — product scope

**Status:** Proposed for team feedback
**Based on:** Weekly business review discussion, 14 Aug 2026
**Product principle:** Standardize the jobs and outputs of a weekly review, not every market's meeting format.

## 1. Problem to solve

The current report helps a BGM identify CEs that need attention, but the review workflow then splits across the report, market sheets, Slack threads and the weekly call. Context is copied or lost, and actions often resurface only at the next review.

The weekly report should become the CE-level review workspace that connects five jobs:

1. Decide which CEs need attention.
2. Gather stakeholder input before the call.
3. Align on actions, async or sync.
4. Track actions and items that need another look.
5. Preserve a short weekly call for decisions, wins and team context.

The monthly review remains the place for OKR depth, Gantt plans, launches, churn and opportunity discovery. The weekly report is for prioritization, coordination and follow-through.

## 2. Release boundary

| | V2 — Review workspace | V3 — Assisted review loop |
|---|---|---|
| Primary outcome | A BGM can prepare and document the review without maintaining a parallel sheet. | Pre-call input, call notes and follow-through are connected with minimal manual reconciliation. |
| Operating model | Human-operated; the report stores the shared review record. | Human-controlled automation; Slack remains the collaboration interface. |
| Core question | “What needs attention, what did we decide, and what must we revisit?” | “What changed since the decision, who owes an input, and did the action happen?” |
| Release gate | Shared workflow is adopted across differently sized pilot markets. | V2 data is reliable enough to automate matching, reminders and status suggestions. |

## 3. V2 scope — Review workspace

### 3.1 Prioritized review queue

- Preserve the current weekly signal/bucket logic—such as CM2 drop/loss, negative CM2 and RPC movement—as the default way to flag CEs; do not redesign the report's analytical foundation for V2.
- Give each market one review queue containing system-flagged CEs plus manually added CEs.
- Show the trigger, materiality, relevant metrics, existing Slack context and prior-week state together.
- Let markets add custom flags without changing the common default buckets.
- Support both large multi-BGM markets and small single-BGM markets through filters/ownership, not separate product flows.

### 3.2 CE review record

Each CE × week gets three first-class sections:

1. **Commentary / observations** — what happened, hypotheses and stakeholder context.
2. **To-dos** — concise action, DRI, status and optional due/check-in week.
3. **Track next week** — an explicit item to carry into a future weekly review.

Required behavior:

- Multiple stakeholders can be attributed in notes; the BGM is not treated as the only author.
- Notes and actions persist by CE and week and remain visible in later reviews.
- Open to-dos and tracked items automatically carry into the next relevant weekly queue.
- Every item exposes its source and last update; no silent overwrites.
- Completed/deprioritized items remain in history rather than disappearing.

### 3.3 Review-mode UX

- Add a focused review mode over the existing report rather than another standalone tool.
- Allow fast next/previous navigation through flagged CEs.
- Keep the main tables scannable; detailed commentary belongs in the CE drawer.
- Show three compact status indicators in the queue: commentary present, open to-do count, revisit scheduled.
- Provide market/BGM/DRI/status filters and a concise pre-call agenda view.
- Retain links to Omni, source Slack threads and other existing evidence.

### 3.4 Collaboration in V2

- Slack stays the place where Perf, BDM, Ops and other stakeholders respond.
- A BGM can post a CE question or action from the review record into Slack and retain the thread link.
- Responses can be summarized back manually in V2; automatic thread reconciliation is V3.
- The report does not require non-BGM stakeholders to adopt a new task-management interface.

### 3.5 V2 intelligence boundary

- Reuse deterministic flags, metrics, historical trends and already-curated Slack context.
- A short factual data summary may appear inside the CE drawer if it can be generated reliably.
- Do not give AI analysis a permanent table column or ask it to produce full CE-level RCA.
- Recommendations and decisions remain human-authored.

### 3.6 V2 completion criteria

V2 is ready to graduate when pilot markets can:

- Select their review set from system flags plus manual additions.
- Complete commentary, actions and revisit tracking without a parallel weekly sheet.
- Carry open work cleanly into the following week.
- Prepare a usable agenda for both a short async-heavy review and a more discussion-led review.
- Retrieve the decision history for a CE without searching old sheets or call notes.

Validate with at least one large/multi-BGM market and one small/single-BGM market before expanding the scope.

## 4. V3 scope — Assisted review loop

### 4.1 Granola call-note ingestion

- Accept a Granola meeting link and process the notes after the call.
- Match notes to a CE only when the match is unambiguous.
- Present unmatched mentions in a small review queue with a CE dropdown.
- Add concise call notes to the CE record, separate from pre-call commentary.
- Target approximately 60 seconds of BGM reconciliation after a call.

### 4.2 Slack-assisted stakeholder input

- Send structured CE questions or action requests to the relevant Slack channel/thread.
- Pull thread responses back into the CE record as linked summaries.
- Preserve author, timestamp and permalink for every imported item.
- Support automated requests for recurring inputs such as Ops checks, MMP handover status and SP acquisition pipeline updates.
- Never treat a Slack summary as a source without retaining the underlying thread link.

### 4.3 Assisted action follow-through

- Scan linked Slack threads for evidence that a to-do progressed or completed.
- Suggest a status change and cite the message that supports it.
- Allow the BGM to confirm, correct or reject the suggestion.
- Keep unresolved items visible and prepare a next-week follow-up list automatically.
- Add reminders/pings only for explicit actions with a DRI; do not infer ownership from conversation alone.

### 4.4 Lightweight AI assistance

- Produce concise L1 and selective L2 summaries inside the CE drawer using report data and linked context.
- Separate facts, hypotheses and decisions so generated text cannot masquerade as an agreed action.
- Keep summaries short and editable; no long narrative RCA.
- Optionally support voice-to-commentary for post-call capture.

### 4.5 Additional operational context

Bring the following into the CE record only where they improve weekly coordination:

- MMP/iteration handover state.
- Salesforce or SP acquisition pipeline state.
- Availability/supply checks and other recurring Ops inputs.
- Known deliberate actions that explain a metric movement.

These are contextual inputs, not new weekly report sections by default.

### 4.6 V3 completion criteria

- Granola notes can be reconciled in about one minute, with no low-confidence auto-attachments.
- Every imported Slack or call-note claim retains a source link.
- Status automation is a cited suggestion, never an unexplained auto-close.
- Open actions, owners and follow-up items are correctly assembled for the next review.
- BGMs report less manual copying and fewer missed follow-ups without requiring other functions to leave Slack.

## 5. Explicit non-goals for V2 and V3

- Replacing Slack, Hello or a general project-management system.
- Building a market-wide task manager beyond CE-level weekly actions.
- Prescribing one agenda, meeting length or presentation format to every market.
- Eliminating the weekly call; its team-context and camaraderie job remains valuable.
- Full autonomous RCA or auto-generated decisions.
- Automated matching when CE identity is uncertain.
- Moving monthly jobs—OKRs, Gantt planning, launch portfolio, churn and broad opportunity discovery—into the weekly report.
- Rebuilding current bucket logic unless a verified bug blocks the review workflow.
- Partner/vendor dashboards, new-CE growth estimation, campaign categorization or homepage/dashboard navigation work.

## 6. Proposed sequence

1. **Now / P0:** Fix current weekly-report bugs and small usability issues.
2. **V2 prototype:** Validate the queue, three-section CE record and agenda with representative markets.
3. **V2 pilot:** Add persistence, carry-forward, ownership/status filters and Slack thread linking.
4. **V2 rollout decision:** Confirm adoption and field/schema stability before integrations.
5. **V3 pilot:** Granola matching, Slack response sync, cited status suggestions and recurring stakeholder requests.
6. **V3 expansion:** Voice capture, selective L2 summaries and additional operational inputs based on measured usage.

## 7. Decisions needed before V2 build

1. Which current signal buckets form the default review queue, and how are manual/custom flags ranked alongside them?
2. Is the action state model limited to `open / done / deprioritized`, or is `blocked` required?
3. The UI keeps “track next week” distinct; should the underlying schema store it as a separate object or as a to-do with a future check-in week?
4. Who can edit a CE review record, and who can only respond through Slack?
5. Which pilot markets represent the large/multi-BGM and small/single-BGM workflows?

## 8. Source

- [Team-ready summary](TEAM-PING-2026-08-14.md)
- [14 Aug meeting notes](https://notes.granola.ai/t/fd4f510e-e188-40c7-a97a-c27b6d7a8cfe)
