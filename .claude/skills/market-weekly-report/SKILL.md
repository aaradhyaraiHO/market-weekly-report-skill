---
name: market-weekly-report
description: Weekly market report for the pilot markets (North America / Italy / Oceania) — one command builds the movement-flow buckets B1-B4 (ROI/CM2 movement, fluctuations, losing ground, scale windows) + week-type header into a single self-contained multi-market tabbed HTML. Runs `/market-weekly-report <market|all> [<week-Monday>]`; default week = latest complete matured week. Use for the Monday weekly market read; agent adds a Slack digest of signal beyond the data.
---

# Market Weekly Report

Weekly-cadence market report for the pilot markets. One orchestrator command builds a per-market snapshot (12 weeks, weekly grain, revenue = `sum_revenue_predicted`) and renders **one self-contained tabbed HTML** with a market-switcher tab per market. §4 is a movement-flow bucket narrative — B1 ROI/CM2 movement, B2 fluctuations, B3 losing ground, B4 scale windows, cross-bucket cascade (one home per CE) — under a week-type header (structural gains/losses vs LY seasonality). The producer is self-contained; the only agent step beyond running it is a Slack digest of signal the data cannot see.

**Audience:** BGM / BizOps / Performance ahead of the Monday weekly market read. Every line must pass "Would the reader do something different after reading this?"

**Dependencies:** Python ≥3.9, `google-cloud-bigquery` + `pandas`, BigQuery ADC on `headout-analytics` (EU, `analytics_reporting` dataset), Slack MCP (for the S3 digest only — the producer never reads Slack). Pipeline: `scripts/weekly_report/weekly_market_report.py` (orchestrator) → `build_snapshot.py` (producer) → `render.py` (HTML).

## Usage

```
/market-weekly-report <market|all> [<week-Monday>]
```

Examples:
- `/market-weekly-report north_america` — latest complete matured week
- `/market-weekly-report all` — all three pilot markets, one tabbed HTML
- `/market-weekly-report italy 2026-06-29` — Italy, specific week
- `/market-weekly-report all 2026-06-29` — all three markets for the week of 2026-06-29

## Workflow

### S1: Resolve market(s) + week

Slugs are `north_america`, `italy`, `oceania`; `all` = all three. If the week (a Monday, `YYYY-MM-DD`) is omitted, the orchestrator defaults to `config.latest_complete_week()` — the most recent fully-complete week whose Sunday end is ≥3 days matured. If the user passes a non-Monday date, use the Monday of that ISO week.

### S2: Run the orchestrator (NA gate is a hard gate)

```bash
cd <repo>/scripts/weekly_report && python3 weekly_market_report.py <market|all> [--week YYYY-MM-DD] --validate
```

The orchestrator builds a snapshot per market, then calls `render.py` **once** with all snapshot paths → a single tabbed HTML under `thoughts/shared/weekly-report-v1/`. With `--validate`, when `north_america` is in the set the NA reference gate runs and **must print `RESULT: PASS`** (5 CM1/conv up-swings, 0 CV-excluded) — **abort and fix if it prints `FAIL`**. Other markets have no reference gate; spot-check them in S4. Add `--no-open` for headless/scheduled runs. The rendered path is printed as `wrote: <path>`.

### S3: Slack digest (agent step — the producer cannot read Slack)

The HTML carries everything in the data; this step adds **signal beyond the data** — supply wins, bugs, supplier/payment issues, bid-change context. For V1 this is presented in chat alongside the report link (not injected into the HTML).

1. Load Slack tools: `ToolSearch("+slack read channel")`, then `slack_read_channel` per channel.
2. **Market → channel mapping** (read the market channel(s) for the report week):

   | Market | Channel ID(s) |
   |--------|---------------|
   | north_america | CNSHDD2H1 |
   | italy | C045L2WQ79P |
   | oceania | CHKRLFDPU, C039TMH0GEP, C097DVBLHGS |

3. **Global channels — always read:** `#tf-bugalert` (C038T64PD), `#pod-live-entertainment` (C042A57T52Q).
4. Extract ONLY signal beyond the data, prioritized by **Hero+ CE × revenue-topic** (the CEs and themes the report's buckets flag). Present the digest in chat next to the report link.

**Rules:** verify specifics match (same TGID/supplier/time horizon) before connecting a Slack item to a data signal; near-term (0-2D) ≠ long-term availability; permalink timestamps must fall inside the report week; no time/difficulty editorializing; no extra parens around links.

### S4: QA + deliver

Confirm the HTML opens. Spot-check per market: **§1 week-type verdict** (header) and **§4 buckets** (B1-B4 home rows + cascade). For Italy/Oceania (no reference gate) sanity-check the headline W0 revenue against Omni. Report the HTML path to the user with the Slack digest.

## Engine notes

- **Revenue = `sum_revenue_predicted`** (analytics-skill canon), NOT actuals. AOV = GBV / orders; TR / CVR / CM1 / ROI(1) per canon.
- **Buckets = movement-only flow.** §4 renders CEs whose state *changed* this week, with a **B1 > B2 > B3 > B4 cascade** giving each CE one home bucket (`also_in` chips for the rest) and a **hard cap of 10** problem rows by $ at stake (B1 problems never dropped; B1 EXITs render as wins). Bucket detection/thresholds are imported from `scripts/ce_buckets/` for cross-cadence consistency with the monthly review — do NOT change them here.
- **§5 seasonality / §6 levers** are driven by `seasonality_config.csv` / `levers_config.csv`; when empty they render an empty-state (graceful degrade).
- **Week-type calibration:** the header's "large" gains/loss threshold is the **p75 of the market's trailing-52-week |WoW-Δ| distribution** (falls back to a market-size $-floor when <20 weeks of history). Small markets churn more, so this replaces the old fixed floor that mislabelled Italy/Oceania. The header emits `calibration: {method, threshold_usd}`.
- **B5 Action Verdicts + overlays (Top-CEs strip, Gap/Pacing)** are deferred (need tracker infra / `revenue_goals`) and degrade to absent.

## Related Skills
- `/market-monthly-review` — single-market monthly review (the cadence sibling)
- `/monthly-growth-review` — portfolio-level monthly (multi-market)
- `/perf-audit` — standalone deep paid audit
