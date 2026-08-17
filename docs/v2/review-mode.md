# Weekly Report V2 — Review Mode

Status: proposed product and integration contract, 2026-08-14.

Review is a first-class V2 mode for turning the published weekly into a durable,
collaborative record. It connects three workflows:

1. BGM review notes, mentions and weekly note history;
2. lightweight audits discussed with the right people in Slack; and
3. meeting evidence and follow-ups extracted from Granola transcripts.

Review is downstream of the weekly build. A Review, Granola or Slack failure
must never block, alter or republish the canonical weekly report.

Public inspection of Market Glance shows that it already implements much of
this workflow: WBR Audit selection/runs, immutable history, governed owner to
Slack mappings, dedicated CE threads, market summaries, and reconciliation into
Actions, Open Topics and Decisions. This document is therefore the cross-product
Review contract. The default recommendation is for Market Glance to own the
workflow state while the weekly owns metric/signal evidence. Do not implement a
parallel Review database in the weekly repository unless joint backend discovery
proves that the existing capability cannot satisfy the contract.

## Grounded operating model: Growth running notes

The reference workflow is `Weekly DB America` → `26 H2 Running Notes`, observed
around `AC9` on 2026-08-14. It establishes the product behavior Review must
preserve:

- one stable row per CE with CE ID/name, DRI and current performance metrics;
- an explicit review choice with `Yes`, `No`, `Offline`, and
  `Time permitting, otherwise asynch`;
- common evidence links and durable learnings separate from weekly commentary;
- one commentary column per report week;
- multiple named contributors appending observations, questions, replies,
  decisions and actions in the same CE/week context; and
- prior-week columns retained side by side so the next meeting can close the
  loop.

For example, the referenced CE/week commentary does not contain a single formal
“note.” It combines a commercial update, metric interpretation, a funnel issue,
a question to another owner, a reply, and evidence links. Review must therefore
model a conversation and outcome, not merely provide a textarea or task form.

The Sheet is a strong behavioral reference but a weak scalable data model:
people are embedded in free text, events have no individual timestamps or
status, actions are not reliably extractable, and every new week widens the
table. V2 preserves the workflow while storing it as CE/week events and rendering
the familiar weekly history vertically.

## User outcome

For every market/week, a reviewer can answer:

- what was reviewed;
- what the BGM or meeting participants said;
- who was notified;
- which Slack discussion is authoritative;
- what decision or action followed;
- what was not discussed and still needs review; and
- whether the item was resolved in a later week.

## Existing substrate and gaps

The current report already supports one CE note per week, prior-week note
history, author text, an Apps Script/Sheet store, and creation or reuse of a
Slack thread. These are useful migration inputs, not the final Review model.

The generated weekly alone cannot safely provide the requested mode because:

- saving a second note overwrites the CE/week row instead of appending an event;
- author is free text and cannot safely resolve a notifying Slack mention;
- the note-created Slack thread can diverge from the weekly alert thread;
- there is no review-cycle, reviewed/not-reviewed or completion model;
- actions, decisions and comments are not separate typed records;
- there is no transcript source, excerpt provenance or CE-match confidence;
- generated content has no review/approval state; and
- the Sheet/Apps Script backend is not an identity- or permission-aware system.

Market Glance appears to address several of those gaps, but authenticated
verification is still required for its append-only guarantees, permissions,
thread idempotency, CE lineage, API stability and metric alignment.

## Product surface

### Weekly Review inbox

The Review mode opens on one market/week and shows:

- **Needs review** — priority report signals without reviewed evidence;
- **Meeting covered** — items matched to transcript evidence;
- **Discussing** — items with an active Slack thread;
- **Awaiting owner** — decision exists but owner/target date is missing;
- **Follow up** — open actions carried into the current week; and
- **Resolved** — reviewed items with an outcome, retained in history.

Every row retains the canonical CE, signal, bucket, metric basis and report
deep-link. Review filters may hide rows but cannot change those facts.

The minimum selection states mirror Growth's actual practice:

| State | Meaning |
|---|---|
| **Review live** | discuss this CE in the weekly meeting |
| **Review async** | send/share for written input; no meeting time required |
| **Offline** | owner will handle outside the weekly |
| **Skip** | explicitly reviewed and not worth discussion this week |
| **Unreviewed** | no choice has been made |

These replace the literal Sheet dropdown labels with clearer product language
while preserving their semantics. Selection is per CE + report week and records
who selected it and why it entered the queue.

### Review workspace inside the current report

Review opens as a focused layer over the existing weekly, not a new dashboard.

For each selected CE it shows:

1. **Evidence header** — CE, market, DRI, current Revenue/ROI/CM2, WoW/4-week/
   YoY movement and “why surfaced.”
2. **This week's discussion** — chronological named contributions, questions,
   replies and source links.
3. **Outcome** — decision, action, owner and expected check date when one exists;
   “discussion only” is also an explicit valid outcome.
4. **Prior context** — last one to two weekly discussions and unresolved items,
   collapsed by default.
5. **Share** — preview and send the reviewed summary to the governed Slack
   thread; saving notes alone never notifies.

The review queue supports previous/next CE, keyboard navigation, progress
(`reviewed / selected`) and autosaved drafts. Closing Review returns the user to
the same report section, filters and CE.

### Notes and weekly threads

Opening a review item shows an append-only timeline grouped by report week.
Timeline events can be a note, reply, decision, action, status change, Slack
message reference or meeting-derived suggestion.

The primary authoring control can remain conversational. Structured decisions,
actions, owner and due/check date are extracted into editable suggestions or
added explicitly; they must not force every comment into a form before the team
can record what was discussed.

Manual note behavior:

1. a reviewer writes a note and optionally selects people from governed identity
   search;
2. saving the note records it without notifying anyone;
3. **Notify and share** previews the target Slack thread and resolved mentions;
4. explicit confirmation posts one idempotent message and records its Slack ID;
5. later replies sync into the timeline without replacing the original note.

Typed `@name` text alone must not imply a notification. The backend must resolve
an internal person ID to a Slack user or user-group ID and display exactly who
will be notified before the write.

### Slack thread topology

Slack does not support nested threads, so V2 uses two linked levels:

- one **weekly review hub** for market-level status and uncovered items; and
- the existing **per-CE alert thread** for CE-specific RCA, notes and actions.

Review must reuse the registered alert thread when it exists. It creates a new
CE/week thread only when no authoritative alert thread exists, and stores the
reason. A single thread registry is shared by alerts, Review and follow-ups.

The report UI presents the per-week timeline even when its events live across
the hub and CE threads.

## Lite audits

A lite audit is a small, explicit review object—not a screenshot or free-form
Slack post. It contains:

- market and report week;
- CE(s) or market-level scope;
- reason for review and triggering signal;
- compact evidence with metric basis and report link;
- question or decision needed;
- requested reviewers/owners;
- status and due/review date; and
- authoritative Slack thread binding.

Lifecycle:

```text
draft -> ready -> posted -> discussing -> decided -> resolved
                                  |                     |
                                  +----> needs_followup -+
```

Only `posted` and later states imply an external Slack write. Draft generation,
report builds and view changes are no-write operations.

The Slack message should be concise: why this needs attention, the minimum
evidence, the question, resolved mentions and a deep-link. Detailed tables stay
in the weekly report.

## Granola transcript workflow

The source requirement is the full transcript, not only an AI-enhanced meeting
summary. The proposed flow is:

1. ingest eligible WBR notes/transcripts into a centrally governed store;
2. associate the meeting to a market and report week from configured calendar,
   folder and meeting metadata;
3. preserve note ID, owner, meeting time, transcript location and access scope;
4. extract candidate comments, decisions, actions, owners and due dates;
5. match candidates to CEs/signals using exact IDs first, then governed aliases;
6. attach transcript excerpts/timestamps and a confidence result;
7. compare covered CEs against the report's review queue;
8. place unmatched or low-confidence candidates in a human reconciliation queue;
9. let a reviewer accept, edit or reject suggestions; and
10. after approval, write accepted events to Review and optionally to the
    authoritative Slack thread.

Generated suggestions never silently become human comments, completed actions
or notifying Slack messages. The UI distinguishes `meeting-derived`,
`human-authored` and `Slack-synced` events.

Granola's current API can return a note with transcript, summary, attendees and
calendar metadata. Access depends on plan and key scope: a personal key sees the
member's accessible notes; an Enterprise key can cover the Team space. The
centralization design must therefore be approved before the integration is a
release dependency.

## Cross-product logical contracts

These are interoperability requirements. They do not imply that the weekly
repository owns the backing tables.

### Review cycle

```text
review_cycle_id, market_slug, week_start, report_artifact_id,
status, required_count, reviewed_count, opened_at, closed_at
```

### Review item

```text
review_item_id, review_cycle_id, scope_type, scope_id,
signal_key, bucket_key, priority, status, owner_id, due_at,
canonical_report_deep_link, created_at, updated_at
```

`scope_id` is the stable CID for CE scope. A review item references report
evidence; it does not copy or recalculate bucket truth.

### Review event

```text
event_id, review_item_id, event_type, body, actor_id, source_type,
source_ref, provenance_excerpt, provenance_time, mentions[],
approval_state, created_at, supersedes_event_id
```

Events are append-only. Corrections supersede an event instead of erasing it.

### Thread binding

```text
thread_binding_id, market_slug, week_start, scope_type, scope_id,
purpose, channel_id, parent_ts, permalink, source, created_at
```

Uniqueness is enforced for market + week + scope + purpose. Post requests use a
stable idempotency key derived from review event and target thread.

### Meeting source

```text
meeting_source_id, provider, provider_note_id, market_slug, week_start,
meeting_at, owner_identity, access_scope, transcript_hash,
ingested_at, processing_status
```

Raw transcript retention, encryption, deletion and excerpt policy require
Security/Legal/Data approval. The product can store only approved excerpts and
a source reference if retaining full transcripts is not permitted.

## Identity and permissions

Review requires authenticated identity. At minimum:

- BGM/reviewer can author notes and approve meeting suggestions;
- owner can reply and update assigned actions;
- market admin can manage shared review presets and mappings;
- service identity can ingest and propose but cannot impersonate a person; and
- Slack writes record both the approving human and posting service.

Email-to-Slack matching is a bootstrap, not the durable identity key. Store an
internal person ID with verified Slack and Granola identities.

## Rollout that cannot affect the weekly

### R0 — ownership and contract validation

- freeze current note/action behavior with regression fixtures;
- inspect the authenticated Market Glance APIs and backing guarantees;
- compare its performance snapshot and CE identity to the weekly;
- agree Review/event/thread/identity ownership and contracts;
- generate integration, Slack and transcript outputs as previews only.

### R1 — read-only integration pilot

- weekly report links to Market Glance audit/commitment timelines;
- weekly shows read-only review/owner/status returned by the shared contract;
- Market Glance shadows a pinned weekly artifact/run ID;
- metric, CE and owner mismatches are measured before any source cutover;
- one market behind a feature flag;
- production weekly build remains unchanged.

### R2 — canonical evidence binding

- new Market Glance audits bind to weekly run, signal and CE IDs;
- audit messages link to the canonical weekly evidence;
- existing alert and audit thread topology is reconciled;
- idempotency and test-channel delivery are verified by the workflow owner.

### R3 — Granola shadow ingestion

- central eligible-transcript source approved;
- ingest and extract after the meeting, never during weekly build;
- show proposed mappings, uncovered CEs and draft follow-ups;
- no action/comment/Slack writes from generated output.

### R4 — reviewed automation

- accepted suggestions create Market Glance/shared Review events and action drafts;
- approved output can update the authoritative Slack thread;
- scheduled reconciliation reports failures without blocking the weekly.

## Safety and acceptance gates

- V1 report artifact and publish path are byte/contract unchanged during pilot.
- Review reads a pinned `report_artifact_id`, never an in-progress build.
- Review jobs have separate credentials, queues, logs and failure alerts.
- Every external write has target preview, human authorization and idempotency.
- Reprocessing a transcript or report produces no duplicate note or Slack post.
- Missing transcript access is visible and creates no inferred meeting coverage.
- Low-confidence CE/person matches cannot notify or assign automatically.
- Deleting a personal view cannot delete Review events or Slack bindings.
- Slack reply ingestion preserves author, timestamp and permalink.
- Meeting-derived claims link to approved provenance.
- Rollback disables Review flags/jobs without changing V1 generation.

## Decisions required before implementation

1. Which markets and meetings constitute the first pilot?
2. Is the weekly alert CE thread the authoritative discussion location?
3. Who may notify individuals or user groups from Review?
4. Is Review send always confirm-first, or can approved rules auto-post later?
5. Which Granola workspace/folder owns WBR transcripts?
6. Is an Enterprise API key and Team-space access available?
7. May full transcripts be centrally retained, or only indexed/referenced?
8. What retention and deletion policy applies to transcripts and excerpts?
9. Who approves meeting-derived comments/actions before they become records?
10. What state closes a review item, and who can reopen it?
11. Does Market Glance become the authoritative Review/commitment/thread store?
12. Which versioned API or table contract will ingest the weekly run and expose
    read-only workflow status back to the report?
