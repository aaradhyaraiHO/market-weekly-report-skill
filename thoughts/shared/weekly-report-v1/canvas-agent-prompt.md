# Canvas agent prompt — Weekly Market Report recap + feedback triage

> Launch a fresh terminal session from `~/market-weekly-report-skill` (repo + Slack MCP available),
> paste everything below, then paste your meeting notes into the marked block at the end.

---

Create a Slack canvas that summarizes (a) the weekly-report/alert work shipped this cycle,
(b) feedback mined from each market's alert thread, and (c) the next TODOs — merging the
SHIPPED record below, the FEEDBACK you'll pull from Slack, and the MEETING NOTES I paste at the end.

## SHIPPED THIS CYCLE  (week W0 2026-07-13 → 07-19, live on market-notebook.vercel.app)
- Headout portfolio hero restyled to the monthly "Spotlight" dark palette; headout true-global
  report ($3.26M, 38 markets) wired into the Weekly Ledger.
- New "Eroding" lane in Losing Money — high-ROI CEs shedding CM2 vs their 4-wk avg (Vatican,
  Niagara, Kennedy Space Center…). Merged into the shared engine (buckets.py); now in BOTH the
  report §4 AND the GM Slack alert (weekly_alert.py was bleeders-only before — biggest gap vs the
  original bleeding-campaign-alert goal).
- Overall CVR switched to orders/clicks (dropped a 320GB Mixpanel-funnel path); 12-wk sparkline
  renders cheaply. CE-ID search live in the All-CE view.
- Google-Search CVR (cvr_g) repopulated across all 10 markets' Losing Money table (full BQ
  rebuild ×9 + a surgical conversions_g inject for SEA to dodge a 127GB cap). Deployed.
- Alerts: headout alert updated in #team-central-biz; all 10 market GM alerts updated IN PLACE
  (chat.update, no new posts) to match the deployed reports — verified report = alert on every
  market. "Blended ROI" renamed to "Paid ROI" (Search-only: Google+Bing search) per Varun.
- New alert tooling: posted_ledger.json, update_posts_weekly.py --slug, bucket_diff.py (report↔
  report verifier), run_market_alert_sweep.py (one-shot in-place update of all 10 GM channels).

## OPEN TODOs / DECISIONS (carry into next cycle)
1. Headout CVR still blank in the portfolio report — needs build_global.py rebuild + re-sweep
   #team-central-biz (heavy, ~69 markets).
2. Full-waste bug (shared engine): the gate trusts ad_conversions, NULL for composite city-suffixed
   CEs ("1043 - Paris", "1132 - Ho Chi Minh") in the GLOBAL query → falsely "0 conv / total loss"
   despite real paid_conversions + positive CM1 (Paris = 123% ROI, profitable). Manifests
   headout-only today (0 false-positives per-market). Fix in buckets.py: guard full-waste with
   conversion value / paid_conversions.
3. Fluctuation-bucket merge in progress → triggers one more render→publish→deploy→alert re-sweep.
4. Varun (exec) open question in #team-central-biz: "why show overall revenue + Paid ROI without
   showing overall ROI first?" — decide the headline-ROI framing for the overall alert.
5. Orchestrator: `weekly_market_report.py all` builds snapshots but skips per-market rendering
   (caused a stale-report deploy mid-cycle); make alert-sweep the final step sourced from the
   deployed report to prevent report↔alert drift.
6. Dashboards (Option A): OKR + Band Explorer + New CE clustered on central-tracking, cross-linked
   from the Ledger (separate workstream).

## HOW TO MINE FEEDBACK FROM THE ALERT THREADS
Each market's alert is two parent messages posted by the bot "Revenue/CVR Alerts" (user id
U07E15NCZNK): MSG1 = summary (blocks contain "Weekly Review"), MSG2 = movers ("Weekly Movers").
Feedback lives as human thread replies under those parents.

1. Channels: read alert/market_channels.json → markets{slug: channel_id}. Headout is
   #team-central-biz (C0975BGAX0B). Shortcut if present: /tmp/market_parents.json =
   {slug:{channel,msg1,msg2}}. Else rediscover: conversations.history newest-first, find the
   bot's latest messages whose blocks contain "Weekly Review" (MSG1) and "Weekly Movers" (MSG2).
2. For each channel read BOTH threads: slack_read_thread(channel_id, message_ts) for msg1_ts and
   msg2_ts (detailed, limit 200). Keep every reply whose author is NOT the bot (U07E15NCZNK).
   Capture author, text, timestamp, permalink.
3. Classify each human reply:
   - FEATURE / ASK (report or alert): wants something added/changed. Signals: "can we add / show /
     include / break down by / split by / filter", "would be useful to", "why don't we", "add a
     column for", "can this also cover". Tag scope = report | alert.
   - DATA / ACCURACY: questions a number or its definition ("is this ROI right?", "why Paid ROI
     not overall?", "does this include Bing?"). → clarify/verify items, not features.
   - ACK / DISCUSSION / OTHER: thanks, noted, investigating, chatter → exclude from TODOs (note
     recurring themes only).
4. Output per item: {market, author, quote, permalink, category (feature|data|ack), scope
   (report|alert|—), one-line so-what}. Roll FEATURE → "Next TODOs", DATA → "Open decisions".
   De-dupe asks repeated across markets (repeat = higher priority; note the count).
5. Unsure? Requests a change to what/how the report or alert shows → FEATURE. About whether a
   number is correct → DATA. Else → ACK.

## CANVAS FORMAT
Title: "Weekly Market Report — <week> Recap & Next Steps".
Sections: 1) What shipped (plain-English bullets), 2) Feedback by market (grouped by market/theme
from the Slack mining + my notes), 3) Next TODOs (prioritized: this-week vs later), 4) Open
decisions (owner + what's needed). Skimmable for a growth/GM audience — no code jargon in
customer-facing sections. Create via slack_create_canvas; ASK which channel/DM to attach to and
show a terminal draft for approval BEFORE creating.

## MY MEETING NOTES + PER-MARKET FEEDBACK
<paste transcript + feedback here>
