# Weekly Report V2 — Weekly Collection Review

Status: build-ready product specification, updated 2026-08-28 from the
authenticated live North America Review and the integrated `main` candidate.

## Product definition

Weekly Collection Review helps a BGM decide which Combined Entities (CEs) need
attention, move the cross-functional discussion to Slack, approve the useful
outcomes, and retain a durable record of what was tried and whether it worked.

The operating model is deliberately simple:

```text
Review identifies and prioritizes
        -> Slack hosts the discussion
        -> AI proposes summaries and actions
        -> BGM approves or edits
        -> Review stores CE memory and open work
        -> later metrics show whether the intervention worked
```

Review is downstream of the canonical weekly report. Review, Slack, AI, history,
or Granola failures must never block, alter, or republish weekly analytics.

## Product principles

1. The BGM is the moderator and final owner of the weekly shortlist.
2. Alerts and team nominations create candidates; they do not dictate the agenda.
3. Slack is the cross-functional discussion surface.
4. Review is the prioritization, approval, memory, and action-control surface.
5. AI removes transcription work but never silently becomes human judgment.
6. One CE has one stable identity and a continuous, source-linked history.
7. Actions from every source enter one backlog rather than separate Slack,
   Granola, Performance, and BGM backlogs.
8. Weekly workload stays bounded: normally three to five selected CEs per BGM or
   task force, with explicit carry-forward exceptions.
9. The weekly ritual remains even when most detailed discussion is asynchronous.
10. Market configuration may differ, but identity, authorization, provenance,
    and action-state contracts do not.

## Current live baseline

The authenticated North America production report for week `2026-08-16`,
inspected on 2026-08-28, currently provides:

- a Review tab inside the complete Market Notebook V2 report;
- an alert-derived queue (48 CEs in the observed North America report), plus
  manual CE additions;
- CE search and stable CE IDs;
- review treatments: `not_scheduled`, `live`, `async`, `follow_up`, and `skip`;
- one BGM note per market × CE × week;
- one persistent Slack discussion thread per market × CE, with weekly starter
  boundaries and a stored permalink;
- automatic and on-demand Slack reply summarization into findings, decisions,
  and open points;
- source-derived action/check suggestions that require human acceptance;
- structured actions and scheduled checks with status, owner, dates, edit, soft
  delete, and carry-forward;
- a review receipt and next-CE flow;
- CE Memory containing weekly notes, Slack summaries, work, receipts, and
  source-linked history;
- read-only historical Performance actions when the sidecar is available;
- Review-to-CE-drawer and CE-drawer-to-Review navigation;
- authenticated BGM/GM/admin access through the isolated Review proxy; and
- isolated Review Apps Script/Sheet storage, separate from legacy diagnostic
  notes and `/api/actions` routes.

The integrated `main` candidate additionally contains responsive CE browsing,
local status/reason/category filters, independent queue scrolling, clearer
completion guidance, progressive CE Memory loading, hidden action trace details,
and suggestion deduplication. These improvements are not treated as production
behavior until the complete site is explicitly deployed and verified.

## Current gaps this specification resolves

The current live product is functional but does not yet implement the intended
weekly operating model:

- every flagged CE enters one large queue; candidates and the BGM shortlist are
  not clearly separated;
- `not_scheduled` dominates the queue and does not communicate whether the BGM
  has considered the CE;
- the Slack action is present, but the page still visually encourages in-app
  commentary before discussion;
- Performance and BDM note inputs create the impression of a second discussion
  destination;
- completion is driven mainly by treatment/receipt state rather than a captured
  outcome and triaged suggestions;
- the live action suggestion UI can expose internal source identifiers;
- CE history exists in multiple blocks but is not yet a single business timeline
  connecting signal, discussion, decision, action, completion, and metric outcome;
- ageing, overdue, stale, and cross-week backlog management are incomplete; and
- Granola is not ready to be a core launch dependency.

## Users and authorization

### BGM

The BGM can:

- review automated candidates and team nominations;
- select, defer, skip, or remove CEs from the weekly shortlist;
- start or continue the authoritative Slack discussion;
- add an optional BGM observation;
- approve, edit, merge, or reject AI suggestions;
- create, assign, update, dismiss, and complete work;
- approve the weekly outcome; and
- finish or reopen a CE review.

### Performance, BDM, and BizOps

These roles can:

- nominate a CE for BGM consideration;
- participate in the relevant Slack thread;
- view approved Review context within their authorized market scope;
- respond to or provide evidence for assigned actions; and
- update an assigned action only when the access model explicitly permits it.

They are not expected to duplicate Slack discussion in role-specific Review
textareas. Existing Performance/BDM notes remain readable for compatibility but
are collapsed and removed from the normal authoring path.

### Admin

An admin can configure access, owner mappings, task forces, Slack routes, and
operational diagnostics. Slack-channel membership alone never grants Review
access.

### Access contract

- The report session supplies verified Google identity.
- The isolated Review backend enforces active BGM/GM/admin market scope.
- Service identities may ingest suggestions but cannot impersonate a person.
- Every mutation records the verified actor.
- Market and CE scope are verified server-side before data is returned or changed.
- Legacy diagnostic action authorization and routes remain unchanged.

## Weekly workflow

### 1. Build the candidate inbox

Candidates originate from:

- Losing Money and RPC/CM1 diagnostic signals;
- other approved weekly report signals;
- BDM, Performance, or BizOps nominations submitted by the cutoff;
- a BGM manual addition; and
- unresolved work or a follow-up carried from an earlier week.

Each candidate shows:

- CE name and stable CE ID;
- market, BGM/BDM/Performance ownership when available;
- why it was flagged and the important metric movement;
- lifecycle/category and current business scale;
- last reviewed date and current cooldown;
- open/overdue work;
- active Slack-thread state; and
- source of the candidate.

Alerts remain read-only evidence. Candidate handling cannot change canonical
bucket membership or metric calculations.

### 2. BGM creates the shortlist

The Review queue is divided into:

- **Candidates** — not yet considered for the week;
- **Selected this week** — `live`, `async`, or `follow_up` treatment;
- **Skipped/deferred** — considered but not selected; and
- **Reviewed** — completed with a receipt.

The existing `review_set` record and treatment values remain the initial storage
contract. No migration is required to introduce the visible candidate/shortlist
separation.

The interface recommends a shortlist of three to five CEs and highlights repeated
hero selection, recent-review cooldowns, smaller overlooked CEs, and carried work.
These are decision aids only; the BGM retains final authority.

### 3. Start or continue Slack discussion

When no authoritative CE thread exists, the available CTA is **Start Slack
discussion**. When prior discussion exists, the BGM chooses between:

- **Continue existing discussion** — recommended and shown with the previous
  thread date, summary, open work, and permalink; or
- **Start a new discussion** — a secondary action available at the BGM's
  discretion when the issue, owner/scope, channel, or review context warrants a
  new parent thread.

The product must neither force reuse merely because a binding exists nor create a
new parent merely because the report week changed. Starting a new discussion
requires a lightweight reason and confirmation. The old and new bindings remain
linked in CE Memory with the acting BGM and both permalinks. Continuing reuses the
existing binding and creates at most one idempotent weekly starter/re-entry
message to define that week's summary window.

The starter preview contains:

- CE and stable ID;
- review reason and minimum relevant evidence;
- BGM, BDM, Performance, or BizOps mentions resolved through governed identity
  mappings;
- previous outcome and open work; and
- a deep-link to the exact market/week/CE Review state.

Posting requires an explicit preview/confirmation, stable idempotency key, known
market channel, and resolved mentions. Ambiguous names fail closed. The returned
thread timestamp and permalink are retained.

### 4. Capture discussion outcomes

The five-minute Slack sync and on-demand summarization retain attributed human
replies and propose:

- findings;
- decisions;
- open points;
- actions; and
- scheduled checks.

The source thread remains the evidence. The summary is a compact, source-linked
representation, not a replacement transcript.

### 5. BGM approves suggestions

Every AI-derived item begins as `pending`. The BGM can accept, edit, merge,
reject, or defer it. Only approved items become authoritative commentary or work.

The suggestion inbox:

- deduplicates with stable source/idempotency keys and normalized content;
- hides raw source IDs behind optional trace details;
- separates Suggested, Accepted/open, and Archived;
- expands only the item being reviewed; and
- never infers an owner from Slack membership or free-text mentions.

### 6. Finish the CE review

A CE is ready to finish when:

- the BGM selected a treatment;
- a Slack discussion exists, or the BGM explicitly chose a no-discussion outcome;
- a concise decision/outcome is present, including `no action needed` when valid;
- pending action/check suggestions have been accepted, merged, rejected, or
  deferred; and
- unresolved work has an owner/check date or an explicit carry-forward state.

A BGM note is optional and cannot be a completion requirement. Finishing writes
one receipt while open work continues independently into later weeks.

### 7. Monday reconciliation

The next weekly cycle shows:

- actions completed since the prior review;
- still-open, blocked, overdue, and stale actions;
- explicit Slack evidence suggesting completion;
- CEs needing another review; and
- metric movement since the intervention.

AI may suggest completion from explicit evidence, but the pilot requires a human
to confirm it.

## Review UI information architecture

### Weekly header

Show market/week, task-force or owner filter, candidates, selected count,
reviewed progress, and open/overdue actions.

### CE browser

Support immediate local search by CE name or stable ID and filters for candidate,
selected, in progress, reviewed, reason, category, owner, and task force.

Desktop can retain a bounded independently scrolling queue. Narrow layouts show
the selected CE immediately and place browse/search/filter controls in an
on-demand panel. Selecting a far-queue CE must never scroll the document away
from the main workspace.

Each row has one primary selection control plus a separate CE-detail/drawer
control. Nested interactive elements are prohibited.

### Selected CE workspace

Order the surface as:

1. **Why this CE** — signal, metrics, ownership, prior-review context.
2. **Slack discussion** — status, channel preview, primary CTA, compact summary.
3. **Current outcome** — approved BGM decision/observation, optional BGM note.
4. **Actions and checks** — suggested, accepted/open, blocked/overdue, archived.
5. **CE Memory** — progressive read-only timeline and source links.
6. **Finish and next CE** — sticky but non-obscuring completion state.

Navigation-only actions render immediately and do not wait for network requests.
Unsaved local drafts survive CE switches, drawer round trips, filters, and Review
tab navigation.

## CE history and memory

The required end state is one chronological CE timeline answering:

> What went wrong, what did we observe, what did we try, who owned it, what
> happened, and did the economics improve?

Material event types include:

- signal triggered;
- candidate created or nominated;
- selected, skipped, or carried forward;
- Slack discussion started/continued;
- Slack or Granola summary approved;
- BGM observation or decision recorded;
- Performance diagnosis retained;
- action/check proposed, accepted, updated, blocked, completed, or dismissed;
- completion evidence added;
- review finished/reopened; and
- later RPC, CM, ROI, or revenue outcome attached.

All joins use stable CE IDs. Names are display fallbacks only. Raw Slack and
meeting content remains linked evidence; the normal timeline shows concise,
approved material events.

### Timeline event contract

```text
event_id
market_slug, ce_id, ce_name
review_week, event_type
source_type, source_ref, source_url
actor_id, actor_name, actor_role
occurred_at, recorded_at
original_body, approved_body
approval_state, approved_by, approved_at
related_review_id, related_work_id
supersedes_event_id
```

Events are append-only. Corrections supersede prior events; deletion is a
tombstone. History loads fail-soft and never blocks the current report.

The current isolated Sheet remains the operational store during the pilot.
PostgreSQL migration should preserve the same stable IDs and event semantics and
should not be coupled to the first UX iteration.

## Unified action backlog

Slack-derived, Granola-derived, Performance-originated, and manually created work
all enter one backlog.

### Work contract

```text
work_id
market_slug, ce_id, ce_name, origin_week
kind (action | check)
text, requester_id, owner_id
created_at, due_date, next_review_date
status, latest_update
source_type, source_ref, source_url
expected_effect, completion_evidence, measured_outcome
approval_state, approved_by, approved_at
idempotency_key, duplicate_of, parent_work_id
deleted_at, deleted_by
```

### States

```text
proposed -> accepted -> open -> complete
                    |-> blocked
                    |-> monitoring
                    |-> no_action_needed
                    |-> stale
                    |-> dismissed
```

The primary backlog views are Needs approval, Open, Mine, Blocked/overdue,
Stale, Recently completed, and Archived.

Rules:

- carry open work forward without recreating it;
- deduplicate retries and equivalent source suggestions;
- require owner confirmation for accepted actions;
- permit ownerless scheduled checks only when explicitly intended;
- surface ageing and overdue state;
- suggest completion only with source evidence;
- keep old completed/dismissed work out of the primary workload; and
- do not turn every observation into an action.

## Granola boundary

Granola is a guarded beta, not a dependency for the core Slack-first pilot.

When enabled, it must:

- ingest through a server-side integration;
- retain meeting ID, source URL, author, time, and access scope;
- match exact CE IDs first and governed names/aliases only as candidates;
- send ambiguous/unmatched records to a reconciliation inbox;
- create pending suggestions, never approved history or Slack posts;
- use stable source-derived idempotency keys; and
- require the BGM to accept or edit before publishing.

No Granola-derived content may automatically notify Slack.

## Data and integration ownership

- **Weekly report/BigQuery:** authoritative CE identity, metrics, diagnostic
  membership, and evidence.
- **Slack:** authoritative cross-functional conversation and source replies.
- **Granola:** meeting transcript source when the guarded beta is enabled.
- **Isolated Review backend:** shortlist state, BGM notes, approvals, summaries,
  work, receipts, thread registry, and CE Memory during the pilot.
- **Legacy diagnostic service:** existing V1/V2 diagnostic actions only; it is not
  a Review backend.

Review never calls or modifies `action_upsert` or `action_delete`. The legacy
`/api/actions` behavior, `publish_weekly.py`, and `notes/apps_script.js` remain
outside this product slice.

## Reliability and latency

- Overview/All CEs/Review navigation, CE selection, drawer opening, and CE focus
  update locally and immediately.
- Every asynchronous action shows immediate pending feedback and deduplicates
  repeated clicks.
- Identity/access is prefetched; CE history is cached by market × week × CE.
- Repeated requests are debounced and stale CE responses are ignored/cancelled.
- Optimistic action creation reconciles or rolls back after persistence.
- Slack, AI, Granola, and history delays show explicit fail-soft states.
- A missing optional source cannot block selection, analytics, or completion with
  an explicitly recorded fallback outcome.

## Two-week pilot

### Included

- candidate versus selected-this-week presentation;
- BGM selection and bounded-shortlist guidance;
- owner/task-force filters where metadata exists;
- Start/continue Slack as the dominant CTA;
- optional BGM observation;
- Slack summary suggestion and approval;
- deduplicated action/check suggestions;
- unified open-work backlog;
- basic chronological CE timeline;
- outcome-based completion; and
- Monday reconciliation.

### Deferred

- Granola as an automatic production source;
- automatic action completion without approval;
- advanced causal attribution of metric outcomes;
- cross-market benchmarking;
- complex dependencies between actions; and
- broad multi-role in-app commentary.

### Success measures

- candidate and selected counts;
- shortlist size and mix;
- selected CEs with meaningful Slack participation;
- time to first Slack response;
- participation by role;
- AI-summary acceptance/edit/rejection rate;
- action acceptance, closure, and duplicate rate;
- median and oldest open-action age;
- repeated hero-selection and smaller-CE coverage;
- manual typing required per CE;
- weekly meeting duration;
- review completion rate; and
- return usage in week two.

## Build plan on top of the current live product

### Slice 1 — Candidate and shortlist semantics

- Reuse existing alert queue, manual additions, `review_set`, and treatments.
- Present untreated items as Candidates and selected treatments separately.
- Add shortlist count/guidance, owner/task-force filtering, recent-review context,
  and Next selected/unreviewed navigation.
- Do not change diagnostic bucket calculations.

### Slice 2 — Slack-first workspace

- Make Start/continue Slack the dominant CTA.
- Show thread state and compact approved summary first.
- Collapse optional BGM observation and compatibility role notes.
- Remove Performance/BDM note creation from the normal flow after confirming
  read compatibility for existing records.

### Slice 3 — Outcome and completion

- Add an explicit approved outcome/decision state.
- Require treatment, outcome, and suggestion triage rather than note entry.
- Preserve existing receipts and open-work carry-forward.

### Slice 4 — Timeline and backlog

- Compose existing weekly commentary, source suggestions, work, receipts, Slack
  links, and read-only Performance history into the timeline contract.
- Add ageing/overdue/stale backlog views and Monday reconciliation.
- Preserve source links and existing stable work IDs.

### Slice 5 — Guarded automation

- Run Granola ingestion in suggestion-only beta after the manual Slack-first
  workflow is stable.
- Add measured metric outcome events without recalculating report analytics in
  the browser.

## Release acceptance criteria

- All 17 market reports plus Headout retain complete current and dated artifacts.
- A BGM can reduce the candidate pool to a three-to-five-CE shortlist.
- Start/continue Slack previews and posts to the configured market channel with
  exactly-once behavior.
- Existing CE threads are reused and weekly summaries remain time-bounded.
- No Performance/BDM app comment is required to complete a review.
- Pending AI items cannot silently become approved history or work.
- Suggestions are deduplicated and normal UI hides internal trace IDs.
- Open work carries across weeks without duplication.
- CE Memory joins by stable CE ID and fails softly when history is missing.
- Review/drawer navigation preserves CE, market, week, document position, and
  drafts on desktop and narrow layouts.
- BGM/GM/admin market access passes and unauthorized access fails clearly.
- Legacy `/api/actions`, `action_upsert`, and `action_delete` contracts remain
  unchanged.
- The complete weekly-report suite, complete-site preflight, authenticated
  current/dated route checks, and legacy action guard pass before deployment.

## Decisions to confirm during Slice 1

1. Is the default shortlist limit advisory or enforced?
2. What is the nomination cutoff and who can nominate through the app?
3. Which reason options and context should be shown when a BGM elects to start a
   new Slack parent thread instead of continuing the prior discussion?
4. Which outcome types are sufficient to finish without an action?
5. After how many days does open work become overdue or stale?
6. Who may confirm completion evidence during the pilot?
7. Which owner/task-force metadata source is authoritative where ownership is
   incomplete?
8. How long should raw Slack reply and Granola transcript evidence be retained?
