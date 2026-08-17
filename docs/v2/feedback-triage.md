# Weekly Market Report — Feedback Triage

Status: first evidence-backed pass, 2026-08-14.

Source: Google Sheet `Market Weekly Report — Product Roadmap (Consolidated
Feedback & Requests)`, tab `Roadmap` (`gid=529122362`). The source Sheet was read
only. This triage uses the repository on `main` and the deployed North America
report for w/c 2026-08-02 as evidence; the Sheet's `Status` field is not treated
as authoritative because it has already drifted from the code.

## V2 product north star

**V2 is an interactive, user-customisable weekly decision workspace.** It should
help each market user reduce the report to the CEs, lenses and actions relevant
to them without creating separate metric definitions or private versions of the
truth.

The deployed V1 already supplies an important part of this north star in All-CE:

- search and multi-dimensional filtering;
- sorting and expandable metrics;
- saved views;
- watchlists;
- custom CE groups;
- highlight rules;
- CE selection and group assignment;
- interactive CE drawers and action/note history.

V2 should preserve and extend those capabilities across the rest of the weekly.
It should not rebuild All-CE from scratch. “Customisable” means user-controlled
views over one governed measurement/identity contract, not user-defined formulas
that make market reports incomparable.

## Source inventory

The Roadmap contains **99 items**:

The source IDs intentionally/currently skip `E10` (`E9` is followed by `E11`
and `E12`), so ID-range audits must not treat `E10` as a missing request.

| Group | Items |
|---|---:|
| A. Report IA & UI | 12 |
| B. Metrics & accuracy | 13 |
| C. Bucket logic & actions | 13 |
| D. New sections & features | 15 |
| E. Actions, comments & follow-ups | 11 |
| F. Alerts & cadence | 15 |
| G. CE opportunity flags | 11 |
| H. Reliability & engineering | 9 |

The Sheet currently labels 2 items P0, 40 P1, 52 P2, 4 P3 and 1 unprioritized.
Its status mix is 54 Planned, 11 In progress, 10 Bug open, 7 Clarify, 4 Shipped
and 13 Parked. Those labels are useful stakeholder input, but V2 ordering below
also accounts for dependency, current implementation evidence and weekly safety.

## Classification rules

- **BUILT** — behavior is present in the current code/deployed weekly. Keep a
  regression test; do not rebuild it as V2 scope.
- **PARTIAL** — useful substrate or UI exists, but the requested outcome is not
  complete.
- **P0 CURRENT** — correctness, data loss, routing, automation, security, or
  inability to verify the current weekly. Fix/prove this without changing the
  intended V1 product behavior.
- **MUST V2** — required product/architecture work for the first V2 release,
  after the P0 baseline is protected.
- **DECIDE** — a product/metric choice is required before implementation.
- **LATER** — additive feature or polish that should not hold the first V2
  release.
- **UPSTREAM/EXTERNAL** — ownership or deployment is outside this repository;
  the weekly may consume the result but cannot solve it alone.

## Sheet status corrections to make later

These are the clearest places where the Sheet and current evidence disagree.

| ID | Sheet says | Evidence-backed state | Evidence / note |
|---|---|---|---|
| E8 | In progress | BUILT; needs regression coverage | `f8db3ed` CID-keyed Perf cells + stable order are on `main` |
| H1 | Planned | BUILT; needs regression coverage | CM1/conversion guard shipped in `92848ae` and related preflight commits |
| H2 | Planned | BUILT | `run_market_alert_sweep.py` verifies deployed report against fresh render before sweep |
| C3 | Clarify | BUILT policy, product confirmation still useful | down-fluctuation CEs already in Losing Money are suppressed in `buckets.seasonality()` |
| F5 | Planned | BUILT | Slack payload already creates separate Losing Money / Fluctuation down / up thread replies |
| B11 | Bug open | BUILT in weekly CE drawer | live drawer shows LP2S, S2C, C2O and CVR; clarify if request targets another CE page |
| E6 | Bug open | BUILT/PARTIAL; cross-market verify | live drawer shows prior-week note history; verify same-week and every market |
| F10 | Shipped | CONTRADICTED by repo | NA still maps to `CNSHDD2H1` / `#mkt-usa`, not `#adhoc-usa`; verify intended production route before posting |
| F4 | Shipped | VERIFY | current RPC bucket thread columns do not plainly show both Revenue and Orders; request may refer to a different alert surface |

## P0 — protect the current weekly first

These are not V2 feature work. They establish whether the current weekly is
correct and safe enough to use as the migration baseline.

| IDs | Required outcome |
|---|---|
| B1 | Reconcile ROI with paid-spend maturity/lag and prevent known under-reporting |
| B2 | Lock the authoritative Sun–Sat versus Monday-start contract and label cross-surface differences |
| B3 | Fix or disprove child-CE ROI aggregation errors |
| B4, B12 | Publish one CVR definition per surface, with explicit provenance where two legitimate bases coexist |
| E7 | Prove comments cannot disappear on a weekly refresh; recover/flag any historical gap |
| E8 | Add reorder/add/remove/duplicate-CID regression tests around the shipped Perf fix |
| F10 | Resolve the NA CTA/channel contradiction before the next write/post |
| H1 | Add a regression fixture for composite city-suffixed CEs and zero-conversion classification |
| H3 | Add freshness/preflight failure so a stale weekly cannot look successfully published |
| H4 | Add V1/V2 contracts, deterministic fixtures, and no-external-write end-to-end verification |
| H6 | Rotate exposed/reused Slack credentials and keep tokens out of commands, logs, and source |

Architecture-derived P0 items not explicitly represented in the Sheet:

| ID | Required outcome |
|---|---|
| ARCH-P0-1 | Reconcile deployed footer `amount_revenue_usd` with embedded `sum_revenue_predicted` metadata |
| ARCH-P0-2 | Resolve Fluctuation copy advertising ROI filters while the Python engine treats ROI only as a verdict |
| ARCH-P0-3 | Replace hard-coded follow-up week layouts with header-driven/versioned discovery; current modified script only defines 2026-07-20 and 2026-07-26 |
| ARCH-P0-4 | Emit structured module health so required missing enrichments block publish instead of silently disappearing |

## Already built — preserve, verify, or relabel

| IDs | Current behavior |
|---|---|
| A3 | Movers label their lens as 4-WK or WoW; expanded All-CE metrics label W0/W-1/WoW/YoY |
| A8 | Losing Money already uses a small status vocabulary: Full waste, Bleeding, Eroding, Recovering |
| B6 | Paid-basis correction is represented in current code/history; retain a Vatican/Omni comparison fixture |
| B11 | Weekly CE drawer already renders LP2S, S2C, C2O and aggregate CVR |
| C3 | Losing Money wins over duplicate down-fluctuation routing |
| E8 | Perf input follows CID and stable row order |
| F5 | Alert bucket tables are separate thread replies |
| H1 | Full-waste CM1/conversion guard is on `main` |
| H2 | Alert sweep has a deployed-versus-fresh verification gate |

Items marked “Shipped” in the Sheet but dependent on external scheduling or
ambiguous surfaces remain verification work rather than accepted facts: F2,
F4, and F10.

## Partial — extend existing substrate, do not rebuild from scratch

| IDs | What exists | Missing outcome |
|---|---|---|
| A6 | favorable/unfavorable color helpers exist | reproduce and test the reported positive-WoW triangle case |
| A11 | headline has raw, structural and 4-week mover reads | decide the single primary headline clock and rewrite verdict rules |
| B5 | report has a $1k/4wk materiality view and the Sheet has an ungated full view | decide adaptive/$100 coverage behavior and where it belongs |
| B7 | drawer and several surfaces say predicted revenue | make provenance consistent everywhere |
| B8 | `build_global.py` exists | prove global CVR parity and complete the requested re-sweep |
| C4 | Scale-Up engine is computed | current report hides the table; approve rule and expose the intended surface |
| C5 | monthly season tags and LY context exist | define the requested V2 seasonality model |
| C6 | Lifecycle/New CE logic exists and is not PP-only | clarify whether “all launches” means every launch or only actionable cohorts |
| C10 | movers combine 4-week and WoW lenses | add the requested 14d-vs-prior-14d reversal lens if approved |
| C11 | action continuity shows prior action/no-action | add “known & managing” semantics and decide suppress versus demote |
| C13 | snapshot emits transition data | make lifecycle/transition tags consistent in the summary surface |
| D5 | drawer has lead-time bands and W-1 comparison | split same-day from 1–2d and finish the requested change display |
| D6 | Prepurchase visibility table exists | add actionable qualification, owner, and recommended action |
| D9 | New CE and Iteration/Untapped sections exist | define whether a separate deep-dive product is still required |
| D10 | Iteration consumes MMP data | production ownership, freshness, and upload path remain unclear |
| D13 | YoY exists in headlines/drawer/expanded All-CE | decide the always-visible weekly comparison placement |
| E1 | drawer has channel, funnel, TGID, lead-time and country RCA | generate the concise “why paid dropped” summary and language attribution |
| E2 | funnel breakdown and Slack context substrate exist | add serious-dip qualification and bottom-3-of-5-week logic |
| E3, E4 | TR and completion metrics are visible | add sanity thresholds/routing only if approved |
| E5 | notes, Slack threading, actions and follow-ups exist | add explicit review selection, owner tagging, and close-out workflow |
| E6 | prior note history is visible in the live drawer | verify same-week visibility and all-market consistency |
| F3 | report distinguishes 4-WK versus WoW | ensure the alert itself explains “grew WoW but flagged as Drop” |
| F4 | alerts contain revenue diagnosis and RPC tables | establish which table must show Revenue/Orders and verify deployed formatting |
| F8 | BigQuery auto-RCA already generates CE threads | add transcript/WBR context and “undiscussed” detection |
| F14 | Thursday/follow-up tooling exists | productize the requested post-call mid-week nudge and future-week tab handling |

## Must-build candidates for the first V2 release

These are candidates pending the combined-list review; “must” here means they
solve repeated cross-market problems or are required to make V2 actionable.

### Report and prioritization

| IDs | Outcome |
|---|---|
| A1 | Action-focused TLDR/Pareto summary with an auditable impact basis |
| A4, A5 | Sort the headline/mover and bucket tables by the decision metrics users actually inspect |
| A9 | Remove internal criteria notation/bracket leakage and define digest states clearly |
| A10 | Correct action/comment ownership labels and support explicit multi-owner attribution |
| A11 | Adopt an approved headline clock rather than letting competing periods imply different verdicts |
| A12 | Collapsible sections with a stable preview and jump navigation; remember the user's view state |
| B13 | Repair the BGM/owner selector used for Slack attribution and persist stable user identity |
| D1 | Revenue target/run-rate section if the target source and cadence are authoritative |
| D4 | Country filtering in All-CE/search |
| D8 | Geo/non-geo filtering using a governed CE classification |
| D13 | Make WoW/4-week/YoY lenses consistently selectable or expandable across core tables |
| D14 | Hard-cap market signals to an approved top-N and preserve a route to the full Digest |

### Bucket/action quality

| IDs | Outcome |
|---|---|
| C1 | Reduce noisy cohorts using coverage/materiality evidence, not an arbitrary row cap |
| C2 | Expand action vocabulary beyond Perf-only actions and record already-actioned/self-recovering states |
| C4 | Ship an approved sustained high-ROI/flat-click Scale-Up signal |
| C6 | Complete the agreed all-launch New CE scope |
| C11 | Support “known & managing” without erasing the audit trail |
| E9 | Store-backed, CE-keyed Perf decisions and four-week history if the Apps Script/store migration is approved |

### Diagnosis and operations

| IDs | Outcome |
|---|---|
| D7 | Actionable paused/dormant campaign view, distinguishing intentional pauses from inventory/supply issues |
| E1, E2 | Concise paid-drop/CVR diagnosis using the drawer's existing measurement substrate |
| E5 | Weekly Audit workflow with selection, owner routing and next-week closure |
| E11, F8 | Review mode that combines BGM notes, approved Granola transcript evidence and quantitative RCA, while surfacing undiscussed CEs |
| F11 | Add Central Live Entertainment coverage and its channel contract |
| F12 | Archive report/action history into an approved durable analytics sink |
| G2 | Unify CVR/TR/completion sanity flags rather than building three unrelated alert systems |
| G3 | Price-parity signal, only after competitor/TGID identity and benchmark quality are proven |
| G4 | Post-event scale-down/revert control |
| G5 | Google-to-Bing/channel-mirror opportunity |
| H5 | One validated market, URL and Slack-channel registry |

## Decisions required before code

| IDs | Decision |
|---|---|
| A2 | Rates legitimately change in percentage points; should the request standardize display language rather than convert pp to percent? |
| B2 | Is Sun–Sat the product contract, or must the weekly align to Monday-start CE DB views? |
| B5, C1 | Should coverage be controlled by spend floor, dollar impact, adaptive market coverage, top-N, or a combination? |
| B9 | Is the Ledger a decision/action layer over Omni, or another general analytics dashboard? |
| C3 | Confirm Losing Money owns duplicate down-signals; define whether upside may coexist |
| C7 | Approve the fluctuation volume floor using backtest evidence (10 versus roughly 40–50 orders/week) |
| C8 | Decide whether flat-revenue margin erosion is a Defend-routing trigger or a visible overlay, and define its metric basis |
| C9 | Should seasonality be a weekly monitored signal or only an opt-in action after about four consecutive weeks? |
| C12 | Define who supplies structured seasonality input and whether it changes routing or only context |
| D9, D11, D12 | Decide whether separate dashboards are products or linked views of the Ledger |
| F1 | Earlier Monday delivery versus paid-attribution maturity/accuracy |
| F6, F7 | Keep/drop the RPC-up alert and decide whether Slack duplicates or summarizes the report |
| F9 | Product grouping for CSEE+Nordics versus merely sharing a Slack channel |
| F13 | Official feedback intake channel and owner |

## Later / separate products

| IDs | Reason to defer from first V2 cut |
|---|---|
| A7 | Language breakdown after language identity/coverage is verified; drawer data can be extended without blocking core customization |
| D2, D3, D11, D12, D15 | separate dashboard/cadence or additive automation work |
| E3, E4 | fold into G2 rather than ship isolated sanity tables |
| E12 | task-management product scope beyond the core weekly action loop |
| F6, F7, F13, F15 | density, process, or attention-management choices after core alert reliability |
| G1 | AI external-context ingestion after deterministic signals and review workflow are trustworthy |
| G6, G7, G8, G9, G10, G11 | valuable opportunity modules, but independent vertical slices after G2–G5 and shared contracts |
| H7, H8 | operational programs/targets, not foundation architecture |

## Upstream or external coordination

| IDs | Dependency |
|---|---|
| B10 | Omni landing-page tagging/data-quality ownership |
| E9 | Google Apps Script/store schema and deployment |
| E11 | Granola access, data policy, identity matching and connector availability |
| F1, F2, F9 | scheduler/cadence and market operating model |
| F12 | BigQuery destination schema, retention and Replit consumer contract |
| H3 | scheduler/runtime monitoring outside the report renderer |
| H6 | credential rotation and secret owner |
| H9 | ongoing product-management operating model; treat as a delivery principle, not a code feature |

## Recommended worktree sequence

No feature worktree should be created until the current dirty
`alert/followup_actioning.py` change is classified and the planning documents are
committed intentionally.

### 1. `codex/weekly-baseline-contracts` — merge first

Owns H4 and ARCH-P0-1/2/4:

- frozen V1 fixtures and characterization outputs;
- executable snapshot/consumer contracts;
- metric provenance assertions;
- no-write end-to-end verification;
- separate V2 artifact paths and V1 default behavior.

It must not change bucket membership or production copy unless a discrepancy is
explicitly approved.

### 2. `codex/weekly-current-correctness`

Owns B1/B3/B4/B12/E7/F10/H1/H3 plus E8 regression tests. Merge before any V2
engine changes. Every behavior change needs an approved before/after fixture.

### 3. Parallel V2 work, at most three active worktrees

| Worktree | Primary IDs | High-conflict ownership |
|---|---|---|
| `codex/v2-routing` | B5, C1, C3, C4, C6, C7, C9, C11 | `buckets.py`, `alerts.py`, V2 routing fields |
| `codex/v2-workflow-contract` | C2, E5, E6, E9, F14 | Market Glance/shared workflow references, action adapters, Sheet previews, follow-up interoperability |
| `codex/v2-report-ia` | A1, A9–A11, D1, D4, D13, D14 | report template and V2-only presentation |

Opportunity modules E1/E2/G2–G5 start only after the shared V2 measurement and
routing contracts land; otherwise each will invent its own metric basis.

## Weekly-safety gates

Every worktree must prove:

1. V1 remains the default engine.
2. The frozen V1 snapshot, bucket memberships, Sheet preview and Slack preview
   are unchanged unless the backlog item explicitly approves a V1 hotfix.
3. V2 writes separate local artifacts and cannot write Sheets, post Slack, or
   stage/deploy production.
4. All human input remains keyed by market + CE + week + bucket/lane.
5. A schema/health/preflight failure stops publish rather than degrading
   silently.
6. Consumer changes land after, or together with, the contract fields they use.
7. External rollout is a separate approved step after code verification.
