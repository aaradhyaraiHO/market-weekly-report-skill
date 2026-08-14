# Weekly Report V2 — V1 capability parity contract

**Status:** Required acceptance contract  
**V2 checkpoint audited:** `674043d` (`codex/v2-market-headlines`)  
**V1 reference:** `scripts/weekly_report/template/report_template.html` and schema-v1 snapshots  
**Default rule:** Every observable V1 capability remains required until an explicit product decision records its replacement or retirement.

## 1. Governing rules

1. V2 may redesign information architecture, visual hierarchy and interaction details.
2. V2 must preserve data meaning, calculation boundaries, workflows, persistence and downstream contracts.
3. A visually similar component is not parity if filters, history, actions, sidecars or edge states are missing.
4. A replacement is acceptable only when it completes the same user job with equal or better evidence and no lost data.
5. A capability cannot be silently dropped because it is difficult, legacy or absent from a mockup.
6. Unknown or unavailable data fails closed and is labelled; it is never inferred from an adjacent field.
7. V1 remains the production fallback until the applicable matrix rows are verified.

### Status vocabulary

| Status | Meaning |
|---|---|
| **Verified** | Implemented in V2 and covered by automated or recorded browser evidence. |
| **Partial** | Some visible behavior exists, but the V1 user job is not complete. |
| **Missing** | Not implemented in V2. |
| **Planned replacement** | A different V2 interaction is proposed, but parity is not accepted until verified. |
| **Retired by decision** | Removed only after an explicit product decision is recorded here. |

## 2. Cross-cutting report contract

| ID | V1 capability | V2 status | Acceptance gate |
|---|---|---|---|
| C-01 | Schema-v1 snapshot remains the source of weekly metrics and bucket membership. | **Verified** | Baseline/golden suite passes; V2 does not mutate the snapshot. |
| C-02 | V1 report, Slack, Sheet, Ledger and publishing paths remain operational during migration. | **Verified** | All no-write V1 contracts pass before every V2 checkpoint. |
| C-03 | Market and week identity remain explicit throughout the report. | **Verified** | Switching week updates every V2 surface consistently. |
| C-04 | Optional sidecars fail soft without fabricating data. | **Verified** for goals and CE ownership | Missing/stale states are visible; no adjacent field is substituted. |
| C-05 | Headout/global and market reports share behavior while respecting capped global CE payloads. | **Missing** in V2 browser coverage | Dense, sparse, global and capped Headout views pass characterization and browser checks. |
| C-06 | Existing notes, actions, Slack links and history remain attributable and week-scoped. | **Missing** in V2 | Round-trip persistence and provenance tests pass before production use. |
| C-07 | Null values render as unavailable, never zero. | **Partial** | Every migrated table/drawer has null-state contract tests. |
| C-08 | Responsive and keyboard-accessible behavior remains usable. | **Partial** | Desktop/mobile, focus, Escape, sorting and horizontal-scroll checks recorded per surface. |

## 3. Overview and market headline

| ID | V1 capability | V2 status | Acceptance gate |
|---|---|---|---|
| H-01 | Market revenue, WoW, YoY and trailing context. | **Verified** | Values match the snapshot view model. |
| H-02 | Dual-clock structural/raw interpretation and disagreement state. | **Partial** | Structural net, concentration and disagreement remain visible or have an approved replacement. |
| H-03 | Monthly target/MTD/run-rate outlook without inferring missing goals. | **Verified** when sidecar exists | Current, stale and missing goal states pass tests. |
| H-04 | Twelve-week TY/LY revenue trajectory and hover values. | **Verified** | TY/LY toggles, WoW/YoY tooltip and responsive rendering pass browser checks. |
| H-05 | Top drops and gains with 4-week/WoW lens and seasonality context. | **Verified** for display/sorting | Impact, Revenue, WoW and Name sorts preserve source rows. |
| H-06 | Clicking a mover opens the relevant CE deep dive. | **Missing** | Every resolvable mover routes to the parity-complete CE drawer. |
| H-07 | Market-detail drawer: metrics, TY/LY sparklines, Shapley and provenance. | **Verified** | Drawer close/focus states and dense/sparse data pass. |
| H-08 | Market pacing evidence and goal freshness. | **Partial** | Existing V1 placeholder behavior plus approved goal-backed V2 behavior are documented and tested. |

## 4. All-CE parity matrix

No subsequent table migration is allowed to reuse the All-CE component until the relevant rows below are complete.

### 4.1 Portfolio controls and persistence

| ID | V1 capability | V2 status | Acceptance gate |
|---|---|---|---|
| A-01 | Search by CE name, ID, city, category and subcategory. | **Partial** | Add subcategory and verify case-insensitive matching and reset. |
| A-02 | Sort every static and metric column; nulls always last. | **Partial** | Full V1 metric set is sortable in both directions with null ordering tests. |
| A-03 | One-click absolute top-mover sort. | **Missing** | Restores `|Δ revenue WoW|` order and visual mover badges. |
| A-04 | Country filtering. | **Verified** as additive V2 behavior | CE membership and reset pass browser tests. |
| A-05 | Management, evolution, lifecycle and tier filters. | **Missing** | Snapshot-backed metadata filters preserve multi-select behavior. |
| A-06 | Diagnostic-bucket filters with counts. | **Missing** | Defend, Compound and Lifecycle chips match `buckets_final` membership. |
| A-07 | Headout market filter. | **Missing** | Global report filters and groups by source market. |
| A-08 | BDM and Growth region filters. | **Verified** only with approved sidecar | Filters disable honestly without the mapping and work with it. |
| A-09 | Group by category, subcategory, city, management, evolution, tier, lifecycle, diagnostic bucket, market and custom group. | **Missing** | Group membership and subtotal values match V1. |
| A-10 | Collapse/expand individual groups and all groups. | **Missing** | State survives table rerenders during the session. |
| A-11 | Saved views preserve filters, grouping, sort, watchlist-only state and highlight rule. | **Missing** | Save/apply/delete and per-market persistence tests pass. |
| A-12 | Persistent per-market watchlist and watchlist-only filter. | **Missing** | Row and drawer stars mirror one state and survive reload/week changes. |
| A-13 | Highlight-rule parser for ROI/WoW/revenue/YoY/CVR/AOV/TR/spend/CM1/clicks/orders. | **Missing** | Supported expressions match V1 behavior and invalid rules fail soft. |
| A-14 | Select CEs and create durable custom groups. | **Missing** | Selection, add/clear and restored custom membership pass. |
| A-15 | Reset returns every control and expanded state to the documented default. | **Partial** | Full-parity state reset is tested. |

### 4.2 Table evidence

| ID | V1 capability | V2 status | Acceptance gate |
|---|---|---|---|
| A-16 | Sticky CE identity plus watch, mover, group and note indicators. | **Missing** | Indicators reflect the same persisted/source state as V1. |
| A-17 | Direct Omni link per CE without opening the drawer. | **Missing** | Link preserves CE and 12-week context and stops row propagation. |
| A-18 | Twelve-week TY/LY revenue sparkline per CE. | **Missing** in table | Sparkline renders null LY safely and exposes values accessibly. |
| A-19 | Filtered-set total row pinned above CE rows. | **Missing** | Aggregations recompute from the visible set. |
| A-20 | Contribution percentage against the filtered set and full market. | **Missing** | Denominators match V1 semantics for CE/group/total rows. |
| A-21 | Overall metrics: Revenue, Orders, AOV, TR and CR. | **Partial** | All columns preserve values, formats and tooltips. |
| A-22 | Paid metrics: Clicks, CVR, CPC, RPC, Spend, CM1, CM2 and ROI. | **Partial** | All columns preserve values, formats, paid boundary and tooltips. |
| A-23 | Collapsed metric cells show W0 plus WoW change. | **Partial** | Every overall/paid metric follows the same compact contract. |
| A-24 | Per-metric expansion shows W0, W-1, absolute change, WoW and YoY. | **Missing** | Individual and expand-all toggles pass numeric and layout tests. |
| A-25 | Group subtotal rows recompute ratios from sums rather than averaging CE ratios. | **Missing** | Aggregation tests cover every derived metric. |
| A-26 | Contribution strip shows group revenue share, WoW movement and stable materiality index. | **Missing** | Values and the 3% materiality floor match V1. |
| A-27 | Capped Headout explanation shows cap, shown count, total count and inclusion rules. | **Missing** | Message matches `meta.ce_cap` and never implies full coverage. |
| A-28 | Result line reports shown/total CEs, filtered revenue, mover sort, highlighted rows, watched count and custom-group count. | **Partial** | All applicable counts reflect current state. |
| A-29 | Link to the market’s monthly deep-dive report. | **Missing** | Existing routing behavior is preserved or explicitly replaced. |

### 4.3 CE drawer parity

| ID | V1 capability | V2 status | Acceptance gate |
|---|---|---|---|
| D-01 | CE identity, metadata chips, watchlist mirror and Omni link. | **Partial** | Add watchlist and Omni; metadata remains source-backed. |
| D-02 | Overall/Paid key metrics with W0, W-1, delta and 12-week TY/LY hover. | **Partial** | Full metric tabs/table and hover evidence match V1. |
| D-03 | CE-level WoW Shapley decomposition. | **Missing** | Factors and reconstruction state match `ce.shapley_wow`. |
| D-04 | Channel-mix table. | **Missing** | Revenue, W-1, WoW, YoY and share are preserved. |
| D-05 | Funnel table from LP users through CVR. | **Missing** | W0/W-1/WoW/YoY units remain correct. |
| D-06 | TGID table with Size, Value, Funnel and Booking-window bands. | **Missing** | Band collapse and enriched metric fields remain available. |
| D-07 | Lead-time bands. | **Missing** | Bookings, W-1, share, revenue and AOV are preserved. |
| D-08 | Customer-country mix. | **Partial** | Current display adds orders, WoW and AOV parity. |
| D-09 | CE-scoped Slack context with source link, channel and date. | **Missing** | Every imported summary retains its underlying source. |
| D-10 | Week-scoped notes with shared-sheet sync, local fallback and Slack post. | **Missing** | Save/load/post, attribution and failure states pass. |
| D-11 | Prior note history. | **Missing** | History is ordered, attributable and collapsible. |
| D-12 | Multi-week Perf action log. | **Missing** | Decision tag, reasoning and one-row-per-week behavior match frozen consumers. |
| D-13 | Drawer opens from All-CE rows, movers, bucket rows and other CE references. | **Partial** | All entry points route to the same parity-complete drawer. |
| D-14 | Drawer keyboard, focus and outside-click behavior. | **Verified** for current V2 drawer | Reverify after full drawer content lands. |

## 5. Remaining V1 report surfaces

| ID | V1 capability | V2 status | Acceptance gate |
|---|---|---|---|
| B-01 | Losing Money membership, ordering, four-week evidence, criteria and status. | **Missing** | Rows and order match current `buckets_final` behavior. |
| B-02 | Losing Money action selection, required commentary, prior action and persistence. | **Missing** | Sheet/local behavior and warnings match V1. |
| B-03 | RPC/CM1 fluctuation down/up membership, driver, four-week evidence and ordering. | **Missing** | Directional buckets remain distinct and match V1. |
| B-04 | Fluctuation actions, required commentary and persistence. | **Missing** | Same action contract as V1. |
| B-05 | Scale-Up, New CE, Iteration/Untapped and lifecycle tables. | **Missing** | Membership and market-specific empty states match V1. |
| B-06 | Seasonality and lever sections. | **Missing** | Existing evidence, notes and links remain reachable. |
| B-07 | Marketing budgets/TR incentives, no-bid campaigns and pre-purchase. | **Missing** | Current joins, metrics and links remain intact. |
| R-01 | Market review narrative with week history and shared persistence. | **Missing** | Existing behavior remains until Review Mode replaces it with verified migration. |
| R-02 | Slack digest and CE/market context rendering. | **Missing** | Source attribution and scoping remain intact. |
| R-03 | Notes export/import including views, groups, watchlist and rules. | **Missing** | Round-trip is preserved or replaced with an approved migration/export path. |

## 6. Required delivery sequence

1. **All-CE analytical parity:** A-01–A-10 and A-16–A-28.
2. **All-CE personalization and links:** A-11–A-15 and A-17/A-29.
3. **CE drawer parity:** D-01–D-14.
4. **Bucket surfaces:** B-01–B-07, reusing the verified table/drawer components.
5. **Review Mode integration:** R-01–R-03 migrate only after its replacement persistence and history contracts pass.
6. **Headout/global verification:** C-05 plus the Headout-specific All-CE rows.

No phase is complete because its page looks finished. Completion requires the applicable matrix rows to be **Verified**.

## 7. Worktree coordination

- `codex/v2-market-headlines` owns the V2 report shell, overview, All-CE, bucket and drawer migration.
- The current Review worktree at `/Users/aaradhyarai/.codex/worktrees/25ff/market-weekly-report-skill` is based on `main` (`06e67e2`) and currently contains two uncommitted scope documents only.
- The Review worktree may continue domain/schema planning and isolated tests, but should avoid editing `report_v2_template.html` until it is rebased or recreated from the V2 checkpoint.
- Integration must bring Review Mode onto a checkpoint that already contains the verified dashboard shell; two branches must not independently redefine navigation, drawer primitives or shared persistence contracts.
- No worktree is merged, rebased, deleted or rewritten without an explicit integration decision.

## 8. Change review checklist

For every V2 pull/merge candidate:

- [ ] Applicable matrix rows are named in the change description.
- [ ] V1 baseline/golden suite passes.
- [ ] V2 unit/contract tests cover source mapping and null states.
- [ ] Browser evidence covers primary interaction, empty state, keyboard and responsive behavior.
- [ ] No production write, Slack post, Sheet write or deployment occurred during verification.
- [ ] Any retirement/replacement decision is recorded in this file with approver and date.
