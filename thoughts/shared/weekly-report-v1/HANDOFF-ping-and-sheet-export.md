# HANDOFF — Thursday actions ping + Weekly Flagged sheet export (+ two-layer actions)

Written 2026-08-03, end of the losing-money worktree session. Losing Money v2 is BUILT and
committed on `worktree-losing-money` (see the commit for scope). This doc is the spec for the
NEXT session. Read `losing-money-blindspots.md` alongside; memory node `losing-money-redesign`
has the compressed state.

## Context you need (verified this session)

- **Actions store** = notes Sheet `config.NOTES_SHEET_ID` (1hC_IAsJ…), via Apps Script
  `config.NOTES_SCRIPT_URL`. Rows: `market_slug · ce_id · week_start · bucket · checkbox ·
  note · status · owner · updated`. Report dropdowns write through (`action_upsert`);
  `action_list?market=<slug>&week=<date>` reads one market-week.
- Week key is the REPORT week start. **Sun→Sat weeks since 2026-08-03** (config.WEEK_START_DAY);
  older rows sit under Monday keys — the template's prev-week pull already queries both −7d and
  −6d, and any new consumer must too (transition-era reads).
- Backfill DONE: 55 unique (market, CE) rows from perf's "Final Loosing money" tab live under
  week_start=2026-07-20, owner=`perf-sheet backfill`, note prefix `[perf-sheet wk 07-20]`.
  Mapping used: Skip/skip+review/to be reviewed/review→skip · tRoAS increase(+…)→roas_change ·
  −ve Seasonality→negative_seasonality · Pause&Review→pause_review · Paused→pause. Latam rows
  skipped (not a pilot). Backfill script: session scratchpad `backfill_actions.py` (temp dir —
  copy into scripts/ if it should survive).
- Perf's reference layout (their `Final Loosing money`, gid 1066981225): A CID · B name ·
  C category · D account/market · then per week (newest first) 8 cols Cost·Clicks·CPC·
  Conversion·CVR·CM1·ROI·CM2 × 4 weeks (E–AJ) · AK new_existing · AL tier · AM 2wk-neg ·
  AO ROI change · AP clicks WoW · AQ Actions Took · AR/AS perf comments · AT Final Actions ·
  AU GM Comments.
- Row payload available per flagged CE (buckets_final.defend.losing_money.existing/new):
  criteria, label, flag_streak, sort_delta, delta_wow, delta_3w, cm2_90d, weeks (W0..W3:
  cm2/cm1/spend/clicks/cvr/cm1conv/cpc/roi), driver(+drivers $), troas_l4w, troas_now,
  launch_date/days_since_launch (new), cm2_series, tier, new_existing.

## Task 1 — Thursday EOD Slack ping (meeting-committed, needed by Thu Aug 6)

New script in `alert/` (pattern-match `weekly_alert.py`: blocks, render_table, channel map,
GM tags). For each pilot market, for the current report week:
1. Pull `action_list` (current week key; during transition also the +1d/-1d variant if empty).
2. Join against the market's flagged set (losing_money existing+new from the deployed report
   snapshot — reuse bucket_diff's report-data extraction; publish dir has the HTMLs).
3. Post to the market channel (alert/market_channels.json):
   - Header "Losing Money — actions this week".
   - DESCENDING list of actioned CEs: CE · action · owner · comment (truncated).
   - Loud second section: flagged CEs with NO action or empty comment ("review these").
   - (Meeting nice-to-have: cases where the final action deviated from growth's input —
     needs the two-layer model below; ship v1 without it.)
4. Cron: Thursday EOD market-local-ish; simplest = one sweep Thursday evening IST alongside
   the existing Monday sweep runner (`run_market_alert_sweep.py` shows the loop pattern).
   GUARD: post only from main checkout (publish-only-from-main rule applies to alerts too).

## Task 2 — "Weekly Flagged" tab auto-export (kills perf's manual rebuild)

Into the SAME spreadsheet as the actions store (one file, two+ tabs — decided 2026-08-03):
- Tab per week or one rolling tab with a week column — prefer ONE tab, newest week on top,
  prior weeks retained (their sheet behaves like an archive; TTL concern already tracked in
  memory `sheet-archival-todo`).
- STRUCTURE MUST MATCH perf's current layout (Aaradhya, this session): identity cols, then
  4 weekly metric blocks side-by-side (Cost·Clicks·CPC·Conv·CVR·CM1·ROI·CM2, W0 first),
  new_existing, tier — then the v2 extras: criteria, flag_streak, sort_delta, tROAS
  (l4w / now), cm2_90d, launch (new CEs), driver — then action columns JOINED from the
  store (GM + perf layers once Task 3 lands; single layer until then).
- Write with `gws sheets spreadsheets values update` (CLI is authed; batch by market) or an
  Apps Script `flagged_upsert` endpoint. Runs as a publish-flow step — GUARD: never write
  the shared sheet from a worktree build; wire into `publish_weekly.py` (main checkout only).
- Source rows: the snapshot JSONs in `.cache/weekly_report/` or the deployed report-data.

## Task 3 — two-layer action model (GM vs perf) — design agreed to need, not yet decided

Problem (Aaradhya, screenshot 2026-08-03): one `status` per (week, CE, bucket), last write
wins — GM markings (Martis/Chloe rows) and perf actions overwrite each other; can't render
"growth said X, perf did Y" or the Thursday "deviations" section.
Cheapest design (no Apps Script schema change): second bucket key `losing_money_perf` for the
perf/final layer; report renders both lines in the Action cell (GM dropdown writes
`losing_money`, a perf-role selector writes `losing_money_perf`); Thursday ping diffs the two.
Alternative: add a `role` column to the store (Apps Script + sheet migration). Decide with
Aaradhya before building. Chip semantics already softened ("no action on record", amber,
either-layer check should apply once two layers exist).

## Also open (not this session's scope)

- Own-target ROI gate for the soft band (blindspots #2) — WAITING ON ADI, 3-line change.
- C4-for-Existing — parked, contradicts meeting decision, needs Adi.
- Blindspots #6–#13 (sub-$50 spend mislabel, seasonality nudge, global build untested with
  v2 schema — run `build_global` once before publishing headout, author-name prompt TODO).
- Dormant CE list + ROI-bucket tracker (meeting next-steps, separate workstream).

## How to verify anything here

- Cross-checker: scratchpad `lm_crosscheck.py <snapshot.json>` (independent criteria
  re-implementation; validated Italy/NA/Oceania + the Sun–Sat week clean).
- Build: `python3 scripts/weekly_report/weekly_market_report.py italy --no-open`
  (defaults to the latest complete Sun–Sat week). Preview via local http server, NOT file://.
- Publish/deploy/Sheet-writes: ONLY from the main checkout (memory `publish-only-from-main`).
