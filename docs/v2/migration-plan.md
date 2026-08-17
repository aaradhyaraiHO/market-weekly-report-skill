# Weekly Market Report V2 — Migration Plan

Status: proposed execution framework, 2026-08-13.

Product scope is defined in `product-roadmap.md`; source-feedback reconciliation
is in `feedback-triage.md`. This document governs how approved scope migrates
without changing the current weekly unexpectedly.

## Goal

Deliver V2 without interrupting the weekly report, misclassifying historical
weeks, losing GM/Perf input, or allowing report, Sheet, and Slack consumers to
silently diverge.

Work continues in this canonical repository. Do not create another repository
copy. The canonical checkout remains the integration and only external-write
environment. After the dirty baseline is classified and committed, approved
short-lived `codex/` worktrees may be created for isolated no-write feature
development, with explicit integration back to main. No worktree is created
during planning.

## Release strategy

Default strategy: **parallel contracts, shared substrate**.

- Freeze representative V1 fixtures and outputs first.
- Introduce a V2 snapshot contract and routing layer without deleting V1.
- Reuse a single measurement substrate wherever metric definitions are shared.
- Make renderers, exporters, and alerts select a supported contract explicitly.
- Compare V1 and V2 on historical weeks and shadow the live weekly run.
- Cut over consumers independently only after their gates pass.
- Retire legacy outputs after one stable live cycle and explicit sign-off.

This is a planning default. V2-006 records the decision if a full replacement is
preferred instead.

## Milestones

### M0 — Baseline and intake

Deliverables:

- Current architecture baseline.
- Normalized backlog for all requested changes.
- Dependency graph and decision log.
- Selected fixture markets/weeks, including edge cases.

Exit gates:

- Every requested change has an ID, outcome, acceptance criteria, affected
  surfaces, and dependencies.
- Contradictory requests are visible as decisions.
- The pre-existing modification to `alert/followup_actioning.py` is either
  accepted into scope, separated, or completed before overlapping edits.

### M1 — Safety rails and contracts

Deliverables:

- Executable snapshot schemas/contracts for V1 and V2.
- Fixture loader and deterministic test data.
- Golden tests for measurement, buckets, render payload, Sheet rows, and alert
  payloads.
- External-write preflight and dry-run verification path.

Exit gates:

- Tests run without BigQuery, Google Sheets, Slack, Apps Script, or deployment.
- Invalid or unsupported snapshots fail before rendering/posting.
- Existing V1 fixtures reproduce accepted outputs.

### M2 — Shared measurement substrate

Deliverables:

- Typed CE/week measurement model.
- Explicit revenue, traffic, CVR, ROI, CM, decomposition, time-shape, tROAS, and
  monthly-home provenance.
- Shared per-market and global assembly path.

Exit gates:

- Market and global builds agree for the same CE/week inputs.
- Shapley/decomposition contributions reconcile to the measured delta within a
  documented tolerance.
- Data availability and optional-enrichment states are visible.

### M3 — V2 routing and recommendations

Deliverables:

- V2 Defend, Compound, New CE, and any approved Prepurchase/overlay logic.
- Single-home/overlap rules and owner routing.
- Explanation fields sufficient for report, Sheet, and Slack consumers.

Exit gates:

- Each rule has boundary and regression tests.
- Historical comparison is reviewed for count, dollar coverage, false positives,
  and lost V1 cases.
- Product/Perf owners approve action semantics and thresholds.

### M4 — Consumer migration

Deliverables:

- V2 report sections and interactions.
- V2-aware global report.
- V2 Sheet export and action history.
- V2 alert tables, RCA selection, follow-ups, and Thursday workflow.

Exit gates:

- Every consumer declares accepted schema versions.
- Stable identity is used across report/store/Sheet/Slack.
- Render and alert golden tests pass for all fixture markets.
- Human-entered Sheet/store data survives re-runs and reorderings.

### M5 — New features

Deliverables depend on the normalized backlog. Features should be implemented as
vertical slices after the substrate and contracts they need are stable.

Review mode is sequenced as an independent downstream integration with Market
Glance as the proposed workflow owner:

1. authenticated ownership/API and metric-alignment discovery;
2. read-only weekly artifact, audit-status and deep-link integration;
3. canonical run/signal binding for new WBR Audits and commitments;
4. Granola transcript ingestion in suggestion-only shadow mode; and
5. reviewed automation after privacy, access and posting gates pass.

Review consumes a pinned published artifact. Its jobs, credentials and failures
remain separate from weekly generation and publication.

Exit gates for each feature:

- Feature-specific acceptance criteria pass.
- No mutation boundary is crossed implicitly.
- Operator and fallback behavior are documented.

### M6 — Shadow run and cutover

Process:

1. Run V1 and V2 for selected historical weeks.
2. Run V2 in shadow for a current week without external writes.
3. Review market/global reports, Sheet previews, and Slack dry-runs.
4. Enable V2 report staging.
5. Enable Sheet writes after a backup and CID-integrity check.
6. Enable Slack posting after channel/token/preflight checks.
7. Observe one complete Monday-to-follow-up cycle.

Exit gates:

- No unexplained material metric differences.
- No missing markets, CEs, or required enrichment.
- Perf and GM actions remain attached to the correct CE/week.
- Re-running every operational step is safe.
- Rollback has been rehearsed using retained V1 artifacts/configuration.

### M7 — Legacy retirement

Deliverables:

- Remove unused bucket outputs and compatibility adapters.
- Archive superseded active plans and update operator documentation.
- Record the final V2 contract and threshold decision log.

Exit gates:

- All consumers use V2.
- At least one stable live cycle has completed after cutover.
- V1 fixtures remain available for historical audit even if V1 runtime code is
  removed.

## Verification matrix

| Layer | Fast check | Historical check | Live/shadow check |
|---|---|---|---|
| Data access | SQL/parameter tests | Selected BQ fixture extracts | Byte caps, row counts, freshness |
| Measurement | Unit/property tests | Reconcile known market-weeks | Headline/dashboard spot check |
| Buckets | Boundary/golden tests | Coverage and diff report | Owner review of surfaced CEs |
| Snapshot | Schema validation | V1/V2 contract diff | No missing required modules |
| Report | Payload/DOM checks | Golden render screenshots/HTML | Interactive review |
| Sheet | Pure row-merge tests | Reorder/add/remove simulation | Backup, dry-run, CID read-back |
| Slack | Payload/chunk tests | Golden dry-run text/blocks | Test channel before production |
| Deployment | State/page tests | Local staged artifact review | Explicit user deploy and smoke test |

## Change-set rules

- One coherent contract or feature slice per change set.
- Tests and migration adapters land with the behavior they protect.
- Do not mix threshold decisions with broad refactors unless inseparable.
- Generated reports, snapshots, credentials, and ledgers remain uncommitted.
- No external Sheet write, Slack post, or production deploy is part of a code
  review unless explicitly called out and approved.
- Update `backlog.md` status and evidence with every merged change.

## Immediate next actions

1. Ingest the user's 50+ requested changes in any convenient format.
2. Normalize and deduplicate them in `backlog.md` without losing original intent.
3. Produce a dependency graph and identify the smallest M1 foundation slice.
4. Decide V1/V2 selection policy and the first fixture weeks.
5. Resolve the existing `alert/followup_actioning.py` modification before work
   touches the follow-up path.
