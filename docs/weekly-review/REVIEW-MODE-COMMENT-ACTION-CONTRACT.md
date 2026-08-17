# Review mode — comment and action contract

Status: mockup requirement only
Scope: Parag weekly-review mode
Boundary: no production writes, bucket changes, weekly calculations, or new persistence schema

## Identity

Every displayed review record preserves the existing identity tuple:

- `market`
- `ce_id`
- `week`

Authorship, timestamps, source labels, and source links remain attached to their originating record. The UI must not infer an owner or merge differently attributed sources.

## Workflow phases

The mockup exposes four connected phases:

1. **Prepare** — assemble system-flagged and manually added CEs, set live/async/offline/time-permitting treatment, order the agenda, show carried-forward items, and identify missing stakeholder inputs.
2. **Review** — work through the CE queue, retain last-reviewed state, record Team commentary, create explicitly owned actions, and schedule next-week checks.
3. **Reconcile** — resolve unmatched Granola mentions before attachment, approve or reject source-attributed call notes, and route each approved note to Team commentary, a to-do, or tracking.
4. **Follow up** — manage actions across CEs, retain status/context/timestamp/source/due state, close with evidence, or carry work into the next week.

Phase transitions in the mockup are presentation-only and do not save or publish records.

## Activity streams

The CE Activity area presents related context together while retaining five distinct streams:

1. **Current Team note** — relabeled from GM note; supports BGM, BDM, and Perf contributions using the author information supplied by the existing record.
2. **Prior Team-note history** — includes same-week and prior-week records. The current-week recording entry point remains rendered even when no saved note exists.
3. **Perf decision record** — read-only, CE-keyed `ce.perf_action_hist`, with four weekly slots. It is not merged into Team-note history and adds no write path.
4. **Slack context** — preserves channel, timestamp, exact CE association, author attribution, and permalink.
5. **Granola context** — reserved for the last one to two weeks. Until an approved CE-keyed source exists, it fails closed as `Source unavailable`.

Existing Sheet and market-scoped local-cache semantics remain unchanged. Multi-owner storage is a future contract and is not simulated by parsing names from note text.

## Actions and follow-through

Each review-mode action slot exposes:

- Action status
- Explicit owner
- Comment or decision context
- Timestamp
- Source and optional source link
- Due or follow-up date
- Next-week close-out behavior

The mockup includes broader operational states without defining a new backend enum:

- Needs action
- Already actioned
- Self-recovering
- Monitoring
- No action needed

Open items may be shown as candidates for next-week resurfacing. Completed items remain in history with their completion evidence.

## Structured Slack handoff

The mockup previews a CE-scoped Slack thread containing market, CE, week, action owner, follow-up date, reason, and evidence link. Posting attribution is shown before the preview. The mockup does not post to Slack or alter the existing save-before-post behavior.

## Explicitly excluded

This scope does not change or extend:

- Metric definitions or time semantics
- Funnel, CVR, TGID, channel, language, lead-time, or country views
- New-CE launch QA
- Weekly calculations or review-bucket logic
- Sheet writes, Slack posting, publishing, or local-cache schemas
- Per-CE chat or BQ-context persistence

Those CE-drawer analytics remain owned by the separate CE-drawer worktree.
