---
name: market-weekly-alert-v2
description: "Build or revise the separate V2 Headout market weekly Slack alert: Alert 1 tags configured market BGMs and shows revenue plus six separately named business and Paid Search metrics, followed by the four finalized market-level Pro+ and GEL KRs; Alert 2 shows the report-owned Top 5 and Bottom 5 against last week, trailing four weeks, last year, and target, with per-CE weekly alert threads. Use for V2 weekly market alert generation, dry runs, BGM mapping, OKR sidecar generation, or validation. Never modify or silently fall back to the V1 alert path."
---

# Market Weekly Alert V2

Build two Slack parent messages from the schema-v2 headline report produced by `codex/v2-market-headlines`. Keep V2 isolated under `alert/v2/`; leave `alert/weekly_alert.py` and the V1 flow unchanged.

Read `references/input-contract.md` before changing the producer or builder. Read `references/okr-tracker.md` before changing OKR logic or refreshing the market sidecar.

## Workflow

1. Generate or obtain the V2 headline HTML with an approved goals sidecar. Confirm its embedded `report-data` has `schema_version: 2` and a `headlines` list. Never use the V1 `markets` payload as a fallback.
2. Resolve every market BGM to a real Slack `U...` ID and update only `alert/v2/market_bgms.json`. Do not use cosmetic `@name` text.
3. Build the four finalized market-level KRs for the same report week. The command is read-only:

```bash
python3 alert/v2/build_market_okr_results.py \
  --week-start <YYYY-MM-DD> \
  --out <okr-results.json>
```

4. Confirm the OKR sidecar week equals the V2 headline week. Never use the company-level `weekly_kr_metrics` row as a market result and never allocate company targets to markets.
5. Build the V2 payload:

```bash
python3 alert/v2/weekly_alert_v2.py \
  --file <weekly-report.html> \
  --market-slug <slug> \
  --okr-results <okr-results.json> \
  --out <payload-v2.json>
```

6. Compute per-CE RCA blocks using the existing read-only helper and the `RCA_CE_IDS`/`WEEK` printed by the builder.
7. Render through the existing delivery layer in dry-run mode:

```bash
python3 alert/post_message.py \
  --payload <payload-v2.json> \
  --rca-blocks <rca-blocks.json> \
  --dry-run
```

8. Inspect both parent messages and all CE threads. Only post live when the user explicitly requests it and confirms the destination.

The locked production handoff is available through the existing staged runner while V1 remains the default rollback path:

```bash
python3 scripts/weekly_report/run_weekly.py <market|all> \
  --week <YYYY-MM-DD> --stage alert --alert-version v2
```

Add `--post` only after the V2 report is live and the dry-run is approved. The V2 stage resolves approved BGMs, builds the current market-grain OKR sidecar, generates both parents, computes optional CE RCA, and hands the payload to the existing duplicate-guarded delivery layer.

Before an all-market dry run, run `python3 alert/v2/check_readiness.py`. Do not waive a missing BGM, channel, report route, or OKR market mapping; resolve the source configuration and rerun the gate.

## Fixed V2 shape

The current locked format version is `2026-08-17.1`. Changing the three KPI tables, compact linked OKRs, two-parent split, or CE-thread contract requires an explicit user decision and a format-version bump.

### Alert 1

- Tag every configured BGM for the market.
- Use three pipe-delimited tables. Revenue has one row and the columns Actual, vs LW, vs same week LY, and vs target. Overall has separate rows for Overall ROI, AOV, and Take rate, with Actual, vs LW, and vs same week LY. Paid has separate rows for Paid ROI, Paid clicks, and Paid CVR with the same three comparison columns; label its scope Google Search + Bing. Overall and Paid must not have a target column. Preserve the Paid ROI footnote explaining the report's calculated-CM fallback before Sep 2025 when applicable.
- Read restored metrics only from `headlines[].detail.metrics`: `roi1`, `paid_roi`, `aov`, `tr_pct`, `paid_clicks`, and `paid_cvr`; never recompute or substitute these values in the alert.
- Seven separate KPI rows across the three tables are an explicit market-alert exception to the generic pod weekly update's five-KPI ceiling. Do not replace the tables with a numbered list and do not group ROI or Paid funnel pairs.
- Show the four finalized market-level KRs from the same-week OKR sidecar.
- Hyperlink the `Selected OKRs` headline to `https://central-tracking.vercel.app/okr-tracker`. Keep each line to the short label, current result, reached count when available, target when available, and status. Do not repeat L92, prior-four-quarter, L4W projection, or exact-calendar methodology in the Slack copy; the linked tracker and retained sidecar detail carry that evidence.
- Link directly to that market's weekly report and to the Weekly Market Report feedback Canvas.
- Do not attach the V1 Losing Money or RPC Fluctuation tables.

### Alert 2

- Use `headlines[].movers.gains[:5]` and `headlines[].movers.drops[:5]`; do not rerank in the alert.
- Show each CE against last week, trailing four weeks, last year, and target.
- Create one `$rca` thread reference per unique CE, ordered Top 5 then Bottom 5.

## Failure rules

- Stop when a market has no configured BGM Slack IDs.
- Stop when the V2 headline lacks a current approved market target. For a CE with no approved target, display `No target` exactly as the V2 report does.
- Omit the optional OKR block if the read-only enrichment fails; never synthesize values. Reject a sidecar from a different report week.
- Never borrow V1 tables, greetings, or payload structure to fill a V2 gap.
- Never change V1 while implementing or repairing V2.
