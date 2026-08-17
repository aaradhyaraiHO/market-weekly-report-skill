# Weekly Report V2 — Product Roadmap

Status: proposed product cut, 2026-08-14.

Inputs:

- 99-item consolidated Roadmap feedback Sheet;
- deployed North America weekly for w/c 2026-08-02;
- current `main` implementation and operational handoffs;
- `feedback-triage.md`, `architecture.md`, and `migration-plan.md`.

Recommended defaults and worktree blockers for the open product choices are in
`decision-brief.md`. The Review workflow, Slack topology and Granola ingestion
contract are specified in `review-mode.md`; customization state is specified in
`interaction-spec.md`. Multi-market computation and Market Glance integration
boundaries are specified in `scale-architecture.md`.

## Product goal

V2 is the **current weekly report, improved incrementally**, with a focused
review layer that turns selected CE signals into week-over-week market notes and
follow-up. The existing sections, metric depth, buckets, drawers and report
delivery remain the base product; V2 does not replace them with a separate
platform or radically different report.

The concrete outcome is:

> A market user opens the familiar weekly, finds the few CEs worth discussing,
> records the team's diagnosis/decision against that CE and report week, and can
> see next week whether the issue was addressed or recovered—without manually
> rebuilding the evidence in a running-notes Sheet.

It should answer, in order:

1. **What deserves attention?**
2. **Why did it move?**
3. **What action is recommended and who owns it?**
4. **What did we decide?**
5. **Did it improve next week?**

Customization must operate over one governed measurement and identity model.
Users can change views, filters, ordering, grouping, visible lenses and personal
watchlists; they cannot create conflicting metric definitions inside the weekly.

## Product shape

The default experience remains the current report. “Modes” are lightweight
views/actions within that report, not six new applications or a replacement
navigation system. Review is the primary net-new workflow.

| Mode | User question | Main surface |
|---|---|---|
| **Scan** | What are the few things that matter this week? | action TLDR, target/run-rate, top signals |
| **Explore** | What does this market/CE look like under my lens? | saved views, filters, groups, sortable tables |
| **Diagnose** | Why did this CE move? | drawer, decomposition, funnel/TGID/channel/lead-time |
| **Review** | What did the BGM/team discuss, and what still needs review? | weekly notes, mentions, lite audits, meeting evidence, Slack threads |
| **Act** | What will we do, and who owns it? | governed action states, comments, owners, Slack thread |
| **Close loop** | Was it handled and did it recover? | prior decisions, known/managing state, follow-up outcome |

The modes share CE identity, week, metrics, bucket membership and action state.
There should not be separate metric implementations for the report, Sheet and
Slack.

## Reuse — already built and strategically valuable

Do not rebuild these capabilities. Protect them with fixtures, then extend them.

### Interactive workspace substrate

- All-CE search and sorting.
- Expandable W0/W-1/WoW/YoY metrics.
- Grouping and subtotals.
- Saved views.
- Watchlists.
- Custom CE groups and selection.
- Highlight rules.
- CE drawers and Omni links.

### Diagnosis substrate

- 12-week CE measurement history.
- raw and structural market movement.
- Shapley revenue decomposition.
- channel, funnel, TGID, booking-window and country breakdowns.
- Losing Money C1–C5 engine.
- L3W CM1-per-conversion/RPC fluctuation substrate.
- Lifecycle, New CE and Iteration/Untapped substrate.
- Prepurchase visibility.

### Action substrate

- GM notes and history.
- action selectors and mandatory rationale.
- CE/week/bucket action identity.
- Slack thread creation and permalinks.
- prior-week action context.
- CID-keyed Perf Sheet preservation.
- alert dry-run/post separation and deployed-report verification.

The current one-note-per-CE/week model and note-created Slack threads are only a
migration substrate. Public inspection indicates Market Glance already has WBR
Audit runs, immutable history, Slack owner mappings, dedicated threads and a
commitment tracker. V2 should integrate those capabilities rather than create a
second Review store in the report repository. Backend readiness and contract
ownership still require validation with the Market Glance owners.

## Release model

### R0 — Current-week safety baseline

R0 is mandatory before V2 feature work can affect shared producer/consumer
contracts. It does not redesign the weekly.

Scope:

- H4: executable V1/V2 contracts, fixtures and no-write E2E verification.
- B1/B3/B4/B12: ROI/CVR correctness and provenance.
- E7/E8: comment and Perf-input durability tests.
- F10: correct NA action/Slack destination.
- H1: full-waste regression fixture.
- H3: freshness/automation preflight.
- H6: Slack credential rotation and secret hygiene.
- ARCH-P0-1: predicted-revenue footer/metadata agreement.
- ARCH-P0-2: Fluctuation ROI description/engine agreement.
- ARCH-P0-3: future-week follow-up tab/layout discovery.
- ARCH-P0-4: required/optional module health policy.

Exit criteria:

1. North America 2026-08-02 is frozen as a V1 characterization fixture.
2. V1 is still the default and reproduces approved snapshot, report, Sheet
   preview and Slack preview behavior.
3. V2 artifacts are separate and external writes are disabled.
4. Unsupported snapshots cannot render/export/post.
5. Stale or materially incomplete runs cannot enter publish/post stages.
6. Human inputs survive reorder, new/removal, duplicate-row and rerun tests.

### V2.0 — Interactive action workspace

V2.0 is the smallest coherent release that delivers the stated product goal.
It is not every P1 request from the Sheet.

#### 1. Scan: prioritized weekly entry point

Scope:

- A1: action-focused TLDR/Pareto summary.
- A9: clear digest states; remove internal criteria/bracket leakage.
- A11: one approved primary headline clock, with secondary clocks visible.
- D1: target/run-rate only when the target source is approved and current.
- D14: top three market signals, with access to the complete Digest.

Acceptance criteria:

- The first viewport shows at most 5–7 decisions/signals, not another full table.
- Every item links to a CE, bucket or saved view.
- Projected impact states its formula and never implies forecast certainty.
- Headline verdict is reproducible from snapshot fields.
- A user can reach the full evidence without losing their current view.

#### 2. Explore: customization across the weekly

Scope:

- A4/A5: sorting for mover and bucket tables.
- A12: collapsible sections with 3–4-line previews and remembered state.
- D4: country filter.
- D8: geo/non-geo filter after governed classification is defined.
- D13: consistent WoW/4-week/YoY lens controls.
- Preserve All-CE saved views/watchlists/groups/highlight rules.

Acceptance criteria:

- Filter/lens/sort state is reflected consistently in counts and visible rows.
- Personal view state cannot change another user's canonical data.
- A reset returns to the governed default market view.
- Saved views are versioned against a view schema so removed fields fail clearly.
- URL or local state can restore the view without altering action records.
- Headout/global and per-market reports expose the same supported dimensions.

#### 3. Diagnose: fewer, better, explainable cohorts

Scope:

- C1/B5: reduce noise through approved materiality/coverage rules.
- C3: formalize Losing Money ownership of duplicate down-fluctuation findings.
- C4: expose an approved Scale-Up signal.
- C6: complete the agreed all-launch New CE definition.
- C7: recalibrate fluctuation volume using backtests.
- C9: decide monitored versus actionable seasonality persistence.
- C11: known-and-managing state without erasing evidence.
- E1/E2: concise paid-drop and serious-CVR-dip diagnosis.

Acceptance criteria:

- Every surfaced CE includes qualification, materiality, dominant evidence,
  recommendation and owner route.
- Cohort reduction is measured by dollar/decision coverage, not row count alone.
- Boundary tests cover every threshold and overlap rule.
- V1/V2 historical comparison reports additions, removals and changed reasons.
- “Known & managing” demotes or suppresses only in the user's operational view;
  it stays present in audit/history and next-week evaluation.

#### 4. Review: weekly evidence and discussion

Scope:

- append-only BGM notes and replies grouped by market/report week;
- governed person mentions with explicit notification preview;
- lite-audit objects posted to the relevant Slack thread;
- one weekly review hub plus authoritative per-CE alert threads;
- Granola transcript suggestions for comments, decisions, actions and follow-ups;
- an explicit uncovered queue for CEs not discussed in the meeting.

Acceptance criteria:

- Review consumes a pinned, already-built weekly artifact and cannot change its
  metrics, cohorts or publication result.
- Saving a note does not notify; an explicit share action previews and resolves
  every Slack mention before posting.
- A CE/week reuses its registered alert thread instead of creating parallel
  discussions.
- Multiple authors and replies append to history; edits never silently erase a
  prior event.
- Meeting-derived content is labeled, provenance-linked and human-approved
  before it becomes a comment, action or Slack write.
- Missing or low-confidence transcript/CE matches remain visibly unresolved.

#### 5. Act: governed multi-owner action capture

Scope:

- A10: correct contributor labels and multi-owner attribution.
- B13: stable BGM/owner identity for Slack attribution.
- C2: operational/non-Perf actions and already-actioned/self-recovering states.
- E5: Weekly Audit selection and owner routing.
- E6: reliable same/prior-week visibility.
- E9: store-backed Perf layer, if Apps Script migration is approved.

Acceptance criteria:

- Action record key is market + CE + week + bucket/lane.
- GM/Growth/BDM/Perf ownership is explicit; one actor cannot overwrite another
  role's fields.
- Status, rationale, owner and update time are visible in the report history.
- Sheet reruns and report rerenders preserve every human field.
- Slack messages link back to the same action record/CE context.
- Action vocabulary is small, versioned and mapped to reporting semantics.

#### 6. Close loop: weekly outcome and operational reliability

Scope:

- F3: explain 4-week-versus-WoW mover disagreements in alerts.
- F8: merge quantitative RCA with reviewed WBR context.
- F11: Central Live Entertainment coverage.
- F12: durable report/action archive after sink contract approval.
- F14: productized post-call/mid-week nudge.
- H5: single validated market/channel/URL registry.

Acceptance criteria:

- Every alert is sourced from the same deployed contract as the report.
- Re-post/update is idempotent and ledger-backed.
- Follow-up identifies actioned, pending, known/managing and recovered CEs.
- Missing context is explicit; generated RCA is distinguishable from reviewed
  human context.
- Market and channel routing pass preflight before any post.

## V2.1 — additive vertical slices

These are valuable after V2.0 contracts and interaction patterns stabilize.

| Slice | Feedback IDs | Why after V2.0 |
|---|---|---|
| Language diagnosis | A7, E1 | needs reliable language attribution and a drawer interaction pattern |
| Advanced lead-time/PP | D5, D6 | visibility exists; action qualification needs supply ownership |
| New CE operations | D9, D10, D15, G11 | depends on authoritative launch/MMP input automation |
| Margin/sanity overlays | C8, E3, E4, G2 | should share one overlay/routing framework |
| Opportunity flags wave 1 | G3, G4, G5 | requires shared identity, owner and evidence contract |
| Opportunity flags wave 2 | G6, G7, G8, G9, G10 | independent data sources and validation burden |
| Thread attention | F15 | depends on stable owner/tag identity and Slack ingestion policy |

## Later / separate product decisions

These should not be smuggled into V2.0 because they change cadence or product
boundary more than the weekly workspace.

- D2: OKR dashboard beyond the target/run-rate summary.
- D3: monthly WBR/month selector.
- D11: full Band Explorer product.
- D12: multi-dashboard Option A shell.
- E12: general ad hoc task tracker.
- G1: AI-ingested weather/geopolitical context.
- H7/H8: operational programs and portfolio targets.

## Explicit V2.0 non-goals

- No user-authored metric formulas.
- No replacement for Omni or the CE dashboard.
- No general-purpose task manager.
- No automatic external-context claim without human review/provenance.
- No migration of every parked opportunity flag.
- No silent Sheet/Slack/deployment action from build commands.
- No removal of V1 before shadow and one-market pilot gates pass.

## Decisions needed from product owners

| Decision | Options | Recommended starting point |
|---|---|---|
| Primary headline clock | WoW / 4-week / structural-vs-LY | 4-week movement as primary; raw WoW and structural context secondary |
| Rate delta display | percent / percentage points | use pp for rate-point movement; standardize labels/tooltips, not the math |
| Week boundary | Sun–Sat / Monday-start | retain Sun–Sat for matured Monday delivery; label cross-tool differences |
| Losing Money materiality | fixed spend / impact / adaptive coverage | dollar-impact gate plus explicit full-coverage view; avoid market-specific mystery thresholds |
| Fluctuation volume | 10 / 40–50 / adaptive | backtest candidates; approve by precision and dollar coverage |
| Seasonality action | weekly / persistent opt-in | monitor weekly, promote to action after persistence/owner confirmation |
| Known & managing | remove / suppress / demote | demote in working view, never remove from audit/history |
| Scale-Up | hidden / report / alert | report first; alert only after one shadow cycle |
| Perf storage | Sheet only / durable store | durable CE-keyed store with Sheet as input/view |
| Slack density | all tables / summary + links | short summary plus separate on-demand/priority threads |
| Review thread authority | note-created thread / alert CE thread | reuse the alert CE thread; create only when no binding exists |
| Meeting automation | automatic writes / reviewed suggestions | transcript-derived suggestions first; human approval before records or notifications |

## Worktree program

The canonical checkout remains the integration and only external-write
environment. Worktrees are code-only and no-write.

### Wave 0 — sequential foundation

1. `codex/weekly-baseline-contracts`
   - R0 contracts, fixtures, provenance, health and V1/V2 artifact separation.
2. `codex/weekly-current-correctness`
   - current ROI/CVR/comment/routing/freshness corrections and regression cases.

These merge before V2 worktrees branch from the updated integration point.

### Wave 1 — three parallel worktrees maximum

| Worktree | Owns | Avoids |
|---|---|---|
| `codex/v2-routing` | V2 measurement/routing, bucket cohorts, explanation fields | report HTML and external action writes |
| `codex/v2-workflow-contract` | Market Glance/shared workflow references, action adapters, audit/close-loop previews | bucket thresholds and duplicate workflow stores |
| `codex/v2-report-ia` | Scan/Explore UI, sorting, collapse, filters, lens state | producer metric calculations |

Merge order:

1. V2 routing contract and fixtures.
2. V2 workflow interoperability contract/adapters.
3. V2 report consumer.

Branches may develop in parallel, but consumer commits rebase after the producer
contract lands. The integration checkout runs the full no-write verification
after every merge.

### Wave 2 — integration and vertical features

- `codex/v2-market-glance-contract` for a read-only canonical weekly artifact,
  identity and deep-link integration after the external API is validated.
- Review, lite audits, commitments and Slack owner mapping stay in Market Glance
  unless joint discovery proves a missing capability.
- Granola integration attaches provenance-linked suggestions to the shared
  Review/commitment contract; it starts in suggestion-only shadow mode.
- `codex/v2-diagnosis` for E1/E2 and shared sanity overlay.
- `codex/v2-close-loop` for F3/F8/F11/F14.
- one opportunity-flag worktree at a time after its input quality is proven.

## Release gates

### Historical gate

- North America, Italy and one small/long-tail market across at least two weeks.
- membership/reason/dollar-coverage diff for every V2 bucket.
- global versus sum-of-market parity for shared measures.

### Shadow gate

- current week V1 production run unchanged.
- V2 report, Sheet preview and Slack preview generated separately.
- stakeholder review records accepted/rejected cohort differences.

### Pilot gate

- one market, one full Monday-to-follow-up cycle.
- Sheet backup and CID read-back before/after sync.
- Slack test-channel verification before production channel.
- rollback uses retained V1 artifacts and configuration.

### Expansion gate

- no unexplained metric mismatch.
- no lost/misattributed action/comment.
- degraded-module status visible.
- operator runbook updated.
- explicit sign-off to change the default engine.

## Success measures

V2 should be evaluated on decision quality and workflow completion, not feature
count:

- median surfaced CEs reviewed per market;
- share of surfaced dollar impact covered by a recorded decision;
- time from report open to first action;
- percentage of repeated flags with visible prior action/outcome;
- false-positive/no-action rate by bucket;
- percentage of users returning to a saved/custom view;
- report-to-Sheet-to-Slack identity mismatches (target: zero);
- stale/incomplete weekly publishes (target: zero).
