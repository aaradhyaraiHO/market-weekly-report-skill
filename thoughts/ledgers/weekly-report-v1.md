> ## ▶ HOW TO RESUME (read first)
> 1. Open a terminal and: `cd ~/analytics/.claude/worktrees/wt-weekly-buckets`
> 2. Launch Claude there (`claude`). The SessionStart hook auto-loads THIS ledger.
> 3. Run: `/implement_plan thoughts/shared/plans/2026-07-10-weekly-report-remaining-phases.md`
>    → it reads the plan + this ledger, sees P1 checked, and executes the next `[→]` phase (agent-orchestrated, committing + updating this ledger as it goes).
> **MUST launch from the wt-weekly-buckets worktree** (the ledger/plan/handoffs live on its branch — not on main). Requires BigQuery ADC auth. Local commits only, NO push.
> Current position: P1+P2+P3 DONE · `[→] Phase 4` (daily TR/price columns). Handoffs: `thoughts/handoffs/weekly-report-v1/`.

# Ledger — Weekly Market Report V1 (wt-weekly-data + drawers/customization)

Updated 2026-07-09. Session built the data mart, the fluctuation engine, Section-1
market drawer (data+render), and mocked the CE deep-dive drawer + All-CE BGM
customization. Master plan: `thoughts/shared/plans/2026-07-09-weekly-report-v1.md`.

## Goal
Ship Weekly Market Report V1 (last 12 weeks, weekly, pilot markets NA/Italy/Oceania).
wt-weekly-data owns the mart (meta, market_summary, ces, followup, bucket1) + the
Section-1 drawer data. Render lives in wt-weekly-report.

## Key decisions (locked)
- **Revenue = `sum_revenue_predicted`** (analytics-skill canon), NOT actuals. AOV = GBV/orders.
  TR/CVR/CM1 = canon. See memory `weekly-report-revenue-basis.md`.
- Fluctuation engine (Bucket 1) = POF gates (CM1/conv & RPC) + CVR>30% WoW + bid-change
  check. Validation gate: NA wk 2026-06-29 → **5 CM1/conv up-swings, 0 CV-excluded** (PASS).
  Key: 3-day *smoothed* persistence ≥0.20 reproduced the exact 5.
- WoW Shapley = exact 5-factor (Clicks×CVR×AOV×CR×TR), reconstructs ΔRevenue. Market + per-CE.
- LY series (−364d) for the 6 comparable metrics (rev/gbv/cr/tr/roi1/paid_clicks);
  offline-paid (Paid RoI / Conv Value / CVR) have NO LY (pre-2025-09-01 gap).
- BGM customization = **client-side localStorage layer** over flat ces[] (no mart change):
  saved views, custom groups (group-by "My groups"), watchlist + highlight rules.
- CE drawer design = SAME component as market drawer (metric table + TY/LY sparkline +
  Shapley + comments); richer channels/funnel/tgids/leadtime/countries = deferred "RE-SOURCE" tier.

## Information architecture (LOCKED 2026-07-09)
Rule: **Table (outside) = collective / find-and-triage** · **Drawer (inside) = single-CE / decide-and-act.**
- TABLE: group-by (+ collapse + subtotals + contribution strip), search/sort/filter chips, saved views,
  custom-group *creation*, highlight rules, per-row scorecard + TY/LY sparkline, **watchlist ★ indicator + "watchlist only" filter**.
- DRAWER: full metric table (W0/W-1/Δ + TY/LY + hover), WoW Shapley, auto-diagnosis + flag+action + cohort benchmark (smart top-3),
  channels/funnel/tgids/leadtime/countries (RE-SOURCE tier), notes, **watchlist star MIRROR**.
- **Star/watchlist decision: ROW-PRIMARY** (one-click flag during scan; payoff = the table "watchlist only" filter),
  **+ drawer mirror** (same state, second entry point). Would only flip to drawer-primary if starring triggers a workflow (e.g. intervention tracker).

## Consolidation gap (the big next task)
The real `report_template.html` has: market drawer ✓, BGM customization ✓ (committed 07d25469). **MISSING from the real build**
(exists only in mockups): collapse-groups, contribution strip, diagnostic-bucket group-by, CPC column, per-row TY/LY sparklines,
and the **entire CE deep-dive drawer** (`ce_drawer_complete_mockup.html` spec: metric table + TY/LY + Shapley + notes + row-mirrored star).
NEXT SESSION = one **consolidation pass**: wire all mockup features into the real template, organized by the IA above, so the
final build matches the mockups. Big, well-specified render build — do fresh, use agents.

## State
- Done (committed, branch `worktree-wt-weekly-data`):
  - [x] 240d2637 mart + fluctuation engine
  - [x] e8f7a6ea meta.market_slug
  - [x] 55fa2366 Section-1 drawer data (9 key_metrics, market shapley_wow, market weekly_ly)
  - [x] d425ba97 CPC + per-CE revenue_ly + tier cleanup (Unclassified)
  - [x] dcff0bf2 per-CE shapley_wow
  - [x] f8ce21d1 per-CE weekly_ly (6 metrics)
  - [x] e79fce13 A1 RE-SOURCE (mart half): ces[].tgids | .leadtime | .countries — W0-week composition tables (fct_orders + fct_bookings, actuals basis, one market batch query each, split per CE). NA --validate PASS; 578 CEs, ~28% populated, long-tail → []. Matches ce_drawer_complete contract.
  - [x] b047417f A2 RE-SOURCE (mart half): ces[].channels | .funnel — channel mix (fct_orders v6.1 channel CASE) + LP→order funnel (mixpanel_user_page_funnel_progression, batched on CE-id list). Both carry W0/W-1/LY → current+WoW+YoY. channels ~28%, funnel ~61% populated. **CE-drawer DATA contract now COMPLETE per ce_drawer_complete mockup (7 blocks: 2 LIVE + 5 RE-SOURCE).**
- Done (committed, branch `worktree-wt-weekly-report`):
  - [x] e8d46d53 market-headline drawer render (9 metrics + TY/LY sparklines + Shapley + pacing placeholders)
  - [x] 07d25469 BGM customization on All-CE view (saved views, custom groups/"★ My groups", watchlist stars + filter, highlight rules)
- Done (committed, render branch, cont'd):
  - [x] 636563a6 consolidation pass (CE drawer LIVE tier + table smarts: collapse, contribution strip, diagnostic group-by, CPC, per-row TY/LY sparkline)
  - [x] f69601d5 FIX: collapse-groups (ceGroup handler → renderApp so button not disabled) + CE drawer not rendering (set .open/.wide BEFORE wiring + try/catch). jsdom 33/33.
- Done (render, wt-weekly-report):
  - [x] d211d6cc A1+A2 RENDER: wired all 5 RE-SOURCE tables (channel mix / funnel / tgids / leadtime / countries) into `openDrawer` between Shapley and Notes via resourceBlocks(). Each section renders only when data present (degrade). Verified: full app node --check clean + resourceBlocks vs real NA snapshot → 5 tables for High Roller (2094), no NaN, empty CE → empty. **CE deep-dive drawer now COMPLETE end-to-end per mockup.**
  - [x] metadata fix (mart d3710c72): group-by dims clean (Unknown/Uncategorized labels + new_vs_existing NULL→'Unknown' bug). Render needs no change — groups on values directly.
- Now: [→] CHECKPOINT — safe to /clear. Current NA build to open: `wt-weekly-report/thoughts/shared/weekly-report-v1/report_NA_2026-06-29_fresh.html` (post drawer-wiring + metadata fix, single market).
- Remaining for full V1: §5 seasonality + §6 levers engines (sibling worktrees wt-seasonality / wt-levers-tables); smart deep-dive top-3 (auto-diagnosis / B1 flag / cohort benchmark); goals join (MTD/target); multi-market rollout (Italy/Oceania) + merge to main (local, no push).

## BUCKET FRAMEWORK BUILD (active — started 2026-07-10)
**Why:** audit vs locked spec (`thoughts/shared/market-report-weekly-v1-spec.md`) found only **B2** is built (as `bucket1_fluctuations`); the spec's flow buckets **B1/B3/B4/B5 + header flows/themes + overlays** are unbuilt. What we polished (all-CE table + CE drawer) is the spec's "§5 store/drill-down" surface, not the §2 bucket narrative.

**LOCKED decisions (2026-07-10):**
- **Data path = A: extend the Python pipeline** (`scripts/weekly_report/`), NOT re-platform to dbt. Key: **import `scripts/ce_buckets/` constants + classify.py** into the pipeline → cross-cadence consistency (same truth-table/thresholds as monthly) without the dbt rebuild. dbt fact layer deferred to a later hardening pass. (dbt `ce_weekly_buckets` exists but is stock-semantics + unwired — do NOT use as-is.)
- **Hosting = centralized** on `market-notebook.vercel.app` (the monthly notebook). Add a **`/weekly/[market]/[week]` route serving the self-contained HTML** (static asset/route), NOT a native shadcn rebuild yet. One home, one link, ledger points there. Native-component convergence = later pass. Weekly producer writes output into the notebook repo (need repo path from user).
- **Isolation:** build buckets in a **fresh worktree `wt-weekly-buckets`** (branched from `worktree-wt-weekly-data` HEAD so it has A1/A2/numerators/metadata-fix) to avoid colliding with the other session in `wt-weekly-data`. Merge back when done. Local commits only, NO push.

**Fork sources:** `scripts/ce_buckets/classify.py` (B1 truth-table: ROI_PAUSE_FLOOR=20, ROI_TRANSITION_FLOOR=70, ROI floor=100, CHRONIC, RPC_CLIFF=−0.25), monthly `market-report-buckets-v3-brief.md`. Built B2 engine = `alerts.py`. Transitions raw material = snapshot `transitions[]`.

**Phased plan (spec §10 adapted):**
- [x] **B1 ROI/CM2 Movement** — DONE (commit 28821ff1, worktree wt-weekly-buckets). `bucket_b1.py` imports ce_buckets constants; weekly truth-table + movement flags (NEW/CLIFF/ESCALATION/EXIT) + Monitor/Cliff (gap#18) + CM2-bleed ranking + action. NA: 9 CLIFF/1 NEW/1 ESC/16 EXIT, 19 standing. --validate PASS. TODO later: EXIT sustained-2wk hysteresis (currently single-week); tROAS target = spend-weighted current (fallback 145%).
- [x] **B2 column completion** — DONE (commit 1a78d8a9). alerts.py adds cause_tag (input-induced/supply-linked/unexplained/up-swing innocence routing), swing_driver (top Shapley factor+share), daily CM1/conv spark+28d baseline. NA: 10 unexplained/10 input-induced/5 up-swing. DEFERRED (need new daily sources): TR-vs-pre-change, price/guest Δ, gray-zone counter, known-cause writeback (render-side).
- [x] **Header flows/themes** — DONE (commit ab1801b1). flows.py → headlines.week_header: structural WoW (centered LY ratio ±100% cap, $200 guard), G/L + N80, 5 week-types, dual-clock, theme attribution (index≥1.5× AND ≥3 CEs AND ≥$2K floor + concentration demotion), routing. Reproduces spec §11 backtest (UNDER-RAMPING; Cruises-Chicago/Immersive/Kennedy; Cruises-Sightseeing theme). LY fetch extended +7d for LY[t+1]. TODO later: week-type 52w-percentile calibration (V1 uses $ floor); masking per-group classifier.
- [x] **B3 Losing Ground** — DONE (commit f90bd1fa). bucket_b3.py imports bands.py; Pro+ + recent-4wk RR ≥1 band below established + ≥2wk on pace; reason cascade (dormant/inputs/paid-opt/manual); ranked by projected monthly loss. NA: 3 rows. APPROX: weekly-RR pace vs spec's MTD daily-shape (note in file). TODO: 🍂 seasonal tag (events registry), band-sheet reconcile.
- [x] **B4 Scale Windows** — DONE (commit 8b8aaf5c). bucket_b4.py: 3 lanes (sticky/⚡NEW WAVE+Louvre guard/🔄LOADING), gain floor, zero-spend flip, est-incremental ranking. flows.per_ce_structural shared. NA: 2 NEW WAVE + 8 LOADING + 0 sticky (reproduces spec gap#16 — tROAS-raise suppresses lane-a). TODO: SIS/supply gates (deferred pull → noted not blocked), RPC-upside sizing for LOADING.
- [ ] **B5 Action Verdicts**: needs tracker infra (deferred). Overlays: OV1 Top-CEs strip, OV2 Gap/Pacing (needs revenue_goals).
- **NEXT after buckets: RENDER** B1–B4 + header into the report (§4 becomes the bucket narrative) + per-bucket action lines + usability check, then Vercel host. All bucket DATA now lands in snapshot: bucket_b1/bucket_b3/bucket_b4 + headlines.week_header + bucket1_fluctuations(B2). B5 + overlays deferred (tracker/goals).
- [ ] **Render** each bucket + per-bucket **action line**; **usability check**; then **Vercel host** under market-notebook + ledger link.

## NEXT (parked): productize as a skill — mirror `market-monthly-review`
**Prerequisite (USER does manually):** merge worktree-wt-weekly-data + worktree-wt-weekly-report into main (local, NO push) so mart + renderer land together in `~/analytics/scripts/weekly_report/`. THEN I scaffold the skill.
Reference to mirror: `~/growth-reviews/.claude/skills/market-monthly-review/` (thin package: SKILL.md + plugin.json; scripts in ~/analytics/scripts/; workflow does `cd ~/analytics && python3 scripts/...`).
Scaffold to build:
  - `.claude/skills/market-weekly-report/SKILL.md` — frontmatter name+trigger-rich description; Audience; Dependencies (Python≥3.9, google-cloud-bigquery+pandas, BQ ADC, EU); Usage `/market-weekly-report <market> [<week-Monday>]`; lean numbered Workflow (S1 resolve market+week [default config.latest_complete_week()] → S2 run orchestrator → S3 QA/open). NO Slack-injection/perf-audit/placeholder steps (weekly HTML is self-contained; unlike monthly).
  - `plugin.json` — name market-weekly-report, main SKILL.md, context_files → scripts/weekly_report/*, deps, settings.
  - `scripts/weekly_report/weekly_market_report.py` — ONE orchestrator: resolve default week, run build_snapshot per market, then render.py (single or multi-market tabbed), print/open HTML path. (render.py already handles multi-input tabbing + --out default + --open.)
Open decisions to confirm at scaffold time (interview was interrupted): (a) Slack draft ping? — lean toward HTML-only for V1; (b) hosting/share link (S3 presign / Drive domain-gated)? — lean local-file+open for V1. §5/§6 already degrade gracefully when absent.
Out of scope for the skill build: the Phase-D Airflow weekly cron (separate).
- **"FULL drawer" remaining = the RE-SOURCE tier** (Channels / Funnel LP→order / TGIDs / Lead-time / Countries). NOT a render fix — needs MART work: fct_bookings fetches (tgids/leadtime/countries, easy) + port CE-Health session-funnel query to weekly (channels/funnel, heavier). CE-Health drawer.json (`~/analytics/.cache/ce-health-drawers/2026-06/<ce_id>/`) + skill `~/.claude/skills/availability-audit-v12`/ce-health run_diagnostic.py have the canonical queries to port. Spec = ce_drawer_complete_mockup.html.
- Next / backlog (see `thoughts/shared/weekly-report-v1/smart-backlog-notes.md`):
  - [ ] CONSOLIDATION PASS: wire all mockup features into report_template.html per the IA (collapse-groups, contribution strip, diagnostic-bucket group-by, CPC col, per-row TY/LY sparklines, + the full CE deep-dive drawer w/ row-mirrored star)
  - [ ] Smart deep-dive top-3: auto-diagnosis headline · inline B1 flag+recommendation · cohort benchmark + targets
  - [ ] RE-SOURCE drawer tier: TGIDs/lead-time/countries (fct_bookings fetch) + channels/funnel/landing (port CE-Health session-funnel query to weekly)
  - [ ] Contribution-index column into Section 3 group-by (parked from themes idea)
  - [ ] Goals join → MTD + target attainment (drawer/§1 placeholders) — waits on revenue_goals
  - [ ] Availability signal refactor (strict sold-out → relative scarcity; see earlier diag)
  - [ ] Integration: merge worktree branches → main (plan step 4), local only, NO push

## Working set
- Mart code: `scripts/weekly_report/{config,bq,fetch,alerts,shapley,build_snapshot}.py` (scripts/ is git-excluded → `git add -f`).
- Build/validate: `cd scripts/weekly_report && python3 build_snapshot.py --market north_america --week 2026-06-29 --validate` (must print RESULT: PASS).
- Snapshots: `.cache/weekly_report/snapshot_{market}_2026-06-29.json` (gitignored).
- Mockups (thoughts/, gitignored): mockups/ = section1 (3), ce_drawer_rich_3b, ce_drawer_complete (full), section3_allce_smart, allce_bgm_customization.
- Render worktree: `../wt-weekly-report/scripts/weekly_report/{render.py,template/report_template.html}`.
- Commit rule: local only, NO push. scripts/ excluded → `git add -f` in wt-weekly-data (tracked in wt-weekly-report).

## Open questions
- BGM customization: local-per-browser (V1) vs shared team store (Phase-2 backend)?
- CE drawer: build the RE-SOURCE tier (channels/funnel) or ship table+Shapley+comments first?
- Section 3 group-first collapsible + contribution strip: is it in the real template yet, or only mocked? (agent report will clarify)

## CONSOLIDATION STATE (2026-07-10)
**`wt-weekly-buckets` is now the single DATA-layer worktree** — holds everything:
A1/A2 (tgids/leadtime/countries/channels/funnel + numerators + metadata fix) · B1-B4 buckets · header flows/themes · B2 columns · §5 seasonality · §6 levers · no-bid (ported from wt-weekly-data session, commit 6fad79cd — that session authored §5/§6; it should now STOP editing §5/§6 to avoid a diverging duplicate).
- **`wt-weekly-report`** = render template (week header + B1-B4 + §5/§6 + all-CE + drawers).
- Merge picture: only `build_snapshot.py` was edited by both data sessions (bucket wiring + §5/§6 wiring) — both additive; one small hand-merge at final consolidation to main. All other files are new/additive or identical.
- Current full render: `wt-weekly-report/thoughts/shared/weekly-report-v1/report_NA_full_2026-06-29.html`.

## RENDER FOLDED IN (2026-07-10, commit 3d57b0c9)
`wt-weekly-buckets` now runs the FULL pipeline end-to-end (build_snapshot → render → HTML) — render.py + template/report_template.html + make_sample_data.py ported from the wt-weekly-report session. Single command chain, no cross-worktree hop:
```
cd scripts/weekly_report
python3 build_snapshot.py --market north_america --week 2026-06-29 [--validate]
python3 render.py ../../.cache/weekly_report/snapshot_north_america_2026-06-29.json
```
Output → `thoughts/shared/weekly-report-v1/report_north_america_2026-06-29.html`.
**wt-weekly-buckets = the single home for the whole weekly report (data + render).** wt-weekly-data (§5/§6) and wt-weekly-report (template) should stop editing to avoid divergence; both are now superseded here. Final step remains: merge wt-weekly-buckets → main (local, no push) — one small build_snapshot.py hand-merge vs the other data session if it committed separately.

## CROSS-BUCKET CASCADE — DONE (2026-07-10)
Data (ecc27ae2) + render (ee1bac09) in wt-weekly-buckets. `_apply_cascade` in build_snapshot: one home per CE (B1>B2>B3>B4), `also_in` chips, hard-cap-10 problems by $ at stake (B1 protected), B1 EXITs → wins line, `in_store` count for overflow. Emits `bucket_cascade`. **B1 spend gate raised to $1k/4w** (was $50) — cut trivial cliffs 27→11 so material B2 swings get cap room. renderBuckets renders home-only rows + chips + wins + "+N in store". NA: 4 B1 + 6 B2 rendered · 7 recovered · 24 in-store. --validate PASS.

## NEXT (fresh session): SKILL for multi-market Monday runs
User goal: "build cascade first, then skill it right so we can run multi-market for Monday."
- Mirror `~/growth-reviews/.claude/skills/market-monthly-review/` (thin SKILL.md + plugin.json; orchestrator does the work).
- Build `.claude/skills/market-weekly-report/` (SKILL.md + plugin.json) + a `weekly_market_report.py` orchestrator that chains build_snapshot → render for ONE or MANY markets (config.MARKETS = north_america, italy, oceania), default week = config.latest_complete_week(), multi-market = pass all snapshots to render.py (already supports tabbed multi-market).
- Usage: `/market-weekly-report <market|all> [<week-Monday>]`.
- Pipeline lives entirely in wt-weekly-buckets/scripts/weekly_report/ now (data + render together).
- Decisions still open (from earlier interrupted interview): Slack draft ping? (lean HTML-only V1) · hosting on market-notebook.vercel.app /weekly route (need repo path — user has it). Deferred: B5/pacing/groups (blocked), remaining audit columns (see bucket-logic-gap-audit.md).
- Multi-market note: engine is market-agnostic; Italy/Oceania = just run build_snapshot per slug then one render. VERIFY each market --validate + spot-check before Monday.

## MASTER SEQUENCE (frozen 2026-07-10)
All remaining work phased in `thoughts/shared/plans/2026-07-10-weekly-report-remaining-phases.md`:
P1 skill+multi-market Monday (incl. 52w-percentile week-type + Slack digest as skill step) → P2 cheap columns (zero-spend flag, burn line, gray-zone, tROAS action-register table) → P3 sparklines → P4 daily TR/price columns → P5 blocked items (B5/pacing/groups — unlock deps one-by-one) → P6 merge+Vercel. One phase per fresh session.
- [x] **P1 DONE** (2026-07-10, commits a94eea46 orchestrator+52w-calibration+fetch, 4d735232 skill package). `weekly_market_report.py <market|all> [--week] [--no-open] [--validate]` chains build_snapshot per slug → one render.py → single tabbed HTML. Week-type "large" threshold now p75 of trailing-52w |WoW-Δ| (NA $47,808 · Italy $35,982 · Oceania $12,659; falls back to $-floor <20wk). Skill `.claude/skills/market-weekly-report/` (SKILL.md + plugin.json, Slack digest = S3 agent step). `all --week 2026-06-29 --validate`: **NA RESULT: PASS** (5/5 CM1/conv up-swings, 0 CV-excl); Italy+Oceania built clean; one HTML `report_multi_2026-06-29.html` (15.8MB). 3-market: NA rev $580K/581 CEs/B1 12·B3 3·B4 11 · Italy $327K/835/B1 11·B3 10·B4 5 · Oceania $126K/516/B1 11·B3 4·B4 16 — all week_header+calibration+cascade present.
- [x] **P2 DONE** (2026-07-10, commit 5ae79715). Four cheap correctness columns, producer + render, NA --validate PASS. **P2.1** zero-spend transition flag → `bucket_b1.zero_spend_exits` + amber B1 line (NA: 4, incl. both Madame Tussauds — the exact hole the plan named). **P2.2** long-tail burn line → `bucket_b1.burn_line {count, bleed_wk_total}` + B1 summary line (NA: 16 CEs · -$1,610/wk). **P2.3** gray-zone → `bucket_b1.gray_zone {near_floor/transition/critical}` (NA 5/1/1) + `_diagnostics.cvr_gray_zone_count` for B2 (NA: 6, CVR drop within 5pp of the 30% trigger) → "Near triggers:" lines in B1+B2. **P2.4** tROAS action-register — BUILT then DROPPED (commit 17aaea84, user call): redundant with B2, which already tags these CEs `input-induced` and prints the tROAS change in its recommendation ("tROAS 150→165 2026-06-23"), plus §6(b) no-bid/tROAS-NULL table. Removed render block + producer wiring + `alerts.build_action_register`. `config.GRAY_ZONE_PP` added. **API CHANGE:** `bucket_b1.build_bucket_b1` now returns a dict (was `(rows, standing)`); build_snapshot updated. renderBuckets verified end-to-end vs real NA payload (6/6). Render: `report_north_america_2026-06-29.html`. DEFERRED (Phase 4, need daily sources): B1/B2 TR-vs-pre-change + price/guest Δ. Action-register PPC-restrictions/holiday tabs deferred (need sheet IDs).
- [x] **P3 DONE** (2026-07-10, commit 1de214ba). Per-bucket sparklines: B1 RPC 8w (cliff vs gradual visual), B3 revenue TY/LY 10w+4 forward LY (grey dashed extends 4wk beyond TY end), B4 revenue 10w. LY fetch extended +7d→+28d for B3 forward weeks. Producer enriches rows after bucket build; render uses existing sparkline()/kmSparkline() helpers. All 3 markets --validate PASS.
- [→] Now: **Phase 4** — daily-source diagnosis columns (TR-vs-pre-change, price/guest Δ on B1/B2, B3 TR-4w-YoY). Needs new daily fetches.

## DECISION: market-weekly-report vs market-weekly-review (2026-07-10)
COEXIST — they do different jobs, keep both (do NOT rename/merge):
- `market-weekly-review` (V5, growth-reviews) = CE-level decision-tree action brief + cross-CE patterns + auto perf-audit → markdown.
- `market-weekly-report` (NEW, this build) = bucket-framework flow report (B1–B4 + week header + drawers) → self-contained tabbed HTML.
Descriptions already differentiate (RCA brief vs bucket HTML). Naming closeness accepted.
