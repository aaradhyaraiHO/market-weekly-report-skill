# Weekly Report V2 — Execution Board

Status: proposed delivery plan, 2026-08-14.

This board converts the consolidated feedback, architecture audit and Review
mode into a delivery program. It deliberately separates:

1. legacy/current-week safety;
2. V2 platform capabilities;
3. product feature slices; and
4. later additive requests.

The current weekly remains the default until the V2 pilot passes. Planning and
implementation happen in this repository; no second repository copy is made.
The source Sheet contains 99 populated requests and no `E10` row.

Public Market Glance inspection materially changes the ownership plan: existing
WBR Audits, Slack identity/threading and commitment tracking should be integrated
and validated, not rebuilt as parallel systems in this repository. See
`scale-architecture.md`.

Phase 1 is governed by `phase-1-compatibility-contract.md`: architectural
cleanup may change internals but not the observable current reporting structure.

## Portfolio model

| Portfolio | Purpose | Production effect while building |
|---|---|---|
| **P0 — Protect V1** | correct unsafe legacy behavior and freeze compatibility | approved, narrow V1 fixes only |
| **V2 platform** | schemas, measurement, view state, identity, actions, Review | none; separate artifacts and previews |
| **V2 product slices** | Scan, Explore, Diagnose, Review, Act, Close loop | none until shadow/pilot approval |
| **Later modules** | opportunity flags, secondary dashboards and automation | none; start only after V2.0 gates |

“Legacy” does not automatically mean “delete.” A legacy field or path is
removed only after every consumer has migrated and parity evidence exists.

## Concrete V2.0 product cut

V2.0 is not a wholesale replacement of the current report. It delivers four
visible improvements on the existing base:

1. **Cleaner scan:** clearer labels, sorting/collapse, a concise priority TLDR,
   and fewer/noisier signals routed more carefully.
2. **Consistent exploration:** existing All-CE customization extended to the
   tables and sections where users requested it.
3. **Grounded Review mode:** select CEs for live/async/offline review, capture a
   multi-author CE/week discussion, record an outcome, and show the prior one to
   two weeks for follow-up.
4. **Workflow links:** connect reviewed evidence to the existing Market Glance/
   Slack workflow rather than duplicating commitment and audit systems.

Everything else is either a correctness prerequisite, a later data module, or
an independently approved integration.

## Release 0 — Baseline and legacy safety

Objective: make the live weekly safe to preserve while V2 is built.

### R0.0 — Repository baseline

- classify the pre-existing `alert/followup_actioning.py` modification;
- intentionally commit planning separately from production changes;
- remove or ignore incidental `.DS_Store` files without bundling user code;
- record the deployed NA 2026-08-02 report as the reference artifact.

No feature worktree starts before this baseline is clean and attributable.

### R0.1 — Compatibility harness

Worktree: `codex/weekly-baseline-contracts`.

Scope:

- V1 and V2 executable snapshot/consumer contracts;
- deterministic fixtures and golden report/Sheet/Slack previews;
- no-external-write end-to-end command;
- metric provenance and structured module-health policy;
- separate V1/V2 artifact paths and explicit engine selection.

Sheet/architecture coverage: H4, ARCH-P0-1, ARCH-P0-2, ARCH-P0-4,
V2-001/002/006/008/009/010.

Exit gate: frozen V1 outputs reproduce locally without BigQuery, Sheets, Slack
or deployment access.

The exact preserved surfaces and comparison layers are defined in
`phase-1-compatibility-contract.md`. Any non-zero behavior change requires a
separate named correctness exception and is not hidden inside cleanup.

### R0.2 — Current-week correctness

Worktree: `codex/weekly-current-correctness`; branches after R0.1 merges.

Scope:

- ROI lag and child-CE aggregation;
- CVR basis/provenance;
- comment and CID-keyed Perf preservation regressions;
- NA Slack/CTA routing;
- full-waste classification regression;
- stale-run/freshness preflight;
- header-driven future-week follow-up discovery;
- credential hygiene/rotation coordination.

Coverage: B1–B4, B12, E7, E8, F10, H1, H3, H6, ARCH-P0-3,
V2-003/007/040/045/047/049.

Rule: fixes require a failing fixture and an approved before/after outcome. This
release does not redesign report IA or bucket strategy.

## Release 1 — V2 platform foundation

Objective: create the shared substrate that prevents each feature from
inventing its own metric, identity or persistence rules.

At most three code-only, no-write worktrees run in parallel after R0 merges.

### R1.A — Measurement and routing contract

Worktree: `codex/v2-routing`.

Owns:

- typed CE/week measurement model;
- shared market/global assembly;
- final routed bucket membership and explanation fields;
- materiality/coverage backtest framework;
- V2 Defend, Compound and Lifecycle routing;
- historical V1/V2 membership and dollar-coverage diffs.

Coverage: B5, B8, C1, C3–C7, C9–C11, C13, V2-004/005/020–030.

Does not own HTML, action writes or production Slack.

### R1.B — Workflow interoperability contract

Worktree: `codex/v2-workflow-contract`.

Owns:

- references to the stable person/role identity owned by Market Glance/shared registry;
- action/review event interoperability contracts;
- CE/week/bucket/lane action keys;
- Perf/GM/BGM/BDM ownership boundaries;
- references to the Market Glance/shared thread registry;
- Sheet/store adapters and read-only previews;
- follow-up and known/managing state.

Coverage: A10, B13, C2, C11, E5, E6, E9, F14,
V2-011–014/040–045.

Does not build a second identity, Review, commitment or thread store; does not
choose bucket thresholds or post externally.

### R1.C — V2 shell and interaction contract

Worktree: `codex/v2-report-ia`.

Owns:

- six-mode shell: Scan, Explore, Diagnose, Review, Act, Close loop;
- versioned personal/shared view definitions;
- sorting, filtering, grouping, lens and collapsed-section state;
- canonical-versus-visible counts;
- deep-links and feature flags;
- accessibility and interaction tests.

Coverage: A1, A4, A5, A9, A11, A12, D1, D4, D8, D13, D14.

Does not calculate new metrics or own shared workflow writes.

### R1 merge sequence

Development may overlap, but contracts merge in this order:

1. routing/measurement contract and fixtures;
2. identity/action/review contracts and adapters;
3. report shell consuming the landed contracts.

The canonical checkout runs full no-write verification after every merge.

## Release 2 — Small-change consolidation

Objective: deliver the Sheet's smaller UX and accuracy requests without turning
them into dozens of independent production changes.

Each batch is one vertical, testable release. A request remains linked to its
original Sheet ID, but related items share implementation and QA.

### Batch U1 — Copy, labels and formatting

Coverage: A2, A3, A6, A8, A9, B7, C13, F3.

- rate deltas use approved pp/% notation;
- provenance and comparison periods are visible;
- favorable/unfavorable color and triangle behavior is tested;
- internal criteria leakage is removed;
- mover disagreements explain 4-week versus WoW.

Why bundled: shared formatter, copy registry and visual regression suite.

### Batch U2 — Table interaction consistency

Coverage: A4, A5, A12, D4, D8, D13.

- mover and bucket sorting;
- collapsible sections and previews;
- country and geo filters after governed fields exist;
- common comparison-lens behavior;
- saved/restored view state.

Why bundled: one versioned interaction-state contract.

### Batch U3 — Drawer diagnosis

Coverage: A7, B10, B11, D5, E1, E2.

- concise paid-drop and serious-CVR diagnosis;
- lead-time refinement;
- funnel data verification;
- language only after authoritative identity/coverage exists.

Why bundled: one CE diagnosis schema and drawer component family. A7/B10 may
remain disabled if their upstream data is not ready.

### Batch O1 — Action and review usability

Coverage: A10, B13, C2, C11, E5, E6, F14.

- correct labels/owners;
- review selection and status;
- known/managing expiry;
- same/prior-week history;
- post-call and mid-week follow-up views.

Why bundled: one workflow state machine and identity model.

### Batch S1 — Slack consistency

Coverage: F3–F8, F10, F14, F15.

- compact summary and separate priority threads;
- correct channel registry;
- report/Slack evidence parity;
- alert-thread attention and follow-up states;
- transcript context only after Review approval.

Why bundled: one alert payload contract and thread registry. Items that change
cadence or density remain configuration decisions rather than forks of the
message engine.

## Release 3 — Market Glance and Review integration

Objective: eliminate manual re-entry while keeping one workflow system, human
ownership and provenance.

### R3.1 — Contract and ownership discovery

Worktree: `codex/v2-market-glance-contract` after authenticated API access and
joint ownership are confirmed.

- compare Market Glance and weekly metric definitions and snapshots;
- validate CE lineage, owner identity, audit, commitment and thread contracts;
- define shared run/artifact/signal IDs and deep-links;
- expose the weekly artifact through a versioned read-only contract;
- produce no-write integration fixtures.

### R3.2 — Read-only linked pilot

- weekly report links to the appropriate Market Glance CE/audit/commitment view;
- report can display read-only audit/owner/status summaries;
- Market Glance shadows the weekly canonical artifact beside its stored snapshot;
- all metric and identity differences are measured and reviewed;
- no workflow or Slack writes originate from the weekly build.

### R3.3 — Granola shadow workflow

Owned with the Market Glance Review integration; repository placement is decided
after the shared contract is approved.

- centrally approved eligible transcript source;
- meeting-to-market/week association;
- provenance-linked suggested comments, decisions, actions and owners;
- exact-ID then governed-alias CE matching;
- undiscussed and low-confidence reconciliation queues;
- suggestions attach to Market Glance/shared Review records;
- no comment/action/Slack writes from generated output.

Reviewed automation is a later rollout state, not part of shadow completion.

## Release 4 — Diagnosis and opportunity features

These are vertical modules after shared contracts stabilize.

| Slice | Sheet coverage | Entry condition |
|---|---|---|
| Sanity overlay | E3, E4, G2 | approved CVR/TR/completion definitions |
| Scale/rollback | C4, G4 | Scale-Up shadow precision accepted |
| Price parity | G3 | competitor/TGID identity and benchmark quality proven |
| Channel mirror | G5 | channel eligibility and ownership contract |
| Prepurchase | D5, D6 | lead-time/availability qualification and owner |
| New CE operations | C6, D9, D10, D15, G11 | authoritative launch/MMP automation |
| Opportunity wave 2 | G6–G10 | each source passes freshness/coverage validation |

One new data-source module runs at a time. Each must state dollar impact,
evidence, recommendation and owner route before entering Scan or Slack.

## Explicit later/separate scope

Unless reprioritized, these do not block V2.0:

- D2/D3: broader OKR or monthly WBR products;
- D11/D12: Band Explorer or multi-dashboard product shells;
- E12: general task tracker;
- G1: automatically ingested external/world context;
- H7/H8: operating programs and portfolio targets;
- user-authored metric formulas;
- replacement of Omni or other source dashboards.

## Decision gates

Decisions are made just before the work they unblock, not all upfront.

### Contract-locking before R1

- D3: authoritative week boundary;
- D9: durable action/store identity;
- D11: personal versus shared view ownership;
- V1/V2 selection and retirement policy.

### Required before relevant feature merge

- D1/D2: headline clock and rate formatting;
- D4/D5/D6: materiality, fluctuation volume and seasonality action;
- D7/D8: known/managing and Scale-Up surface;
- D10: Slack density;
- D12: role presets;
- D13: authoritative Review thread;
- D14: meeting-derived content approval.

Tunable thresholds may change during shadow; identity, schema, metric basis and
week semantics cannot.

## Definition of ready for every Sheet request

A Sheet item enters a code batch only when it has:

1. a normalized outcome and retained original ID/wording;
2. a named user and affected markets;
3. explicit metric/source provenance;
4. surfaces and consumers listed;
5. dependencies and decisions resolved or isolated;
6. acceptance criteria;
7. a fixture week and expected evidence;
8. V1 compatibility expectation; and
9. a separate external-rollout step if it writes or posts.

Items that fail this test stay `DECIDE`, `UPSTREAM` or `LATER`; they do not get
quietly implemented from ambiguous wording.

## Definition of done for a batch

- unit/boundary tests and fixed historical fixtures pass;
- market/global parity is checked where applicable;
- report, Sheet and Slack previews consume the same contract;
- no-write E2E passes;
- all changed Sheet IDs have acceptance evidence;
- V1 golden outputs remain unchanged unless an approved P0 fix says otherwise;
- owner/product review accepts historical or UI diffs;
- code completion and production rollout are recorded separately.

## Rollout ladder

```text
local fixture -> historical comparison -> current-week shadow
-> one-market feature-flag pilot -> one full weekly cycle
-> multi-market expansion -> explicit default-engine cutover
```

At every rung, rollback means disabling V2/Review and retaining the V1 artifact,
not attempting to reconstruct the old weekly after the fact.
