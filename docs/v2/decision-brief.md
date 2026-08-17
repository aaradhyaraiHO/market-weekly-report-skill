# Weekly Report V2 — Decision Brief

Status: recommended defaults for product sign-off, 2026-08-14.

This brief converts the unresolved choices in `product-roadmap.md` into
decision-ready proposals. “Recommended” means the safest coherent starting
point based on the deployed weekly, current engine and 99-item feedback intake;
it is not a claim that stakeholder sign-off already exists.

## Decision protocol

For each decision, record:

- selected option;
- approver and date;
- rationale;
- fixture/backtest evidence;
- affected backlog IDs;
- whether the decision may change during shadow mode or is contract-locking.

Thresholds may remain tunable through V2 shadow. Metric definitions, week
identity, action identity and customization ownership are contract decisions and
must be locked before dependent worktrees merge.

## D1 — What is the primary headline clock?

Feedback: A3, A11, D13, F3.

Options:

1. raw WoW;
2. W0 versus trailing four-week average;
3. structural movement versus last year's seasonal ramp;
4. no primary clock—show all equally.

**Recommendation:** use **W0 versus trailing four-week average as the primary
movement**, then show raw WoW and structural-versus-LY as secondary context.

Why:

- It is less vulnerable to a single noisy prior week.
- The current mover engine already calculates the four-week lens.
- It directly addresses feedback that the headline can overreact to one week.
- Raw WoW remains important for reversals and should never be hidden.
- Structural-versus-LY is valuable context but missing/unstable LY history should
  not control the primary verdict.

Product rule:

- primary verdict: 4-week direction/materiality;
- acute override: a material WoW reversal is called out separately;
- seasonal context: explains agreement/disagreement, never silently changes the
  measured current-period movement.

Locks: V2 headline contract and F3 alert wording. Blocks `v2-report-ia`.
Reversal cost: medium.

## D2 — How should rate changes be displayed?

Feedback: A2, B4, B12.

Options:

1. force every delta to percent change;
2. use percentage points for rates and percent change for quantities;
3. let each table choose.

**Recommendation:** use **percentage points for rate-point movement** and
**percent change for quantities**, with explicit labels.

Examples:

- CVR 4.0% → 3.0% = `−1.0pp`, not `−25%`, in the primary read.
- Revenue $100K → $75K = `−25%`.
- A tooltip may additionally expose the relative CVR change when diagnostically
  useful, but it must not replace the pp read.

Why: forcing rates into relative percentages magnifies low-base movements and
does not make metrics more comparable; standardizing notation solves the actual
legibility problem.

Locks: presentation/provenance contract. Blocks `v2-report-ia` and diagnosis
copy. Reversal cost: low if centralized formatting is built first.

## D3 — What is the weekly time boundary?

Feedback: B2, F1.

Options:

1. Sun–Sat report week;
2. Mon–Sun report week;
3. use whichever boundary each source/dashboard uses.

**Recommendation:** retain **Sun–Sat** for the Monday weekly, and make the exact
dates visible on every output and link.

Why:

- The engine moved to Sun–Sat to obtain maturation time before Monday delivery.
- A third mixed-boundary option is unacceptable.
- Switching back to Mon–Sun trades cross-tool familiarity for less mature paid
  attribution and a later reliable delivery.

Required mitigation:

- label the date range, not just “this week”;
- ensure Omni deep-links land on the same window;
- explain any CE DB/dashboard boundary difference;
- do not join week-keyed human action data without normalizing the boundary.

Locks: snapshot identity, store/Sheet keys, comparisons and fixtures. Blocks all
V2 worktrees. Reversal cost: very high.

## D4 — How should Losing Money balance coverage and noise?

Feedback: B5, C1.

Options:

1. fixed spend floor ($1K/4wk today; requested $100 alternative);
2. top-N rows;
3. CM2 dollar-impact threshold;
4. adaptive market coverage;
5. two-level action and audit views.

**Recommendation:** use **two levels**:

- **Action view:** material CEs ranked by adverse CM2 dollar impact, with a
  market coverage statement;
- **Audit view:** complete ungated qualifying set, searchable/exportable.

Keep the current $1K/4wk rule only as a V1 compatibility rule during shadow.
Backtest V2 dollar-impact/coverage options before choosing a threshold. Do not
lower globally to $100 without evidence; that likely increases noise while
solving only one market's coverage symptom.

Required evidence per candidate rule:

- CE count;
- adverse CM2 dollars covered;
- spend covered;
- no-action/false-positive rate;
- market-size sensitivity;
- lost C1/full-waste cases.

Locks: V2 bucket materiality contract after shadow. Blocks `v2-routing` final
cohort selection. Reversal cost: medium; thresholds should remain configuration.

## D5 — What volume floor should Fluctuations use?

Feedback: C7.

Options:

1. current minimum around 10 weekly orders plus W0 spend floor;
2. 40–50 orders/week;
3. statistical/adaptive floor by signal denominator;
4. no volume floor, confidence label only.

**Recommendation:** backtest **10, 25, 40 and 50** plus an adaptive confidence
rule, then choose based on precision and dollar coverage. The provisional V2
default should be **40 orders/week** only if the backtest supports the existing
design note.

Important: CM1/conversion and RPC do not have the same denominator. A single
order threshold may not be the best long-term rule. V2 should emit raw volume
and confidence so the threshold is auditable.

Locks: tunable V2 threshold, not snapshot identity. Blocks `v2-routing` release
gate but not its contract work. Reversal cost: low.

## D6 — When does seasonality become an action?

Feedback: C5, C9, C12.

Options:

1. every qualifying weekly swing creates an action recommendation;
2. only after roughly four consecutive weeks;
3. weekly monitor, promote after persistence or reviewed context;
4. human-only opt-in.

**Recommendation:** **monitor weekly; promote to action after persistence or
reviewed context**.

Suggested states:

- `new_signal` — first qualifying movement;
- `sustained` — repeated for two weeks;
- `confirmed_seasonal` — owner/review context confirms duration and geo scope;
- `actioned` — a temporary bid/budget change is recorded;
- `expired/revert` — the seasonal window ended.

The current engine already computes a sustained label, which should be reused.
Four weeks should be evaluated as a product threshold, not embedded without a
backtest; waiting four full weeks could make early warning useless.

Locks: action-state vocabulary and routing. Blocks `v2-routing` and
`v2-workflow-contract`. Reversal cost: medium.

## D7 — What should “known & managing” do?

Feedback: C11, C2.

Options:

1. remove the CE from future reports;
2. suppress it globally;
3. demote it in working views;
4. show it unchanged with a chip.

**Recommendation:** **demote in the default action view**, keep it in counts,
audit/history and next-week evaluation.

Rules:

- status requires owner, rationale and review/revisit date;
- it expires automatically unless renewed or closed;
- a materially worse movement re-promotes the CE;
- custom views may include/exclude it;
- Slack should not repeatedly ping it unless it worsens, reaches review date or
  lacks closure.

This preserves the audit trail and prevents “known” from becoming a permanent
blind spot.

Locks: action state and notification policy. Blocks `v2-workflow-contract`, `v2-routing`
and close-loop work. Reversal cost: medium.

## D8 — Where should Scale-Up appear first?

Feedback: C4.

Options:

1. report and Slack immediately;
2. report only during initial release;
3. hidden engine only;
4. separate dashboard.

**Recommendation:** **report first**, shadow for at least one cycle, then decide
whether only the highest-confidence cases enter Slack.

Why: the engine already computes Scale-Up but the report hides it. Exposing it
in the interactive workspace provides feedback without increasing notification
density prematurely.

Locks: surface decision, not core contract. Blocks `v2-report-ia` Scale-Up
section. Reversal cost: low.

## D9 — Where should Perf decisions live?

Feedback: E8, E9.

Options:

1. Sheet only with CID-preserving rewrites;
2. Apps Script/store as canonical, Sheet as input/view;
3. report-only entry;
4. independent Sheet and report values.

**Recommendation:** **durable CE-keyed store as canonical; Sheet as Perf's
input/view**.

Key:

`market + ce_id + week_start + bucket/lane + actor_role`

The shipped CID-keyed Sheet fix remains the transition safeguard. Store-backed
fields must be separate from GM/Growth fields so roles cannot overwrite each
other. Current-week Sheet input may win on sync, but every write must be read
back by CID.

Locks: action identity and external store schema. Blocks `v2-workflow-contract` durable
implementation. Reversal cost: high after migration.

## D10 — What belongs in Slack versus the report?

Feedback: F5, F6, F7, F8, D14.

Options:

1. post all report tables;
2. short summary plus priority/on-demand threads;
3. link-only notification;
4. role-specific Slack payloads.

**Recommendation:** **short summary plus priority threads and report links**.

Default:

- market verdict and top three signals;
- action-required/past-due items;
- separate priority threads by type;
- report link preserving the relevant filtered view;
- no routine RPC-up thread until shadow proves it drives action.

Slack is the attention and discussion surface; the report is the complete
interactive evidence surface. Avoid copying full audit tables into both.

Locks: notification contract. Blocks close-loop/alert consumer work. Reversal
cost: low if payload generation is contract-driven.

## D11 — Are saved/custom views personal or shared?

Feedback: V2 product goal plus existing All-CE behavior.

Options:

1. personal/browser-local only;
2. shared market views only;
3. both personal views and governed shared presets;
4. URL-only transient views.

**Recommendation:** support **both personal views and governed shared presets**.

- Personal: filters, sort, collapsed state, visible metrics, watchlist.
- Shared preset: named market/team view with owner, description and version.
- URL state: shareable transient view, excluding private notes/actions.
- Canonical default: product-owned and versioned.

View state must never be stored in action records. Shared presets should not
include private watchlists unless explicitly published.

Locks: V2 view-state schema and storage. Blocks `v2-report-ia` saved-view
implementation. Reversal cost: high if storage is chosen late.

## D12 — Should customization be role-based?

Feedback: A10, B13 and cross-role requests from GM/BGM/BDM/Perf.

Options:

1. one identical default for everyone;
2. hard-coded role-specific products;
3. common product with optional role presets;
4. fully user-built dashboards.

**Recommendation:** **one common product with optional role presets**.

Examples:

- GM/BGM: market movement, ownership and closure.
- Perf: Losing Money, fluctuations, tROAS/action history.
- Growth/BDM: lifecycle, countries, funnel and market context.

Presets change default view state, not metric definitions or access to the audit
trail. Users can save their own view from any preset.

Locks: product IA and preset registry. Blocks final `v2-report-ia` defaults, but
not foundation contracts. Reversal cost: medium.

## D13 — Which Slack thread is authoritative for Review?

Feedback: E5, E6, F8, F15 and the WBR-transcript workflow.

Options:

1. create a new thread whenever a report note is posted;
2. reuse the existing CE alert thread when present;
3. keep report notes and alerts in separate threads;
4. post all review discussion only in one weekly market thread.

**Recommendation:** use a **weekly review hub plus the existing per-CE alert
thread**. The hub carries market-level completion and uncovered items; CE notes,
RCA, actions and follow-ups reuse the registered CE alert thread. Create a CE
thread only when no authoritative binding exists.

Why: Slack cannot nest threads. Reusing the CE alert thread keeps quantitative
evidence, BGM notes, meeting context and follow-up in one discussion without
turning the weekly hub into an unreadable stream.

Locks: shared thread registry and Slack reconciliation contract. Blocks the
Market Glance canonical-evidence integration and reviewed meeting output.
Reversal cost: high once live
threads accumulate.

## D14 — How may meeting-derived content become a record?

Feedback: E11, F8 and the WBR-transcript workflow.

Options:

1. automatically write extracted comments/actions and notify owners;
2. create suggestions that a permitted reviewer accepts, edits or rejects;
3. show transcript search only and never create structured suggestions;
4. ingest only Granola summaries rather than transcripts.

**Recommendation:** use the **full eligible transcript to create
provenance-linked suggestions**, then require human approval before a suggestion
becomes a Review event, action assignment or Slack notification.

This preserves the “no manual re-entry” benefit—the reviewer approves or edits
extracted records instead of retyping them—without silently attributing an AI
interpretation to a person. Low-confidence CE/person matches remain in an
unresolved queue.

Locks: Granola access scope, transcript retention, provenance, approval and
identity contracts. Blocks `v2-granola` beyond shadow mode. Reversal cost: high
if unreviewed automation writes history first.

## Recommended sign-off order

1. **D3 week boundary** — identity foundation.
2. **D9 action/store identity** — human-data foundation.
3. **D11 view ownership/storage** — customization foundation.
4. **D1 headline clock** and **D2 rate formatting** — report contract.
5. **D4 materiality**, **D5 fluctuation volume**, **D6 seasonality** — routing.
6. **D7 known/managing** — actions and notifications.
7. **D8 Scale-Up**, **D10 Slack density**, **D12 role presets** — rollout/surface.
8. **D13 thread authority** and **D14 meeting approval** — Review integrations.

## Worktree blocking matrix

| Worktree | Must be signed before merge | May remain tunable during shadow |
|---|---|---|
| `weekly-baseline-contracts` | D3 | none |
| `weekly-current-correctness` | D2, D3 | none |
| `v2-routing` | D3, D4 contract shape, D6 state shape | D4 threshold, D5 threshold |
| `v2-workflow-contract` | D3, D7, D9 | reminder timing |
| `v2-report-ia` | D1, D2, D8, D11, D12 | default sort/collapse details |
| `v2-close-loop` | D7, D10 | top-N and notification thresholds |
| `v2-market-glance-contract` | D3, D9, D10, D13 | review-status labels, message density and reminder timing |
| `v2-granola` | D9, D13, D14 | extraction prompt and match threshold during shadow |

## Decision record template

```text
Decision: D# — title
Selected option:
Approver:
Date:
Evidence reviewed:
Rationale:
Contract fields affected:
Backlog IDs affected:
Shadow-tunable values:
Revisit trigger/date:
```
