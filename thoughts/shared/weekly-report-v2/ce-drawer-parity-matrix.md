# Weekly Report V2 — CE drawer parity and additions matrix

Audit date: 2026-08-16

Baseline: `codex/v2-ce-drawer` at `0605e09`

V1 source: `scripts/weekly_report/template/report_template.html`

Feedback source: `Market Weekly Report — Product Roadmap (Consolidated Feedback & Requests)`, `Roadmap` tab (`sheetId=529122362`), read only.

This is the gate for CE-drawer implementation. A V2 item is not parity merely because a visually similar component exists: its source, calculation, link target, attribution text, write semantics, and entry/exit behavior must also match.

## V1 parity inventory

Disposition vocabulary: **Present** = represented completely in the sanitized mock; **Mock-only** = visible but production wiring is absent; **Missing parity** = V1 behavior still needs representation or integration; **Intentionally excluded** = explicitly removed from this drawer; **Delegated** = owned by the separate review-mode worktree.

| Surface / capability | Disposition | V1 source and observable contract | Current V2 treatment and remaining gate |
| --- | --- | --- | --- |
| Entry points | Missing parity | Delegated `[data-ce]` clicks from All-CE, movers, buckets, and follow-ups; aggregate/missing CEs fail closed. | Standalone mock starts open. Later integration must wire every CE-bearing surface and prevent nested controls from bubbling. |
| Drawer lifecycle | Mock-only | Right-side modal plus scrim; close button, scrim click, and Escape close it. | Dialog semantics, sticky header, and close control are visible. Focus trap/return, Escape, scrim close, scroll lock, and actual teardown remain integration work. No section sidebar. |
| CE identity and Omni | Mock-only | Market, CE ID/name, Omni deep link, category, subcategory, city, management type, evolution, new/existing, and tier. | All identity fields are represented with sanitized values; Omni uses an inert fixture URL. Omit null metadata during integration. |
| Watchlist | Mock-only | Shared per-market `wr_watch::<market>` set; toggle repaints the All-CE table. | Explicit watchlist control toggles in memory only. Reuse the shared key/shape and repaint contract later. |
| Revenue headline | Present | W0 predicted revenue, WoW %, absolute change, and weekday-aligned `−364d` YoY. | Approved first fold shows predicted W0, W-1 amount/change, LY base, alignment, and a large TY/LY revenue trajectory. |
| Key metrics | Present | Overall and Paid inventories; W0, W-1, delta %, and 12-week TY/LY per metric. | Both tabs and every V1 metric are present. Production must project `ce.weekly`/`weekly_ly` without presentation-layer recalculation. |
| Metric hover evidence | Present | Pointer reveals week, TY, LY, and YoY when LY is non-zero. | Hover and keyboard focus expose all four values; expandable rows expose every week. Shared scale and TY/LY styling are explicit. |
| Overall-CVR definition | Missing parity | Current builder injects `overall_cvr_pct = orders ÷ all-traffic clicks`; product wording has also referred to LP users. | Mock now displays the snapshot field and flags B4/B12 instead of recomputing. Canonical source definition must be resolved upstream. |
| WoW Shapley | Present | Optional traffic, CVR, AOV, completion, and take-rate USD contributions plus net. | All factors, signs, attribution, and reconciliation are represented. Conditional omission remains covered by Graceful absence. |
| Channel mix | Present | `ce.channels`: actual W0/W-1 revenue, WoW, YoY, and within-CE share. | Complete V1 table at channel grain. Share adds compact WoW/YoY pp context; the proposed 12-week revenue line remains a historical-sidecar extension. Orders and AOV are not added to this surface. |
| Funnel | Present | `ce.funnel`: LP Users, LP2S, S2C, C2O, CVR; counts use %, rates use pp. | Complete stacked table with scope/unit definition. Proposed 12-week lines remain data extensions. |
| Top experiences / TGIDs | Present | Sticky TGID identity; Size, Value, Funnel, and Booking-window bands with every W0/W-1 field and source delta. V1 collapses bands to `···`. | Expanded state preserves the complete V1 table; collapsed rows use the proven V1 ellipsis fallback. Source-linked variants expand as subordinate rows in the same bands. Booking-grain Size, AOV, CR, TR, and booking-window fields remain aligned; TGID-only RPC/funnel fields render `—`. Null `variant_id` records must remain an unattributed child bucket so additive child totals reconcile to the parent. |
| Lead-time mix | Present | `ce.leadtime`: bookings, W-1, within-CE share, actual revenue, and AOV across four production bands. | Uses the four production bands (`0–2D`, `3–4D`, `5–7D`, `7D+`) with Orders W0/WoW/YoY, Revenue W0/WoW/YoY, Share, and a proposed 12-week Revenue line. AOV and visible W-1 values are omitted to reduce density. |
| Customer-country mix | Present | `ce.countries`: top six by source ordering; orders/WoW, revenue/WoW, share, AOV. | Kept in the compact V1 shape with Orders first-class. A proposed 12-week Revenue line is the only visible extension. |
| Slack context | Intentionally excluded | Exact CE-keyed `market_review_context` cards with tag/metric, channel/date, body, “so what,” and link. | Removed following product feedback. Contract remains recorded so the exclusion is explicit rather than accidental. |
| Current weekly note | Delegated | One note per market × CE × week; author, 600-char limit, sync state, Sheet truth, local cache, save/clear/error behavior, and All-CE dot repaint. | Owned by the review-mode worktree; no duplicate UI or persistence path in this mock. |
| Slack note post | Delegated | Save-before-post; empty guard; channel mapping; posted thread timestamp/permalink and retry/error states. | Owned with the note workflow in the review-mode worktree. |
| Note history | Delegated | Newest-first prior records with week, author, text, and optional Slack link; collapsible. | Owned by review mode, including E6 same-week visibility and future source-aware Granola work. |
| Perf action history | Delegated | Read-only `ce.perf_action_hist` sidecar from Weekly Flagged; newest-first week, final action, and comment. | Owned by review mode and remains distinct from team-note authorship. |
| Action-store compatibility | Delegated | Multi-week `losing_money` records through the shared action endpoint; avoid double-counting against `perf_action_hist`. | Canonical read-model decision belongs to review-mode integration; preserve bucket/week/CE keys. |
| Graceful absence | Missing parity | Optional Shapley/resource blocks omit when absent; nulls render `—`, never zero; unavailable LY says `LY n/a`. | Current dense fixture does not exercise sparse, global, null, or missing-LY states. Add fixture variants before production integration. |

### Verification result

- **Present (9):** revenue headline, complete Overall/Paid metrics, hover evidence, Shapley, and all five V1 resource surfaces.
- **Mock-only (3):** drawer lifecycle, identity/Omni live wiring, and shared watchlist persistence.
- **Missing parity (3):** every production entry point, canonical Overall-CVR definition, and sparse/null/`LY n/a` behavior.
- **Intentionally excluded (1):** CE-scoped Slack context.
- **Delegated (5):** current note, Slack post, note history, Perf history, and action-store reconciliation.

The first-fold revenue chart and the proposed Channel/Funnel/Lead-time/Country history lines are V2 presentation/data extensions. They do not satisfy or replace any V1 row above.

## Requested additions and bug fixes

| ID | Request | Priority / state | Source readiness at `0605e09` | Drawer decision |
| --- | --- | --- | --- | --- |
| A3 | Label WoW vs 4-week vs 12-week ranges clearly. | P1 · Planned | Ready; existing periods are already present. | Include explicit range labels throughout the mock and require them for integration. |
| A7 | Language-breakdown table in CE drawer. | P2 · Planned | Not present in schema-v1 CE payload. | Reserved resource section only; do not show values until an approved sidecar or snapshot field exists. |
| B4 | CVR inconsistency between headline/drawer and funnel. | P1 · Bug open | Multiple valid fields exist (`overall_cvr_pct`, `paid_cvr_pct`, funnel CVR). | Label scope and denominator beside every CVR. Investigate source discrepancy separately; no drawer-side recomputation. |
| B11 | Restore C2O within the CE funnel. | P2 · Bug open | V1 `ce.funnel` and TGID funnel include C2O when supplied. | Full parity requirement. Do not omit from V2 projection. |
| B12 | CVR appears twice with different definitions. | P2 · Bug open | Scope ambiguity, not necessarily a data defect. | “Overall CVR”, “Paid CVR”, and funnel “LP→Order CVR” labels plus definitions. |
| D5 | Use operational lead-time bands and show comparisons. | P2 · Planned | Current production query emits `0–2D`, `3–4D`, `5–7D`, `7D+` and only W0/W-1 bookings. | Keep the four production bands; request explicit Revenue W0/W-1/WoW/YoY and Share WoW/YoY pp fields before integration. |
| E6 | Prior-week / same-week CE comments are not visible to the GM. | P1 · Bug open | V1 list/sync/cache path exists. | Treat current note and prior history as one visible activity surface; test cache-empty then Sheet-sync repaint. |
| E9 | CE-keyed store-backed Perf finals, four-week history, drawer Perf row. | P1 · Parked | Rendered `perf_action_hist` exists; live Apps Script deployment is pending. | Preserve rendered sidecar now. Do not introduce a new write path in this slice. |
| A10 | “GM note” is mislabeled; BGM/BDM/Perf all contribute; support multi-owner comments. | P2 · Planned | Current record has one free-text `author` string. | Relabel to “Team note” now. Multi-owner structure requires a future backward-compatible contract; never infer owners from CE dimensions. |
| E11 | Granola-integrated CE note history for the last 1–2 weeks. | P1 · Planned | No approved Granola sidecar in schema-v1. | Show a source-aware reserved state in the mock. Integrate only with CE-keyed, dated, attributed records. |
| G11 | New-CE launch QA scorecard (price/product benchmark %, hero SDA). | P2 · Planned | No scorecard fields in schema-v1. | Conditional reserved section for New CEs; fail closed with “source unavailable.” |

## Iteration-2 enrichment contract

| Surface | Mocked addition | Existing-source readiness | Production gate |
| --- | --- | --- | --- |
| Channel | Revenue trend plus Share WoW/YoY pp in the existing scan-friendly table. | Current snapshot has W0/W-1 revenue, WoW, YoY, and share; historical arrays and share deltas are not contracted. | Add channel-keyed weekly revenue arrays and source-calculated share deltas without widening the visible metric set. |
| Lead time | Four production bands with Orders and Revenue W0/W-1/WoW/YoY plus Share WoW/YoY pp. | Current query has the four bands and W0/W-1 bookings, but no LY revenue/share economics. | Add source numerators for Revenue and LY comparisons; preserve current band boundaries. |
| Countries | Preserve the V1 Orders, Orders WoW, Revenue, Revenue WoW, Share, and AOV columns; add a Revenue trend. | Current columns are ready in `ce.countries`; historical country arrays are not contracted. | Preserve top-six source ordering and null rendering; add country-keyed history only from a sidecar. |
| Variant reporting | Expandable child rows use the TGID band header instead of a separate mini-table. Supported booking-grain metrics remain visible; RPC and funnel are explicitly TGID-only. | Read-only BigQuery CLI verification confirms `fct_bookings` contains `experience_id`, `variant_id`, booking economics and lead time; `mixpanel_user_page_funnel_progression` contains `experience_id` but no variant key. A 30-day reconciliation sample produced zero Revenue and Order difference between variant children and the TGID parent when null IDs were retained as unattributed. | Add a booking-grain variant sidecar keyed by CE + TGID + variant. Preserve the unattributed bucket, verify additive Revenue/Orders/Share, and never project TGID funnel values onto variants. |
| Trendlines | Filled TY area, distinct dashed LY, nearest-week cursor and tooltip for Channel, Funnel, Lead time, and Countries. | Presentation-ready for existing weekly metrics. Resource tables still lack approved 12-week arrays. | Use real weekly arrays only; never synthesize resource history in production. |

## Drawer-only boundary

The mockup is a standalone, sanitized HTML artifact. It does not import the production template, call network endpoints, write localStorage, or modify the All-CE table, filters, grouping, sorting, overview, navigation, weekly engine, bucket logic, publish flow, Slack, or Sheets. Integration should be a later reviewable slice after this matrix and mockup are approved.
