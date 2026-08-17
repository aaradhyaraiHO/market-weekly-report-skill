# Phase 1 — Current Report Compatibility Contract

Status: proposed release gate, 2026-08-14.

Phase 1 improves the architecture without changing the current reporting
product. Internal cleanup is complete only when the existing weekly behaves the
same at every observable boundary.

## Frozen behavior

Unless a separately approved correctness fix explicitly says otherwise, Phase
1 preserves:

- report sections, sequence, headings and navigation;
- market switcher, Headout route and published URL conventions;
- metric values, formats, comparison periods and provenance labels;
- CE populations, bucket membership, ordering and recommendation text;
- All-CE search, filters, sorting, groups, saved views and drawers;
- notes, actions, history and local cache behavior;
- snapshot fields consumed by existing report, Sheet, Slack and follow-up jobs;
- Sheet column order, stable CID association and human-owned fields;
- Slack parent/thread structure, wording, routing and posting cadence;
- follow-up semantics and posted-message ledger identity; and
- operator commands and V1 as the default engine.

“The page renders” is not sufficient evidence. Compatibility is checked at the
data, rendered, export and alert boundaries.

## Phase 1 may change

- internal module boundaries and shared helpers;
- schema validation and typed/explicit contracts;
- fixture and test infrastructure;
- logging, run manifests and structured module health;
- configuration validation;
- deterministic local preview paths;
- code duplication, provided parity is proven; and
- inactive V2-only code/artifacts behind explicit flags.

## Change exceptions

A current-report behavior may change only through a named exception containing:

1. backlog/Sheet ID or architecture-defect ID;
2. reproduced before-state;
3. approved expected after-state;
4. affected markets and consumers;
5. regression fixture;
6. report, Sheet and Slack preview evidence where applicable; and
7. rollback instructions.

Correctness fixes are developed separately from structural cleanup so a parity
failure cannot be dismissed as an intended refactor effect.

## Reference fixtures

The minimum compatibility matrix is:

| Scope | Purpose |
|---|---|
| North America, week 2026-08-02 | deployed reference and dense-market behavior |
| Italy, same selected fixture week | second major market and action/comment coverage |
| one small/sparse market | empty/degraded/long-tail behavior |
| Headout, same selected fixture week | global aggregation, market tags and capped CE view |

Exact non-NA fixture weeks are locked during fixture capture based on available
accepted artifacts. A fixture records source artifact hashes and does not depend
on live BigQuery for routine tests.

## Required comparison layers

### Snapshot

- schema and required fields;
- market/week/run identity;
- market and CE totals;
- metric components and ratios;
- bucket membership, rank, reason and recommendations;
- follow-up and optional-module payloads.

### Rendered report

- section presence and order;
- embedded report data;
- headings, explanatory copy and links;
- tables, rows and displayed values;
- interaction smoke tests for filters, sorting, drawers, notes and actions;
- representative visual screenshots.

Dynamic or intentionally variable fields such as generation timestamp are
normalized through an explicit allowlist, not broad snapshot exclusions.

### Sheet/export preview

- headers and column ownership;
- row identity/order rules;
- CID-keyed human data preservation;
- action/comment fields;
- no live Sheet write.

### Slack/follow-up preview

- message groups and thread structure;
- rows, values, links and routing lookup;
- posted-message/follow-up identity;
- no live post.

## Merge gates

A Phase 1 branch may merge only when:

1. the pre-existing `alert/followup_actioning.py` modification is classified and
   excluded, accepted, or completed intentionally;
2. all reference fixtures pass snapshot comparisons;
3. report, Sheet, Slack and follow-up previews pass;
4. no external write occurs during verification;
5. V1 remains the default command path;
6. every diff is either zero or linked to an approved exception;
7. the current live build command still succeeds; and
8. rollback is the previous known-good commit/artifact, not an emergency rewrite.

## Worktree boundary

The canonical checkout remains the integration and only external-write
environment. After the dirty baseline is intentionally resolved:

1. `codex/weekly-baseline-contracts` captures contracts, fixtures and comparison
   tooling without refactoring producers;
2. it merges and establishes the compatibility gate;
3. `codex/weekly-architecture-cleanup` performs internal cleanup in small,
   independently comparable commits; and
4. correctness/product changes use later branches and approved exceptions.

No Phase 2 small report change, Oak redesign or Review-mode behavior is included
in these Phase 1 branches.
