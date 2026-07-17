---
name: market-weekly-report
description: Weekly market growth report for a Headout market — one command builds a self-contained HTML with trend movers (4-wk vs raw, seasonal-tagged), a per-market Digest (flagged-CE follow-ups + a Slack-signal briefing + GM narrative), the full All-CE view with a CE drawer (vitals, funnel, Shapley, RE-SOURCE, GM notes), Defend/Compound/Lifecycle diagnostic buckets, seasonality, and prepurchase tracking. Runs `/market-weekly-report <market|all> [<week-Monday>]`; default week = latest complete matured week. Use for the Monday weekly market read; the agent then mines Slack for signal beyond the data and folds it into the report.
---

# Market Weekly Report

Weekly-cadence, market-level growth report. One orchestrator command builds a per-market snapshot
(12 weeks, weekly grain, revenue = `sum_revenue_predicted`) and renders a **self-contained HTML**
(one file per market; `all` produces a tabbed multi-market file). The producer is fully data-driven;
the one agent step beyond running it is a **Slack-signal briefing** (S3) that the pipeline can't
produce — folded into the report via a sidecar.

**Audience:** BGM / BizOps / Performance ahead of the Monday market read. Every line must pass
"would the reader do something different after reading this?"

**Dependencies:** Python ≥3.9, `google-cloud-bigquery` + `pandas`, BigQuery ADC on `headout-analytics`
(EU, `analytics_reporting`). Slack MCP for S3 + GM-note channels (the producer never reads Slack).
Optional: `ANTHROPIC_API_KEY` for the seasonality Explore layer (deterministic heuristic fallback if
absent). GM notes need the Apps Script notes backend (`config.NOTES_SCRIPT_URL`).
Pipeline: `scripts/weekly_report/weekly_market_report.py` (orchestrator) → `build_snapshot.py`
(producer) → `render.py` (HTML).

## Usage

```
/market-weekly-report <market|all> [<week-Monday>]
```
- `/market-weekly-report north_america` — latest complete matured week
- `/market-weekly-report all 2026-07-06` — all pilot markets for that week, one tabbed HTML
- Markets (config.MARKETS): `north_america`, `italy`, `oceania`. Expansion to the full 10 live
  markets is planned (see the fan-out plan); this skill runs whatever is in `config.MARKETS`.

## Workflow

### S1 · Resolve market(s) + week
Slug or `all`. Omitted week → `config.latest_complete_week()` (most recent complete week whose
Sunday end is ≥3 days matured). A non-Monday date → the Monday of that ISO week.

### S2 · Run the producer
```bash
cd <repo>/scripts/weekly_report && python3 weekly_market_report.py <market|all> [--week YYYY-MM-DD] --no-open
```
Builds a snapshot per market (`.cache/weekly_report/snapshot_{slug}_{week}.json`) then renders once →
`thoughts/shared/weekly-report-v1/report_{slug}_{week}.html` (single) or `report_multi_{week}.html`
(`all`). `--validate` runs the **NA reference gate**, but that gate is frozen to the 2026-06-29
build (5 CM1/conv up-swings, 0 CV-excluded) — it only PASSes for that week. For any other week run
**without** `--validate` and spot-check in S4.

### S3 · Slack-signal briefing (agent step — folded into the report)
The data can't see supply wins, bugs, supplier/payment/bid changes. Mine them and write a **sidecar**
the producer auto-loads into §2 Market Review:

1. Load Slack read tools: `ToolSearch("+slack read channel")`.
2. Read the market channel(s) + the two global channels for the **report week window** (Mon 00:00 →
   next Mon 00:00, as Unix ts):

   | Market | Channel ID(s) |
   |--------|---------------|
   | north_america | CNSHDD2H1 |
   | italy | C045L2WQ79P |
   | oceania | CHKRLFDPU, C039TMH0GEP, C097DVBLHGS |

   Global (always): `#tf-bugalert` C038T64PD · `#pod-live-entertainment` C042A57T52Q.
3. Extract ONLY signal beyond the data, **prioritized by the CEs the report flags** (top movers +
   bucket members). For each item build a card and write them to
   `.cache/weekly_report/slack_context_{slug}_{week}.json` as a JSON list of:
   ```
   {group:'risk'|'win'|'ctx', ce, tag, tag_kind:'risk'|'win'|'watch'|'ctx',
    channel, date, so_what, body, metric, metric_kind:'red'|'green'|'amber'|'purps',
    link,   # link = REAL Slack permalink, canonical form: .../archives/{CH}/p{ts_nodot}?thread_ts={ts}&cid={CH}
    scope:'market'|'ce', ce_id}   # routing — see below; scope defaults to 'market' if omitted
   ```
   **Routing (`scope` / `ce_id`):** a card either belongs to the market at large or to one specific CE.
   - `scope:'ce'` — the item is about a specific CE (names its TGID/supplier/campaign). Set `ce_id`
     to that CE's `combined_entity_id` — it **must exactly match** a `ces[].ce_id` in the snapshot
     (grep the snapshot if unsure; a wrong `ce_id` silently orphans the card). These render inside
     that CE's **drawer** under a "Slack context" section, not in §2.
   - `scope:'market'` (or omitted) — market-wide signal (portfolio strategy, competitive landscape,
     market-wide bug). Leave `ce_id` null. These render in the **§2** grouped digest.
   Get the real message `ts` from a detailed channel read or `slack_search_public` (never fabricate a
   permalink). Then re-run `render.py` on the cached snapshot so §2 + the drawers show the cards.
4. **Rules:** verify specifics match (same TGID/supplier/time horizon) before tying a Slack item to a
   data signal; near-term (0-2D) ≠ long-term availability; permalink timestamp must fall inside the
   report week; no editorializing; no extra parens around links.

### S4 · QA + deliver
Open the HTML. Spot-check: **§1** week-type verdict + top movers; **§2** the market-scoped Slack
cards resolve to the right threads, and any `scope:'ce'` cards land in their CE's drawer (open one
to confirm the "Slack context" section); **§4** Defend/Compound/Lifecycle bucket membership; **§6** prepurchase.
For non-NA markets sanity-check headline W0 revenue vs Omni. Report the HTML path.

## What the report contains
- **§1 Market headlines** — revenue verdict + dual-clock (raw vs LY-seasonal) header; **top movers**
  ranked by the bigger of 4-wk-trend / raw-WoW, each with a lens label + a seasonal tag
  (seasonal / against season / mostly TY / no LY).
- **§2 {Market} Digest** (collapsible, Show/Hide) — **Follow-up** (last week's flagged CEs) +
  **Market Review** (the S3 Slack-signal briefing grouped into Risks / Tailwinds / Context, plus a
  localStorage narrative composer).
- **§3 All-CE view** — sortable/filterable table; click a CE → drawer (vitals, funnel, Shapley,
  RE-SOURCE composition, and the **GM note**).
- **§4 Diagnostic buckets** — Defend (Losing Money · Fluctuations↓), Compound (Scale-Up ·
  Fluctuations↑), Lifecycle (New CEs · Iteration/Untapped). Detection lives in `buckets.py`.
- **§5 Seasonality** · **§6 Prepurchase** (`dim_pp_allotments` → CE, with stale-allotment flag),
  levers, no-bid.

## GM notes (per-CE, per-week)
Each CE drawer has a **GM note**: one note per (market, CE, week), current week editable, prior weeks
shown as collapsible history (author + Slack thread link), with **Post to #channel**. Backed by a
Google Sheet via Apps Script (`config.NOTES_SCRIPT_URL`, env `WR_NOTES_SCRIPT_URL`) + Slack.
`notes.py` exposes `notes_for_report()` / `open_notes()` for pipeline use (not yet wired).
⚠ Notes sync only over **http(s)** (the deployed ledger); from a local `file://` they save to
localStorage only (browser CORS blocks the cross-origin write).

## Engine notes
- **Revenue = `sum_revenue_predicted`** (analytics-skill canon). AOV = GBV/orders; TR/CVR/CM1/ROI(1)
  per canon. Paid metrics from `ads_campaign_stats` (Google + Bing Search).
- **Movers** (`flows.py`): trend = W0 − trailing-4-wk avg; raw = W0 − W-1; ranked by the union of
  top-10 on either; seasonal tag from LY same-week WoW.
- **Week-type calibration**: "large" threshold = p75 of the market's trailing-52-wk |WoW-Δ|
  (falls back to a size-floor under 20 weeks).
- **Seasonality Explore layer** (`seasonality_llm.py`): per-CE high/low-season tag; heuristic default,
  optional LLM enrichment; always emits full coverage.

## Related
- `/market-monthly-review` — single-market monthly (cadence sibling; owns The Ledger deploy)
- `/perf-audit`, `/ce-rca` — CE-level deep dives
