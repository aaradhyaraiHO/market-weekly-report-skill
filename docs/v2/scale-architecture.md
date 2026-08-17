# Weekly Report V2 — Multi-Market Scale Architecture

Status: proposed target architecture, 2026-08-14.

This design incorporates lessons from the current weekly engine and the public
client of Market Glance at
`agentic-pm-architect--fabriziomalato1.replit.app/market-glance`.

The weekly is delivered every week to all configured markets and to Headout
overall. V2 must therefore scale by adding logic once, not by adding a new code
path, query set, report implementation and workflow for every market.

## Discovery: what Market Glance already provides

Public client inspection shows an authenticated WBR collaboration application
with routes and interfaces for:

- Market and Focus-collection performance from stored BigQuery snapshots;
- weekly/monthly performance grains, filters, sorting and user-restored state;
- Targets and collection goal performance;
- governed Universe/Focus CE identity and owner roles;
- owner-to-Slack-user mappings and per-market route configuration;
- WBR Audit candidate selection, immutable run history and delivery outcomes;
- dedicated CE audit threads plus a market summary;
- reconciliation of discussion into Actions, Open Topics and Decisions;
- a commitment tracker, reminders and market digests;
- ThreadPulse, new-launch/MMP, ILF and Google Sheet integrations;
- health/admin surfaces for BigQuery snapshots, sync jobs and routes.

The application requires authentication, so this assessment proves exposed
product contracts and client behavior, not live data correctness or operational
readiness. Its owners must validate backend guarantees before V2 depends on it.

## Architectural conclusion

Do not rebuild a second collaboration platform inside the generated weekly
report.

Recommended ownership:

| Capability | Authoritative owner |
|---|---|
| metric definitions and CE-week facts | Weekly Decision Data Product |
| bucket/signal qualification and reasons | Weekly Decision Data Product |
| market and Headout report artifacts | Weekly Decision Data Product |
| personal analytical view state | report shell or Market Glance, by surface |
| CE/market workflow identity and role mapping | Market Glance/shared identity registry |
| Review/Audit runs and immutable history | Market Glance |
| Actions, Open Topics and Decisions | Market Glance commitment store |
| Slack thread bindings and delivery history | shared registry, operationally owned by Market Glance |
| transcript-derived suggestions | Review integration, attached to Market Glance records |
| report build/publish state | Weekly Decision Data Product run manifest |

The existing Sheet/Apps Script note/action backend becomes a compatibility
adapter during migration. It must not become a second long-term workflow store.

## Current scaling constraints

The V1 orchestrator currently:

1. loops through configured markets and queries/builds each independently;
2. assembles Headout through a separate `build_global.py` path with another set
   of global queries and duplicated assembly logic;
3. renders many market snapshots into a self-contained HTML;
4. validates only North America through a hard reference gate; and
5. fans alerts/follow-ups through code-level market/channel mappings.

Consequences:

- BigQuery work and expensive enrichments are repeated;
- global and market logic can drift;
- a correction must be propagated across multiple builders/consumers;
- one market can fail after others succeed without a first-class run manifest;
- validation strength differs by market;
- adding markets requires code/config edits in several places;
- large embedded HTML payloads grow with the number and depth of CEs; and
- report, Sheet, Slack and Market Glance can each retain their own snapshot.

## Target: one weekly decision data product

Compute the entire Headout CE universe once per report week and rule version.
All scopes are projections of the same canonical run.

```text
governed sources
      |
      v
canonical CE x week facts
      |
      +--> metric/provenance layer
      |
      +--> signal/routing layer
      |
      +--> scope projector
              |--> each market
              |--> regional/group views
              `--> Headout overall
      |
      +--> immutable artifact registry
              |--> weekly web report
              |--> Market Glance
              |--> Slack preview/poster
              `--> Sheet/export adapters
```

Headout is aggregated from the same canonical CE rows used by markets. It is
not a separately interpreted dataset. Shared measures must satisfy Headout =
sum of included market components, subject only to declared unattributed or
excluded rows.

## Canonical data grains

### CE-week fact

Primary key:

```text
run_id + week_start + combined_entity_id
```

Carries:

- governed market and CE identity;
- raw metric numerators and denominators;
- display measures with basis/provenance IDs;
- data-through and maturity state;
- 12-week/LY references required by routing;
- enrichment health and availability; and
- source snapshot/revision identifiers.

Ratios remain derivable from additive components so market, region and Headout
aggregates never average CE percentages.

### Signal fact

Primary key:

```text
run_id + scope + combined_entity_id + signal_key + rule_version
```

Carries:

- qualification result and reason codes;
- severity/materiality and dollar impact basis;
- recommended action class and owner route;
- overlap/single-home result;
- evidence references; and
- prior signal/action linkage.

### Scope summary

Primary key:

```text
run_id + scope_type + scope_id
```

Carries additive totals, headline inputs, contribution rankings, coverage and
module health. Headline verdicts are deterministic consumers of these fields.

## Run and artifact identity

Every weekly run has a manifest:

```text
run_id
report_week
schema_version
metric_definition_version
rule_version
source_revisions
started_at / completed_at
data_through
scope_statuses
module_health
artifact_ids
publish_status
```

Artifacts are immutable. A corrected rerun receives a new `run_id` and an
explicit supersession link. Report, Slack and Market Glance must display or log
the same `run_id`; “latest” is resolved only at the registry boundary.

## Multi-market configuration as data

Replace scattered code mappings with a validated registry containing:

- scope ID, display name and business-market membership;
- active dates and aliases;
- timezone and delivery schedule;
- report URL/slug;
- required and optional modules;
- Slack report/audit/status destinations and user groups;
- owner/role identity mappings;
- pilot/feature flags; and
- fallback/escalation owner.

Changes are reviewed configuration records, not code forks. The run preflight
rejects overlaps, unknown CEs, missing required routes and invalid Slack IDs.

Regional/group scopes such as CSEE + Nordics are composable memberships, not a
new calculation engine.

## Consumer contract

Each consumer declares supported schema versions and reads by `artifact_id` or
`run_id + scope`.

### Weekly report

- Scan/Explore/Diagnose presentation of canonical metrics/signals;
- deep-links into Market Glance Review/Audit/commitment records;
- optional read-only workflow status returned through an API;
- personal views can change presentation, never the facts.

### Market Glance

- consumes the weekly run instead of independently redefining weekly metrics;
- owns Focus/Universe workflow context, audits, commitments and Slack identity;
- links every workflow record to `run_id`, CE ID, signal key and report deep-link;
- may enrich with targets/MMP/ILF context without overwriting weekly facts.

### Slack

- payloads are generated from the same published artifact;
- thread binding is registered once and reused by alerts, audits and follow-up;
- message IDs, channel and delivery status are stored against the run/signal;
- posts remain an explicit, idempotent operational step.

### Sheets/exports

- treated as views/input adapters, not alternate metric stores;
- stable IDs and owned columns are mandatory;
- human values round-trip through the authoritative workflow store;
- a failed mirror does not mutate canonical facts.

## Build-once pipeline

Recommended stages:

1. **Resolve** week, config revision and eligible universe.
2. **Extract once** per source/window at the full-universe grain.
3. **Normalize** identities and metric components.
4. **Measure once** at CE-week grain.
5. **Route once** using versioned rules.
6. **Project scopes** for every market, group and Headout.
7. **Validate** parity, completeness, freshness and module health.
8. **Register immutable artifacts** without publishing.
9. **Render consumers** from registered artifacts.
10. **Shadow/diff** against the active run.
11. **Publish atomically** by updating the active-run pointer.
12. **Notify separately** through idempotent Slack/export jobs.

One market's optional enrichment may degrade with an explicit warning. A
required metric or identity failure blocks that scope. Headout cannot publish
as healthy when a material included scope failed.

## Performance and delivery model

Avoid one ever-growing self-contained multi-market HTML as the long-term
serving model.

Recommended progression:

1. keep static V1 artifacts for rollback;
2. produce one compact summary artifact per scope plus chunked CE detail data;
3. lazy-load CE drawers and long tables by artifact/run ID;
4. cache immutable responses aggressively;
5. precompute common summaries and group aggregates;
6. retain a printable/exportable static artifact for audit and fallback.

This reduces initial payload and allows Headout and long-tail markets to share
the same application shell without embedding every CE in every page.

## Reliability at scale

Required controls:

- retries operate per stage/scope with idempotency keys;
- the run manifest shows pending, healthy, degraded and failed scopes;
- stale source revisions fail freshness checks before publish;
- historical backfills cannot change the active current-week pointer;
- publish is atomic and reversible;
- Slack, Sheet and deployment credentials are isolated by job;
- all external writes have ledgers and deduplication;
- every market has at least smoke/parity fixtures, with deeper rotating fixtures;
- long-tail and zero/sparse-data markets are explicit test classes; and
- cost/row/runtime metrics are recorded per source and stage.

## Product behavior across scales

The same six modes apply at market and Headout level:

| Mode | Market | Headout |
|---|---|---|
| Scan | top local decisions | top contributing markets and cross-market decisions |
| Explore | CE/country/owner views | market/region/CE views with full-population coverage labels |
| Diagnose | CE evidence | market contribution, then CE evidence |
| Review | linked market audit state | coverage/completion across market review cycles |
| Act | local owner commitments | cross-market escalations and unresolved ownership |
| Close loop | CE recovery and follow-up | portfolio recovery, overdue and repeated-signal patterns |

Headout must not simply concatenate every market's top-N. It first ranks market
contributions and systemic signals, while preserving drill-down to the exact
market/CE facts.

## Revised implementation program

### Foundation

1. freeze V1 artifacts and add executable contracts;
2. define run/artifact/config registry contracts;
3. build canonical full-universe CE-week fixtures;
4. prove market/global parity from one fact set;
5. add consumer contract tests for report, Market Glance, Slack and Sheets.

### Market Glance integration discovery

Before building workflow features:

- confirm its repository owner and roadmap;
- inspect authenticated API and database contracts;
- identify authoritative CE lineage and workflow keys;
- verify audit/thread idempotency and permissions;
- compare its BigQuery metric definitions to the weekly;
- choose which system hosts the shared identity/thread registry; and
- agree a versioned ingestion/API contract for weekly artifacts.

### Migration

- weekly report first links to existing Market Glance records read-only;
- Market Glance shadows the canonical weekly artifact alongside its snapshot;
- metric diffs are reconciled before switching its performance source;
- new audits/actions bind to canonical run/signal IDs;
- legacy report notes/actions become read-only history after migration;
- only then retire duplicate Apps Script/Sheet workflow paths.

## Non-negotiable invariants

1. A metric or signal is implemented once for all scopes.
2. Headout is derived from the same CE facts as its markets.
3. Market-specific behavior is configuration unless the source data genuinely
   differs.
4. Report, Market Glance, Slack and Sheets identify the same run, CE and signal.
5. Collaboration failures cannot block weekly computation or artifact creation.
6. A weekly build cannot post, notify or overwrite human inputs.
7. Generated context never becomes a human decision without provenance and the
   approved Review policy.
8. No V1 path is removed before shadow, pilot and rollback gates pass.
