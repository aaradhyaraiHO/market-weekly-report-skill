---
date: 2026-07-17
repo: ~/market-weekly-report-skill
topic: "Weekly Market Report — resume state (skill + weekly ledger shipped; open threads)"
main_head: d1411a0
status: shipped-v1, iterating
---

# Weekly Market Report — Resume State (2026-07-17)

## Where things are
- **main head `d1411a0`**, working tree clean. Everything below is MERGED into main.
- **Live**: https://market-notebook.vercel.app (auth-gated @headout.com). `/` = monthly card grid;
  `/weekly` = **trajectory matrix** (NA / Italy / Oceania × trailing 6 weeks). Monthly⇄Weekly toggle
  both ways. Deploy is **file-based**: `vercel deploy --prod --cwd market-notebook-v2` (from ~/analytics, USER runs).

## Pipeline (all in scripts/weekly_report/)
`weekly_market_report.py <market|all> --week YYYY-MM-DD [--no-open]` → `build_snapshot.py` (producer,
BQ) → snapshot JSON in `.cache/weekly_report/snapshot_{slug}_{week}.json` → `render.py` → HTML in
`thoughts/shared/weekly-report-v1/report_{slug}_{week}.html`. Reference week in use: **2026-07-06**.
config.MARKETS = north_america, italy, oceania (3 pilots).

## Report sections (report_template.html)
- §1 headlines + **trend movers**: DROPS take precedence, GAINS exclude material WoW drops
  (`flows.py`: drop if 4wk<0 OR raw<−$500 `WOW_DROP_FLOOR`; gain only if not drop & up on either;
  mutually exclusive, 0 overlap). Display leads with the directional lens.
- §2 **{Market} Digest** (collapsible Show/Hide): Follow-up table + Market Review = Slack-signal
  briefing (grouped Risk/Tailwind/Context, `.chip` tags, so-what + metric + REAL permalink) + GM narrative.
- §3 All-CE table (banded, per-metric expand, sticky TOTAL + opaque sticky headers) + CE drawer
  (vitals/funnel/Shapley/RE-SOURCE/**GM note**/**Slack context**).
- §4 Defend/Compound/Lifecycle buckets. **Losing Money redesigned** (buckets.py, cm2Spark).
  **Scale-Up table HIDDEN** (engine still computes C.scale_up; re-add one `_bucketBlock` line to restore).
- §5 seasonality (`seasonality_llm.py`, heuristic default) · §6 **Prepurchase** (see below).

## Slack digest — reproducible sidecar (S3 agent step)
Write `.cache/weekly_report/slack_context_{slug}_{week}.json` (list of cards); build_snapshot
auto-loads into `market_review_context`. Card schema: `{group, ce, tag, tag_kind, channel, date,
so_what, body, metric, metric_kind, link, scope:'market'|'ce', ce_id}`.
- scope='market' (or omitted) → §2 grouped digest. scope='ce' + ce_id (must == a ces[].ce_id) → routes
  into that CE's drawer "Slack context" section.
- **NA (07-06)**: 10 cards written w/ real permalinks; 4 routed to drawers (Kennedy 3111, Boston Whale
  6105, Edge NYC 4012, USH 2174), 6 kept in §2 (multi-CE / market-wide). Italy (9 cards) + Oceania
  (8 cards) digests written (all market-scoped). Channels: NA CNSHDD2H1; italy C045L2WQ79P; oceania
  CHKRLFDPU/C039TMH0GEP/C097DVBLHGS; globals #tf-bugalert C038T64PD, #pod-live-entertainment C042A57T52Q.
- Permalink form: `.../archives/{CH}/p{ts_nodot}?thread_ts={ts}&cid={CH}` (get ts from detailed read /
  slack_search_public — never fabricate). Notes/digest sync only over http(s), not file:// (CORS).

## Prepurchase §6c (fully current)
Sourced from **fct_pp_tickets** (per-ticket "FDT"), NOT dim_pp_allotments. Net ROI = (CM1 − realized
loss of tickets expiring unsold this month)/cost — corrected (NA 22–171%, sane). Fields: str_nt, dated,
remaining_dated, expiring_unsold, loss_liab_dated, expiring_loss, net_roi, sold_last_wk, cvr, cvr_wow.

## Hosting engine
`scripts/weekly_report/publish_weekly.py <market|all> --week` → matrix into ~/analytics/market-notebook-v2/
(weekly.html + weekly-report-{slug}.html + weekly_state.json). Monthly toggle lives in
~/market-monthly-review-skill/engine/publish_ledger.py `render_index()` (committed 8029f4d, unpushed);
may-2026.html archive patched directly. `_bucketFamColor`/matrix cells: rev + WoW%, region-grouped.

## Skipped commits (leave skipped)
- `worktree-SLACK` 6e32b04 — stale old-base (e0fe3cb) original of Slack routing; superseded by the
  merged slack-port 5e2da6d.
- `worktree-all-ce-view` 082bfa1 — paid-metrics→ads_campaign_stats already in main.

## OPEN THREADS / TODOs
1. **Deploy pending**: live site still shows PRE-merge Italy/Oceania + pre-movers-fix reports. To go
   live with everything: regenerate NA/Italy/Oceania (~12 min BQ) → publish_weekly all → vercel deploy.
   Also ships the may-2026 toggle fix. (NA is already regenerated locally with all merges.)
2. **Fan out 7 more markets**: add to config.MARKETS (france, united_kingdom, iberia, csee, east_asia,
   sea, uae — business_market strings verified) → generate → S3 digest → publish_weekly. Matrix rows +
   MARKET_META in publish_weekly already wired for all 10.
3. **Rethink Follow-up (§2) from the ground up** — feed it the GM weekly notes (notes.py
   notes_for_report/open_notes, not yet wired) → "you noted X last week — did it resolve?" loop.
4. **Roll out "How to read" strips** to buckets/§6 lacking them (match .lm-howto pattern). NO tabs.
5. **Upgrade "hover for names"** (Losing Money burn footer, line ~1643, native title tooltip) → click-to-expand.
6. **Push** the monthly-skill toggle commit (8029f4d) to GitHub if wanted (convention: local, no push).
7. Cohort-bar empty middle — "$-at-stake" fill idea, parked.

## Plan file
~/.claude/plans/sunny-spinning-robin.md (10-market + ledger plan; has several of these TODOs).
