---
name: market-weekly-report
description: Build and inspect Headout weekly market reports, shared snapshot metrics, CE drawers and diagnostic buckets. Uses complete Sunday–Saturday weeks. For production V2 packaging and delivery, follow the canonical weekly-market-report-v2 release procedure; legacy V1 workflows remain available only as an explicit fallback.
---

# Market Weekly Report

## Canonical V2 package

For a complete V2 release candidate—every configured market plus Headout—use:

```bash
python3 scripts/weekly_report/run_v2_release.py --week <YYYY-MM-DD> \
  --base-notebook /absolute/path/to/verified-complete-notebook --plan
```

Read `docs/v2/release-workflow.md` before any release or alert operation. `--plan`
is no-write; omitting it builds local artifacts and runs read-only source queries.
The V2 path includes all 17 configured markets plus Headout, frozen required RCA,
full-notebook preservation, signed-in browser proof and duplicate-safe delivery.
Deployment requires `--deploy`; posting additionally requires `--post-alerts`,
both with user authorization. `awaiting_browser_verification` is not completion;
resume using the receipt's `planned_steps`, never by rerunning generation.

The staged `run_weekly.py --alert-version v2 --post` path is disabled. Never use
the legacy poster below for V2 delivery or retries. The S1–S5 descriptions below
document the V1 fallback/curation flow, not the production V2 release procedure.
Local regression tests do not prove live delivery or authorize activation.

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
/market-weekly-report <market|all|headout> [<week-Sunday>]
```
- `/market-weekly-report north_america` — latest complete Sunday–Saturday week
- `/market-weekly-report all 2026-08-30` — all configured markets for that week
- `/market-weekly-report headout 2026-08-30` — **true-global Headout rollup** (all ~69
  `business_market` values, not a sum of the 10 pilots). Own build path (`build_global.py`):
  queries BQ with NO market filter, so the headline is exact ($3.26M for 07-13, vs the merge-of-10's
  17.5%-undercounted $2.69M). Adds a §1 per-market breakdown, a Market column/filter/group-by, and
  bounds the expensive Mixpanel RE-SOURCE drawers to the surfaced-CE set only.
- Markets: resolve current coverage from `config.MARKETS` (17 at this release). `headout` is separate — it does not read
  `config.MARKETS`, it queries every market in the warehouse.

## Legacy V1 workflow (not the V2 release path)

**Full run (all markets), end-to-end** — driven by `run_weekly.py`, which chains the deterministic
glue and stops at the two human/agent gates. Three stages:
```bash
cd <repo>/scripts/weekly_report
python3 run_weekly.py all --week <W> --stage report    # S2 build+render; lists markets needing a digest
#   ← S3: fan out one digest agent per market → writes .cache/…/slack_context_{slug}_{week}.json
python3 run_weekly.py all --week <W> --stage publish    # reload digests + re-render + publish_weekly (stages Ledger)
#   ← USER: ! vercel deploy --prod --cwd market-notebook-v2   (from ~/analytics)
python3 run_weekly.py all --week <W> --stage alert      # S5 dry-run per market; add --post to go live
```
Each stage prints the exact next action. **S3 (curation) and S5 (post) are the only non-deterministic /
human-gated steps** — S3 needs agents, the deploy + live post are human-gated; everything else is a plain
script. Big markets (CSEE/SEA) can exceed BQ byte caps — `config.MAX_BYTES_BILLED` (build) and
`weekly_rca_helper.MAX_BYTES_BILLED` (RCA) are both 80 GB. The stages below (S1–S5) document each piece.

### S1 · Resolve market(s) + week
Slug or `all`. Omitted week → `config.latest_complete_week()` (most recent complete
Sunday–Saturday week). Use an explicit Sunday for releases. Bucket-specific
maturity handling must not shift the headline week.

### S2 · Run the producer
```bash
cd <repo>/scripts/weekly_report && python3 weekly_market_report.py <market|all> [--week YYYY-MM-DD] --no-open
```
Builds a snapshot per market (`.cache/weekly_report/snapshot_{slug}_{week}.json`) then renders once →
`thoughts/shared/weekly-report-v1/report_{slug}_{week}.html` (single) or `report_multi_{week}.html`
(`all`). `--validate` runs the **NA reference gate**, but that gate is **stale**: its `VALIDATION_NA`
fixtures were calibrated to the pre-2026-08 daily-POF fluctuation engine that the L3W re-cut replaced
(single ±35% vs the prior 21 days; no CV / 3-day / cv-excluded), and its `week_start` is a Monday that
is invalid under `WEEK_START_DAY = SUNDAY`. It will MISMATCH until re-baselined against a live NA run.
Until then, run **without** `--validate` and spot-check in S4.

### S3 · Slack-signal briefing (agent step — folded into the report)
The data can't see supply wins, bugs, supplier/payment/bid changes. Mine them and write a **sidecar**
the producer auto-loads into §2 Market Review:

1. Load Slack read tools: `ToolSearch("+slack read channel")`.
2. Read the market channel(s) + the two global channels for the **report week window** (Sun 00:00 →
   next Sun 00:00, as Unix ts):

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

### S4.5 · Publish + deploy the Ledger
Stage the trailing-6-week matrix into the Vercel Ledger, then go live:
```bash
cd <repo>/scripts/weekly_report && python3 publish_weekly.py all --week <W>   # → ~/analytics/market-notebook-v2/
```
This rewrites `weekly.html` + `weekly-report-{slug}.html` + `weekly_state.json`, rolling the current
column to `<W>` (local files only — nothing live yet). Then the **USER** deploys (interactive auth):
```bash
! vercel deploy --prod --cwd market-notebook-v2   # from ~/analytics
```
Do this **before** S5 so the alert's "→ weekly report" link resolves to the just-published week (else
the ping is for `<W>` but the linked report shows the previous week). Live at `market-notebook.vercel.app/weekly`.

### S5 · Slack revenue alert (dry-run → USER posts)
Turn the report into a per-market Slack alert with the `alert/` bundle. Two top-level messages:
**MSG 1** = summary (headline + 6 WoW metrics + Top-5 drops/gains) with threads for the 3 §4 tables
(Losing Money · RPC Fluctuations ↓ · ↑, read from the report JSON); **MSG 2** = movers with a per-CE
**BigQuery, user-based** revenue diagnosis thread (matches Omni — exactly like the monthly alert).
Run the 3-step flow **per market** (loop the slugs present in the report):

```bash
cd <repo>/alert
# 1) summary + 3 tables from the report JSON (stdlib only) — prints RCA_CE_IDS / WEEK, also in payload._rca
python3 weekly_alert.py --file <weekly-report.html> --market-slug <slug> --out payload.json
# 2) per-CE user-based RCA blocks (BigQuery; needs ADC on headout-analytics)
python3 weekly_rca_helper.py --ce-ids "<RCA_CE_IDS>" --week-start <s> --week-end <e> --out rca_blocks.json
# 3) render — DRY-RUN first (no token needed), then hand the USER the live command
python3 post_message.py --payload payload.json --rca-blocks rca_blocks.json --dry-run
```

- **Losing Money table sources `buckets_final.defend.losing_money`** (the §4 bucket, Google-only) —
  NOT the legacy `bucket_b1` block — so the alert matches the report.
- **Market greeting:** MSG1 opens `Hello team @<market> <flag>` (`weekly_alert.MARKET_TEAM`), mirroring
  the monthly alert. ⚠ `@handle` text in a Block Kit block is **cosmetic** (does not notify); a real
  team notification needs a `<!subteam^ID>` mention, which needs `usergroups:read` on the token —
  run `resolve_market_usergroups.py` once that scope is added, then swap `MARKET_TEAM` to subteam IDs.
- **Editing a posted alert never notifies** — `update_posts_weekly.py` edits parents + bucket threads
  in place (no re-ping); to notify on a change, repost or add a thread reply.
- Channel from `alert/market_channels.json[markets][<slug>]` — all 10 real channels set + bot is a
  member (east_asia/sea/uae point at #mkt-japan/#mkt-singapore/#mkt-mena, narrower than the full market).
- **Never auto-send.** Live posts need `REVENUE_ALERT_SLACK_TOKEN` (xoxb, ask the alert owner —
  intentionally not in the bundle) and are handed to the user:
  `! post_message.py --payload payload.json --rca-blocks rca_blocks.json --channel <REAL id>`
- See `alert/README.md` for the full spec + a one-hook loop-all-markets wrapper.

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
