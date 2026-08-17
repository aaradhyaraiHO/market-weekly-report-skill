# Weekly Market Report V2 — Backlog

Status: intake baseline, 2026-08-13.

This file is the single planning index for the 50+ V2 changes. It records
desired behavior, not implementation details. A change is ready only when its
acceptance criteria and affected surfaces are explicit.

The consolidated 99-item stakeholder intake and product cut now live in:

- `feedback-triage.md` — built/partial/P0/must/decision/later reconciliation;
- `product-roadmap.md` — interactive/customisable V2.0 and V2.1 release shape;
- `decision-brief.md` — recommended defaults, sign-off order and worktree blockers.
- `interaction-spec.md` — versioned view state, scope and interaction contract;
- `review-mode.md` — BGM notes, Slack lite audits and Granola transcript workflow.
- `execution-board.md` — releases, batches, worktree ownership and rollout gates.
- `scale-architecture.md` — build-once multi-market architecture and Market
  Glance integration boundary.
- `phase-1-compatibility-contract.md` — frozen current-report behavior and
  architecture-cleanup merge gates.

This file remains the implementation-status ledger once approved Sheet items
are converted into atomic engineering backlog IDs.

## Status vocabulary

- `INBOX`: captured but not analyzed.
- `NEEDS_DECISION`: blocked on product or metric choice.
- `READY`: scoped, dependency-ordered, and testable.
- `IN_PROGRESS`: actively being implemented.
- `VERIFY`: implemented; evidence is pending.
- `DONE`: acceptance criteria and rollout checks passed.
- `DEFERRED`: intentionally excluded from the current V2 release.

## Priority vocabulary

- `P0`: correctness, data loss, unsafe mutation, or weekly-run blocker.
- `P1`: required for the V2 release.
- `P2`: valuable but can follow the first V2 release.
- `P3`: polish or cleanup.

## Change template

Copy this block for every requested change:

```text
ID: V2-###
Title:
Status: INBOX
Priority:
Problem / desired outcome:
Acceptance criteria:
Markets / users affected:
Inputs or metric definitions affected:
Snapshot fields affected:
Surfaces affected: report | global | sheet | Slack | action store | deploy
Dependencies:
Backward-compatibility requirement:
Verification fixture / week:
External rollout or approval:
Notes:
```

## Foundation backlog discovered by audit

| ID | Priority | Status | Item | Acceptance gate |
|---|---:|---|---|---|
| V2-001 | P0 | READY | Define executable snapshot V1 and V2 contracts | Builders validate before write; render/export/alert fail clearly on unsupported versions |
| V2-002 | P0 | READY | Establish deterministic local fixtures and golden outputs | At least one fixed market-week runs without BigQuery and detects contract/bucket/render drift |
| V2-003 | P0 | NEEDS_DECISION | Replace or re-baseline stale NA validation | A named market-week has current expected results and a documented refresh policy |
| V2-004 | P1 | READY | Separate measurement substrate from bucket routing | CE measures can be tested without rendering or routing; bucket functions consume the same typed input |
| V2-005 | P1 | READY | Unify per-market and Headout-global assembly | Shared logic produces equivalent fields; global-only capping/market tags are isolated |
| V2-006 | P1 | NEEDS_DECISION | Define V1/V2 runtime selection and retirement policy | Operator can deliberately run either supported contract during migration |
| V2-007 | P1 | READY | Add configuration validation | Market mappings, thresholds, channels, and week semantics fail early when inconsistent |
| V2-008 | P1 | READY | Add provenance to every metric basis consumed across surfaces | Report, Sheet, and Slack differences are machine-readable and visibly labeled where needed |
| V2-009 | P1 | READY | Formalize optional-enrichment health | Output records present/missing/failed state; required V2 modules can fail the build |
| V2-010 | P1 | READY | Add a no-external-write end-to-end verification command | Builds from fixtures through report/alert/export previews without network mutations |
| V2-011 | P1 | NEEDS_DECISION | Validate and adopt Market Glance Review event/cycle contracts | Multiple authors/sources retain history; Review cannot mutate weekly truth |
| V2-012 | P1 | NEEDS_DECISION | Adopt governed Market Glance/shared person-Slack identity | Mentions resolve to verified IDs and preview recipients before notification |
| V2-013 | P1 | NEEDS_DECISION | Reconcile weekly alert bindings with the authoritative Market Glance/shared thread registry | Alert, Review and follow-up reuse the same CE/week discussion binding |
| V2-014 | P1 | NEEDS_DECISION | Integrate Market Glance WBR Audits and commitment lifecycle | Weekly links canonical evidence; workflow writes remain outside the build |
| V2-015 | P1 | NEEDS_DECISION | Approve Granola transcript access and retention | Central eligible source, API scope, privacy and deletion policy are signed off |
| V2-016 | P1 | READY | Build Granola suggestion-only reconciliation | Extracted evidence/actions are provenance-linked and require human acceptance |

## Bucket and product backlog already present in repository notes

These are candidates, not approved scope. They must be reconciled with the
user's 50+ changes before implementation.

| ID | Priority | Status | Item | Open decision / dependency |
|---|---:|---|---|---|
| V2-020 | P1 | NEEDS_DECISION | Adopt “monthly state, weekly change” architecture | Confirm monthly-home source and refresh contract |
| V2-021 | P1 | NEEDS_DECISION | Replace B1+B3 with structural Defend routing | Confirm material-move floor and owner routing |
| V2-022 | P1 | NEEDS_DECISION | Keep temporary moves as positive/negative seasonality lanes | Confirm ROI gates and action sizes |
| V2-023 | P1 | NEEDS_DECISION | Define structural boundary | Proposal is at least two consecutive weeks |
| V2-024 | P1 | NEEDS_DECISION | Resolve mixed comparison bases in fluctuations | Decide whether to unify basis or expose a basis chip |
| V2-025 | P1 | NEEDS_DECISION | Recalibrate fluctuation volume floor | Current 10 orders/week may be too low; backtest candidate 40–50 |
| V2-026 | P1 | NEEDS_DECISION | Add CM1/conversion margin overlay | Define escalation behavior when revenue is flat but margin erodes |
| V2-027 | P2 | DEFERRED | Implement true Prepurchase bucket | Requires lead-time and availability trigger definition/data quality |
| V2-028 | P1 | NEEDS_DECISION | Finalize New CE framework | Confirm launch window, tier boundary, and handoff owner |
| V2-029 | P1 | NEEDS_DECISION | Finalize Scale-Up/Compound structural rules | Resolve lane-a target gate and tROAS-change interaction |
| V2-030 | P1 | READY | Remove legacy bucket outputs after all consumers migrate | Depends on V2 contracts and consumer inventory |

## Action-loop and operations backlog discovered by audit

| ID | Priority | Status | Item | Acceptance gate |
|---|---:|---|---|---|
| V2-040 | P0 | READY | Preserve and test CID-keyed Perf Sheet writes | Re-sort/add/remove simulations never move human input to another CID |
| V2-041 | P1 | NEEDS_DECISION | Implement store-backed Perf layer | Requires Apps Script deployment and store schema approval |
| V2-042 | P1 | READY | Make Sheet column ownership explicit | Engine-owned and human scratch ranges cannot clobber each other |
| V2-043 | P1 | READY | Version alert/report parsing contracts | Alert generation handles V1 and V2 deliberately, not through missing-key fallbacks |
| V2-044 | P1 | READY | Make external writes idempotent and auditable | Re-running publish/export/post has a documented and tested result |
| V2-045 | P1 | READY | Consolidate market/channel mappings | Report, notes, alerts, and follow-ups use one validated registry |
| V2-046 | P1 | NEEDS_DECISION | Add Central Live Entertainment coverage | Confirm report semantics and Slack destination |
| V2-047 | P1 | READY | Add operational preflight | Checks branch, credentials, snapshots, channels, week, and dry-run mode before mutations |
| V2-048 | P1 | READY | Define degraded-run policy | Each unavailable enrichment is classified as fatal, warning, or retryable |
| V2-049 | P2 | READY | Rotate and document Slack-token handling | No inline tokens; environment/secret path and rotation owner documented |
| V2-050 | P2 | READY | Reconcile stale handoffs with code | Historical notes remain archived; active plan points only to current truth |

## Intake status

The initial combined intake is complete: all 99 Sheet items are accounted for
in `feedback-triage.md`. New requests continue to use the atomic change template
above. Implementation order and batching are maintained in
`execution-board.md`; this file remains the engineering-status ledger.

## Intake rules

1. Preserve the user's wording in the item, then add a normalized outcome.
2. Split requests that have independently releasable or testable behavior.
3. Do not estimate until acceptance criteria and dependencies are known.
4. Identify every consumer of a changed snapshot field before marking it READY.
5. Require a fixture week and expected evidence for every metric/bucket change.
6. Flag contradictions instead of resolving product choices silently.
7. Keep external writes and rollout actions separate from code completion.
