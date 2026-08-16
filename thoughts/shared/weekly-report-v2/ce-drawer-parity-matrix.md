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
| Key metrics | Present | Overall and Paid inventories; W0, W-1, delta %, and 12-week TY/LY per metric. | Both groups are projected from `ce.weekly`/`weekly_ly` into the live V2 drawer without presentation-layer metric recomputation. |
| Metric hover evidence | Present | Pointer reveals week, TY, LY, and YoY when LY is non-zero. | Hover and keyboard focus expose all four values; expandable rows expose every week. Shared scale and TY/LY styling are explicit. |
| Overall-CVR definition | Present | The snapshot retains `overall_cvr_pct = orders ÷ all-traffic clicks`, while `ce.funnel.CVR` is LP2S × S2C × C2O and Paid CVR is paid conversions ÷ paid clicks. | The V2 drawer now uses the funnel source for its explicitly labeled “LP→Order CVR,” so its W0/W-1 values and pp change match the funnel table. Paid CVR remains separately labeled; no unavailable funnel history is synthesized. |
| WoW Shapley | Present | Optional traffic, CVR, AOV, completion, and take-rate USD contributions plus net. | All factors, signs, attribution, and reconciliation are represented. Conditional omission remains covered by Graceful absence. |
| Channel mix | Present | `ce.channels`: actual W0/W-1 revenue, WoW, YoY, and within-CE share. | Live V2 renders the complete snapshot-backed table and source-calculated share WoW/YoY pp. No resource history is synthesized. |
| Funnel | Present | `ce.funnel`: LP Users, LP2S, S2C, C2O, CVR; counts use %, rates use pp. | Live V2 renders the complete snapshot-backed table with the V1 count/rate delta semantics. Proposed 12-week lines remain data extensions. |
| Top experiences / TGIDs | Present | Sticky TGID identity; Size, Value, Funnel, and Booking-window bands with every W0/W-1 field and source delta. V1 collapses bands to `···`. | Live V2 preserves the TGID metrics and adds expandable, booking-grain variant children. Null IDs stay unattributed; child Revenue and Orders reconcile to the parent; TGID-only RPC/funnel fields render `—`. |
| Lead-time mix | Present | `ce.leadtime`: bookings, W-1, within-CE share, actual revenue, and AOV across four production bands. | The live source query now emits `0D`, `1–2D`, `3–4D`, `5–7D`, and `7D+`, with W0/W-1/LY Orders, Revenue, Share deltas, and AOV. V2 displays the approved compact Orders/Revenue/Share set. |
| Customer-country mix | Present | `ce.countries`: top six by source ordering; orders/WoW, revenue/WoW, share, AOV. | Live query and V2 projection add matched LY Orders/Revenue/AOV and YoY movement while preserving the V1 columns and top-six rule. |
| Slack context | Intentionally excluded | Exact CE-keyed `market_review_context` cards with tag/metric, channel/date, body, “so what,” and link. | Removed following product feedback. Contract remains recorded so the exclusion is explicit rather than accidental. |
| Current weekly note | Delegated | One note per market × CE × week; author, 600-char limit, sync state, Sheet truth, local cache, save/clear/error behavior, and All-CE dot repaint. | Owned by the review-mode worktree; no duplicate UI or persistence path in this mock. |
| Slack note post | Delegated | Save-before-post; empty guard; channel mapping; posted thread timestamp/permalink and retry/error states. | Owned with the note workflow in the review-mode worktree. |
| Note history | Delegated | Newest-first prior records with week, author, text, and optional Slack link; collapsible. | Owned by review mode, including E6 same-week visibility and future source-aware Granola work. |
| Perf action history | Delegated | Read-only `ce.perf_action_hist` sidecar from Weekly Flagged; newest-first week, final action, and comment. | Owned by review mode and remains distinct from team-note authorship. |
| Action-store compatibility | Delegated | Multi-week `losing_money` records through the shared action endpoint; avoid double-counting against `perf_action_hist`. | Canonical read-model decision belongs to review-mode integration; preserve bucket/week/CE keys. |
| Graceful absence | Missing parity | Optional Shapley/resource blocks omit when absent; nulls render `—`, never zero; unavailable LY says `LY n/a`. | Current dense fixture does not exercise sparse, global, null, or missing-LY states. Add fixture variants before production integration. |

### Verification result

- **Present (10):** revenue headline, complete Overall/Paid metrics, hover evidence, scoped CVR, Shapley, and all five V1 resource surfaces.
- **Mock-only (3):** drawer lifecycle, identity/Omni live wiring, and shared watchlist persistence.
- **Missing parity (2):** every production entry point and sparse/null/`LY n/a` behavior.
- **Intentionally excluded (1):** CE-scoped Slack context.
- **Delegated (5):** current note, Slack post, note history, Perf history, and action-store reconciliation.

The first-fold revenue chart and the proposed Channel/Funnel/Lead-time/Country history lines are V2 presentation/data extensions. They do not satisfy or replace any V1 row above.

## Requested additions and bug fixes

| ID | Request | Priority / state | Source readiness at `0605e09` | Drawer decision |
| --- | --- | --- | --- | --- |
| A3 | Label WoW vs 4-week vs 12-week ranges clearly. | P1 · Planned | Ready; existing periods are already present. | Include explicit range labels throughout the mock and require them for integration. |
| A7 | Language-breakdown table in CE drawer. | P2 · Planned | Not present in schema-v1 CE payload. | Reserved resource section only; do not show values until an approved sidecar or snapshot field exists. |
| B4 | CVR inconsistency between headline/drawer and funnel. | P1 · Done in V2 drawer | Multiple valid fields exist (`overall_cvr_pct`, `paid_cvr_pct`, funnel CVR). | Drawer headline now reads `ce.funnel.CVR`, exactly matching the funnel row. |
| B11 | Restore C2O within the CE funnel. | P2 · Done in V2 drawer | V1 `ce.funnel` and TGID funnel include C2O when supplied. | C2O is projected and rendered at CE and TGID grain. |
| B12 | CVR appears twice with different definitions. | P2 · Done in V2 drawer | LP→Order CVR and Paid CVR have different valid denominators. | The two metrics are explicitly named and defined; ambiguous “Overall CVR” is removed from the drawer. |
| D5 | Split same-day availability and show comparisons. | P2 · Implemented in live drawer source | BigQuery CLI verification confirms integer `lead_time_days` supports distinct `0 days` and `1–2 days`; the production query emits five bands and matched W0/W-1/LY numerators. | Render source-calculated Orders/Revenue WoW and YoY plus Share; retain AOV in the snapshot contract. |
| E6 | Prior-week / same-week CE comments are not visible to the GM. | P1 · Bug open | V1 list/sync/cache path exists. | Treat current note and prior history as one visible activity surface; test cache-empty then Sheet-sync repaint. |
| E9 | CE-keyed store-backed Perf finals, four-week history, drawer Perf row. | P1 · Parked | Rendered `perf_action_hist` exists; live Apps Script deployment is pending. | Preserve rendered sidecar now. Do not introduce a new write path in this slice. |
| A10 | “GM note” is mislabeled; BGM/BDM/Perf all contribute; support multi-owner comments. | P2 · Planned | Current record has one free-text `author` string. | Relabel to “Team note” now. Multi-owner structure requires a future backward-compatible contract; never infer owners from CE dimensions. |
| E11 | Granola-integrated CE note history for the last 1–2 weeks. | P1 · Planned | No approved Granola sidecar in schema-v1. | Show a source-aware reserved state in the mock. Integrate only with CE-keyed, dated, attributed records. |
| G11 | New-CE launch QA scorecard (price/product benchmark %, hero SDA). | P2 · Planned | No scorecard fields in schema-v1. | Conditional reserved section for New CEs; fail closed with “source unavailable.” |

## Live roadmap reconciliation — CE drawer

Checked read-only against `Roadmap!A1:K1000` on 2026-08-16. “Done” means implemented in this CE-drawer worktree; it does not alter the roadmap Sheet’s own Status column.

| Roadmap ID | CE-drawer ask | Implementation state | Evidence / remaining work |
| --- | --- | --- | --- |
| A3 | Make WoW / 4-week / 12-week ranges legible. | **Done for drawer** | W0, W-1, WoW and 12-week TY/LY labels are explicit; unavailable histories remain visibly unavailable. |
| A7 | Add a language-breakdown table. | **Not done** | No approved CE-language source exists in schema-v1. |
| B4 | Fix top/drawer CVR versus funnel inconsistency. | **Done** | Drawer CVR now uses `ce.funnel.CVR`, matching the LP→Order funnel row. |
| B11 | Restore C2O in the CE CVR funnel. | **Done** | CE and TGID funnel surfaces retain C2O. |
| B12 | Disambiguate duplicate CVR definitions. | **Done** | Drawer uses “LP→Order CVR”; Paid uses “Paid CVR,” with denominators stated. |
| D5 | Lead-time WoW plus finer `0d` / `1–2d` split. | **Done** | Live BQ query and snapshot emit five bands with Orders/Revenue WoW and YoY plus Share. |
| E6 | Show prior-week / same-week CE comments. | **Not done here — delegated** | Owned by Review mode; intentionally absent from this drawer worktree. |
| E9 | Store-backed Perf finals, four-week history and drawer row. | **Not done here — delegated** | Review-mode persistence/deployment remains pending. |
| A10 | Relabel GM comments and support multiple owners. | **Not done here — delegated** | Review mode owns the Team-note model and backward-compatible author contract. |
| E11 | Add CE-keyed Granola note history. | **Not done** | No approved CE-keyed Granola sidecar is available. |
| G11 | Add New-CE launch QA scorecard. | **Not done** | Price/product benchmark and hero-SDA fields are not in schema-v1. |

Adjacent roadmap rows E7/E13 concern the Review-mode comment/posting workflow, not the read-only CE evidence drawer, and remain outside this worktree.

## Iteration-2 enrichment contract

| Surface | Mocked addition | Existing-source readiness | Production gate |
| --- | --- | --- | --- |
| Channel | Revenue trend plus Share WoW/YoY pp in the existing scan-friendly table. | Current snapshot has W0/W-1 revenue, WoW, YoY, and share; historical arrays and share deltas are not contracted. | Add channel-keyed weekly revenue arrays and source-calculated share deltas without widening the visible metric set. |
| Lead time | Five bands: `0 days`, `1–2 days`, `3–4D`, `5–7D`, `7D+`, with Orders and Revenue W0/WoW/YoY plus Share. | Production now reads integer `lead_time_days` plus matched W0/W-1/LY booking and economics fields. | Implemented; preserve null/negative exclusions, total reconciliation, and compact rendering. |
| Countries | Preserve the V1 Orders, Orders WoW, Revenue, Revenue WoW, Share, and AOV columns; add a Revenue trend. | Current columns are ready in `ce.countries`; historical country arrays are not contracted. | Preserve top-six source ordering and null rendering; add country-keyed history only from a sidecar. |
| Variant reporting | Expandable child rows use the TGID band header instead of a separate mini-table. Supported booking-grain metrics remain visible; RPC and funnel are explicitly TGID-only. | Live `fct_bookings` + `fct_orders` query is keyed by CE + TGID + variant, allocates order economics once, and retains null IDs. CLI verification found 11,781/11,781 W0 booking rows matched the order TGID; the reconciliation sample produced zero Revenue and Order difference. | Implemented in the snapshot and V2 renderer; retain additive Revenue/Orders tests and never project TGID funnel values onto variants. |
| Trendlines | Filled TY area, distinct dashed LY, nearest-week cursor and tooltip for Channel, Funnel, Lead time, and Countries. | Presentation-ready for existing weekly metrics. Resource tables still lack approved 12-week arrays. | Use real weekly arrays only; never synthesize resource history in production. |

## Drawer-only boundary

The standalone mockup remains sanitized and network-free. The production V2 drawer now reads the schema-v1 live snapshot contract, but does not modify the All-CE table, filters, grouping, sorting, overview, navigation, weekly engine, bucket logic, publish flow, Slack, or Sheets. Notes/actions remain delegated and CE-scoped Slack context remains excluded.
