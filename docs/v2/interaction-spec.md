# Weekly Report V2 — Interaction and Customization Specification

Status: proposed V2.0 interaction contract, 2026-08-14.

This specification turns “interactive/customisable” into implementable behavior.
It is grounded in the current All-CE implementation in
`report_template.html`, which already supports sorting, filtering, grouping,
saved views, watchlists, custom groups, highlight rules, expandable metrics and
CE drawers.

## Current implementation audit

### What works today

All-CE maintains an in-memory state with:

```text
sortKey, dir, group, search, filters, watchOnly, rule,
selMode, collapsed, filtersOpen, expand
```

Browser-local persistence is scoped by market slug:

```text
wr_views::{slug}
wr_groups::{slug}
wr_watch::{slug}
wr_rule::{slug}
```

Views currently save:

```text
search, group, sortKey, dir, watchOnly, rule, filters
```

Notes/actions are separate from view state and use shared Sheet/Apps Script
sync with localStorage as cache. That separation is directionally correct.

### Current limitations

1. Saved views have no schema version or stable ID.
2. An applied view is tracked by array index; deleting/reordering changes its
   identity.
3. Views do not save expanded metrics, collapsed sections/groups, visible
   columns, time lens or role preset.
4. Views are browser-local; another device or teammate cannot use them except
   through manual JSON export/import.
5. There is no distinction between a private view and a governed market preset.
6. There is no URL/deep-link representation for a filtered view.
7. Unknown or renamed filter fields fail by becoming ineffective, not by
   showing a migration warning.
8. Custom groups/watchlists have no owner or stable shared identity.
9. Group-by “diagnostic bucket” uses a raw fluctuation index while filter chips
   use `buckets_final`, so customization can describe a different cohort from
   the displayed final tables.
10. Search/filter dimensions assume CE metadata fields; country and geo/non-geo
    need governed fields before they can be added safely.
11. The Headout view is capped. A saved filter cannot imply it searched the
    omitted long tail.
12. Personal view changes and canonical market-level conclusions are not
    explicitly distinguished in the UI.

## Design principles

1. **One truth, many views.** Customization changes presentation and scope, not
   metric definitions, bucket membership or historical action records.
2. **Personal state is private by default.** Sharing is an explicit action.
3. **Shared presets are governed.** They have an owner, description, version and
   review lifecycle.
4. **Canonical conclusions stay visible.** Filtering the workspace must not
   silently rewrite the market headline.
5. **Every view is restorable.** Saved and URL views are versioned and validated.
6. **Actions are never view state.** Hiding a CE does not remove or mutate its
   action, owner or follow-up obligation.
7. **Missing coverage is explicit.** Capped/global views show the searchable
   population and omissions.
8. **Interaction is accessible.** Controls work with keyboard, labels and visible
   focus; color is never the only signal.

## State layers

V2 has four separate state layers.

| Layer | Examples | Persistence | Sharing |
|---|---|---|---|
| Canonical data | metrics, buckets, provenance, module health | snapshot/artifact | same for all users |
| Shared workflow | actions, notes, owners, review dates, Slack links | durable action store | role/market governed |
| View definition | filters, sort, lenses, columns, section state | personal store/local cache or shared preset registry | explicit |
| Ephemeral UI | selected rows, open drawer, hover, unsaved search text | memory/URL where useful | not shared by default |

No field may exist in more than one layer without an explicit source-of-truth
and synchronization rule.

## View definition contract

Proposed logical shape:

```json
{
  "schema_version": 1,
  "id": "view_...",
  "name": "My at-risk Hero CEs",
  "scope": "personal",
  "owner": {"id": "...", "display_name": "...", "role": "gm"},
  "market_scope": ["north_america"],
  "role_preset": "gm",
  "filters": [
    {"field": "tier", "operator": "in", "values": ["Hero"]},
    {"field": "bucket", "operator": "in", "values": ["losing_money"]}
  ],
  "search": "",
  "sort": [{"field": "cm2_impact", "direction": "asc"}],
  "group": {"field": "country", "collapsed": []},
  "lenses": {
    "primary_period": "vs_4wk",
    "comparison_periods": ["wow", "yoy"],
    "expanded_metrics": ["revenue", "roi", "cm2"]
  },
  "columns": {
    "visible": ["ce", "revenue", "cm2", "roi", "driver", "action"],
    "order": ["ce", "revenue", "cm2", "roi", "driver", "action"]
  },
  "sections": {
    "headlines": "preview",
    "digest": "collapsed",
    "all_ce": "expanded",
    "buckets": "expanded"
  },
  "watchlist_only": false,
  "highlight_rules": [
    {"field": "roi", "operator": "lt", "value": 120}
  ],
  "created_at": "...",
  "updated_at": "..."
}
```

### Required invariants

- `id` is stable and never derived from array position.
- `schema_version` is validated before application.
- fields/operators come from a registry, not arbitrary JavaScript expressions.
- unknown fields/operators produce a visible “view needs updating” state.
- a view may reference canonical field IDs only, never visible column labels.
- views do not contain notes, comments, action status or Slack thread data.
- view application is pure: it cannot write any external state.
- a personal view cannot silently become shared.

## View scopes

### Canonical default

- product-owned;
- one per report type/market class;
- versioned with the report;
- cannot be deleted by users;
- reset always returns here.

### Role preset

- product/market-operations owned;
- optional GM/BGM, Perf and Growth/BDM starting arrangements;
- changes visible sections/columns/filters, never metric definitions;
- user may copy to a personal view.

### Personal view

- private by default;
- stores filters, columns, sorting, grouping, lenses and section state;
- watchlist may be referenced by the personal view but is maintained as a
  separate personal collection;
- initially browser-local with export/import compatibility if no user store is
  available; later synced to an identity-backed view store.

### Shared market preset

- explicit publish action;
- owner, description, market scope and review date required;
- stable URL/ID;
- edits create a new version or update timestamp;
- consumers can copy but not accidentally overwrite it.

### URL view

- contains only non-sensitive presentation state;
- may include market, filter, sort, group, lens, section and CE focus;
- never includes notes/actions, private watchlist membership, author identity or
  unshared custom-group contents;
- validates against the current view schema on open.

## Customization field registry

Every filter/group/sort field must declare:

```text
id
label
type
allowed operators
source snapshot path
supported report scopes
null behavior
aggregation behavior
provenance
```

V2.0 registry candidates:

| Field | Filter | Group | Sort | Notes |
|---|---:|---:|---:|---|
| market | yes | yes | yes | global only |
| country | yes | yes | yes | governed CE/customer-country definition required |
| geo_class | yes | yes | yes | geo/non-geo classification source required |
| category/subcategory | yes | yes | yes | current metadata |
| city | yes | yes | yes | current metadata |
| management_type | yes | yes | yes | current metadata |
| evolution | yes | yes | yes | current metadata |
| lifecycle/tier | yes | yes | yes | current metadata/routing |
| bucket | yes | yes | yes | must use final routed membership only |
| action_state | yes | yes | yes | shared workflow read, never view-owned |
| owner | yes | yes | yes | shared workflow identity |
| known_managing | yes | yes | yes | time-bound action state |
| revenue/CM2/ROI/driver | range | limited | yes | explicit period/basis required |
| flag_streak | range | yes | yes | V2 routing field |

Country and geo/non-geo cannot ship as guessed frontend derivations. Their
source and cardinality must be defined in the snapshot contract.

## Interaction model by product mode

### Scan

- Canonical market TLDR remains stable regardless of personal filters.
- A secondary “current view” summary shows filtered CE count, revenue share,
  adverse impact and pending actions.
- Top-signal cards can apply a view and scroll/focus the relevant evidence.
- Cards display the active lens and qualification reason.
- No hidden filter may change the market verdict without a visible scope label.

### Explore

- Filter changes update visible rows, visible/total cohort counts and current-view
  summary immediately.
- Bucket chips show `visible / total`, for example `12 / 38`.
- Sorting is available on mover and bucket tables, not only All-CE.
- Section collapse state is remembered per view.
- Lens control selects display comparison; routing qualification remains based
  on the engine's declared period.
- Reset returns to the current preset/canonical default, not an arbitrary empty
  state.

### Diagnose

- Opening a CE drawer does not clear the current view.
- Browser back/URL can restore CE focus and the view.
- Drawer labels every metric basis and comparison period.
- “Why surfaced” uses final routed explanation fields.
- Links from Slack open the CE and relevant section/lens when possible.

### Review

- Review is a shared workflow layer, never personal view state.
- The inbox can be filtered by coverage, owner, review status, source and due
  state without altering canonical report signals.
- Notes append to a weekly timeline; saving a draft does not notify.
- Mention selection resolves governed identities and previews the exact Slack
  recipients before an explicit share action.
- Manual, meeting-derived and Slack-synced events are visually distinct and
  preserve provenance.
- CE discussion opens the authoritative alert thread when one exists; the UI
  must not create a parallel thread merely because a note was added.
- Generated meeting suggestions cannot assign, close, notify or post until a
  permitted reviewer accepts them.

### Act

- Actions remain visible even if a view hides their CE.
- View filters may include action state/owner/past-due status as read-only shared
  workflow fields.
- Bulk selection never implies bulk action; any future bulk write needs a
  separate reviewed flow and explicit confirmation.
- Changing a view cannot trigger Sheet, Slack or action-store writes.
- Owner/action controls display synchronization state independently of view-save
  state.

### Close loop

- Personal filters can focus `pending`, `past_due`, `known_managing`, `recovered`
  and `no_action` cohorts.
- Known/managing has expiry/review date and remains in audit history.
- Next-week comparison evaluates the same CE/bucket identity even if current
  membership changed.
- A closed item links to the decision and outcome evidence.

## Counts and aggregation semantics

V2 must distinguish:

- **canonical total** — entire snapshot/bucket population;
- **visible total** — current filters/view;
- **selected total** — ephemeral user selection;
- **action total** — shared workflow state.

Rules:

- ratios recompute from summed numerators/denominators, never average CE ratios;
- action/bucket counts are not recalculated from visible labels;
- capped Headout views state both shown and full population;
- no saved view may claim complete coverage of data absent from its artifact;
- group subtotals inherit metric provenance and active display lens.

## Persistence and storage rollout

### V2.0 initial implementation

- personal views/watchlists/groups: versioned local storage plus export/import;
- canonical/role/shared presets: repository-authored configuration embedded into
  the artifact;
- URL views: compact validated query/hash representation;
- actions/notes: existing durable shared workflow path, never local-only source
  of truth.

This delivers safe customization without making authentication/view storage a
hard dependency.

### Later identity-backed sync

- sync personal/shared views through an authenticated service;
- preserve stable view IDs and versions;
- implement conflict handling (copy or explicit overwrite, never silent
  last-write-wins on shared presets);
- keep local storage as offline cache only.

## Migration from current V1 customization

Current view shape:

```text
{name, st:{search, group, sortKey, dir, watchOnly, rule, filters}}
```

Migration steps:

1. Read `wr_views::{slug}` without deleting it.
2. Validate known current fields.
3. Generate stable view ID and `schema_version: 1`.
4. Map `sortKey/dir` to `sort[]`.
5. Map filter object entries to registered filter clauses.
6. Map single rule string to a typed highlight rule when parseable.
7. Add default lenses, columns and section state.
8. Save to the V2 key only after round-trip validation.
9. Mark unsupported fields and keep the original view available for recovery.
10. Migrate groups/watchlists separately; never embed action/note caches.

Recommended keys:

```text
wr_v2_views::{slug}
wr_v2_groups::{slug}
wr_v2_watch::{slug}
wr_v2_active::{slug}
```

The migration is idempotent and retains V1 keys through at least one stable live
cycle.

## Accessibility and interaction requirements

- All controls have accessible names and keyboard operation.
- Sort direction is announced in text/ARIA, not color alone.
- Filter chips expose selected state.
- Drawer focus is trapped and returns to the originating row on close.
- Collapsed sections expose expanded state.
- Saved-view errors are visible without blocking canonical reset.
- Mobile/narrow layouts keep Scan and actions usable even if wide metric tables
  require horizontal scrolling.
- Motion is restrained and respects reduced-motion preference.

## No-write interaction invariant

The following are always presentation-only and cannot cross an external write
boundary:

- sort/filter/group changes;
- lens/column/section changes;
- apply/save/delete personal view;
- open/close drawer;
- URL view creation;
- watchlist changes unless a future explicit shared-watchlist feature is added.

External writes remain explicit actions:

- save/update action or note;
- publish a shared preset;
- post/update Slack;
- write/sync Sheet;
- stage/deploy report.

## Acceptance tests

### View contract

- V1 view migrates once and round-trips without loss of supported fields.
- unknown field/operator creates a visible invalid-view warning.
- deleting one view does not change another view's identity.
- canonical reset always succeeds.

### Scope and counts

- filter changes show visible/total counts.
- canonical headline stays unchanged under personal filters.
- filtered aggregate ratios recompute from raw components.
- bucket group/filter membership matches `buckets_final` exactly.

### Persistence

- refresh restores personal view state.
- share URL restores allowed presentation state only.
- private watchlist/groups are absent from shared URL.
- V1 local keys remain intact after successful migration.

### Workflow isolation

- applying/deleting a view emits no Sheet/Slack/action-store request.
- hiding a CE leaves its action and pending-follow-up state intact.
- role preset changes columns/layout only, not metrics or membership.

### Cross-surface links

- TLDR card opens the correct filtered evidence.
- Slack link opens the intended market, CE, section and lens.
- browser back returns to the previous view without losing filters.

## Implementation ownership

- `v2-routing`: supplies governed fields, final membership and explanation data.
- `v2-workflow-contract`: supplies read-only Market Glance/shared
  action/owner/filter references and write adapters outside the weekly build.
- `v2-report-ia`: owns view schema, migration, URL state, controls and interaction.
- baseline contracts: validate that view fields exist for the declared snapshot
  version.

The report-IA worktree must not derive new business classifications merely to
make a requested filter appear.
