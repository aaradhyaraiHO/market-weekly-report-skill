# Spec — Store-backed Perf layer (durable, CE-keyed, multi-week)

Status: proposed 2026-08-09, for Aaradhya + Adi (perf) sign-off before build.
Repo: `~/market-weekly-report-skill`. Owner surfaces: `scripts/weekly_report/export_perf_sheet.py`,
the Apps Script behind `config.NOTES_SCRIPT_URL`, store sheet `1hC…`, perf sheet `1sXd…`.

## Problem
GM actions/comments live in the **store** (`1hC`, Apps Script), keyed by `(market, ce_id,
week)` — durable, all-weeks, drift-proof. **Perf finals live only in the perf sheet** (`1sXd`,
`w/c <week>` tab), addressed by **row position**, single-week. That asymmetry causes: (1) drift
whenever the export re-sorts (perf cells slide off their CE); (2) no history past one tab;
(3) no prior-week reflection for perf; (4) GM and perf collide in the store's single `status`/
`note` field. Goal: give perf finals the same store home GM has, and render the sheet from it.

## 1. Store schema — extend the action record with a PERF layer
Current record (actions tab): `market_slug, ce_id, week_start, bucket, checkbox, note, status,
owner, updated`. `status`/`note` are GM's; `note` is the combined `growth:\nperf:` string.

Add perf-owned fields to the SAME record (one row per market×ce×week×bucket):
- `final_action`   — perf's final decision (canonical vocab: skip / pause / pause_review /
  roas_change / negative_seasonality / scale_down / tROAS_movement / no_change …)
- `perf_comment`   — perf's rationale (replaces the ad-hoc `perf:` line in `note`)
- `perf_owner`, `perf_updated`

GM keeps writing `status` + `note` (growth line); perf writes `final_action` + `perf_comment`.
**No collision** — separate fields. `updated`/`perf_updated` track each side independently.

New / changed Apps Script endpoints:
- `perf_upsert` — `?action=perf_upsert&market_slug=&ce_id=&week_start=&bucket=losing_money
  &final_action=&perf_comment=&perf_owner=` → writes only the perf fields of that record
  (creates the row if GM hasn't; never touches GM's `status`/`note`).
- `action_list` — already returns the record; include `final_action, perf_comment, perf_owner,
  perf_updated`. This is what makes multi-week history queryable.

## 2. Sheet ↔ store sync (each export run, both directions)
The export becomes a **merge point**. Every run (publish + the 3×/day cron):
1. **Sheet → store (capture perf input):** read perf's typed cells from the `w/c <week>` tab by
   **CID** (Final action, Perf comment columns) → `perf_upsert` each into the store for `(ce_id,
   week)`. This persists whatever perf typed since the last run into the durable record.
2. **Store → sheet (render):** rebuild the tab from the store — GM cols (as today) + perf cols
   (`final_action`, `perf_comment` round-tripped) + prev-week cols (§3), CID-keyed, stable order.

Conflict rule: sheet is where perf types, so **sheet wins** on the current week (upsert). The
store is the surviving record. Concurrency (perf editing mid-run) is last-write-wins per cell,
but because it's CID-keyed the write always lands on the right CE — no drift regardless of timing.

## 3. Prior-week reflection (answers "was it flagged last wk + what was done")
For each flagged CE this week, the export queries the store for that `ce_id`'s prior weeks and
writes:
- `Flagged last wk?` (Y/N — from `flag_streak`/store presence)
- `GM action (last wk)` · `Final action (last wk)` — the actual prior values, not just a chip
- `Perf history` — one compact cell: `07-26 Skip · 07-19 Pause & review · 07-12 ROAS change …`
  (grows one short entry/week, rendered from the store — never from prior tabs)

Scales flat: week 2 and week 50 are identical; the store holds all weeks, the tab shows a slice.

**Surfacing (decided 2026-08-09):**
- **Report (GM view):** the intuitive home is the **CE-drawer Action Log** — a per-CE timeline,
  newest first, unifying GM (action+comment) AND perf (final+comment) per week + the flag mark.
  Extends the existing `historyFor` drawer trail. The table stays lean (streak chip + current
  action only). Example:
    w/c 07-26  ⚑  GM: skip "rev/clicks dip"       Perf: —
    w/c 07-19  ⚑  GM: roas_change "+5pp"          Perf: ROAS target change
- **Perf sheet (no drawer):** keep a compact inline `Perf history` cell + `Final action (last wk)`
  (last 4 weeks). Both surfaces read the SAME store, so they always agree.
- **Depth:** render **last 4 weeks** (matches W0–W3); the store keeps the FULL trail (drawer can
  expand on demand).

## 4. Sheet as a pure VIEW (CID-keyed, stable order)
- Row identity = `ce_id`. First run of a week sets the CM2-sorted order; later runs **keep each
  CID on its row**, update metrics in place, append newly-flagged CIDs — **no mid-week re-sort.**
- Perf cols are always re-placed by CID (from the store) → **drift impossible.**
- CEs flagged last week but not this week: keep in `Perf history`; don't lose the record.

## 5. Column contract (kills column chaos)
Export owns a fixed schema **A–AT** (identity · weekly blocks · flags · GM cols · perf cols ·
prev-week cols). Perf's own scratch columns go **AU+** — export never reads/writes there. Drop
the leftover duplicate Perf/Final columns (46/47). Header row unmerged each run (already shipped).

## 6. Rollout / migration (must start aligned)
1. **Freeze** the re-export cron.
2. **Backfill** the store's perf layer with the recovered current finals (the 17 from the 5 PM
   aligned snapshot, `/tmp/final_CLEAN_5pm.csv`), via `perf_upsert` keyed by `ce_id` — seeds the
   store correctly. (GM already in the store; don't touch it.)
3. **Deploy** the sync+render export (§2) from that aligned baseline.
4. **Resume** — every run now persists perf finals to the store and renders the sheet from it.

## 7. What it fixes (traceable to the failure list)
- **A/B/C drift** — perf is CE-keyed + stable order → order changes are harmless.
- **D history** — store holds all weeks; sheet renders a slice + compact trail.
- **Prior-week reflection** — real last-week GM action + perf final shown per CE (§3).
- **Store collision** — GM `status`/`note` and perf `final_action`/`perf_comment` are separate.
- **F column chaos** — A–AT contract.

## 8. Decisions (2026-08-09)
- **The report's GM action dropdown is UNCHANGED.** This spec touches only the perf layer; the
  report UI is not modified.
- **`final_action` enum is OPTIONAL, not a blocker.** The fix works with **free-text** perf finals
  (store holds verbatim; history renders them; normalize common variants on read). Keep free text
  for now — don't change perf's workflow. IF a picklist is later wanted, it's a **data-validation
  dropdown on the SHEET's Final action column** (perf-side, NOT the report), using this descriptive
  enum derived from perf's own entries: skip · pause · pause_review · roas_change ·
  negative_seasonality · scale_down · troas_new_to_existing · no_change · to_review. Additive anytime.
- **History depth = last 4 weeks** rendered (report drawer + sheet), **full trail in the store**
  (drawer expands on demand).
- **Reflection surface = CE-drawer Action Log** in the report (§3), compact inline in the sheet.
- Still open: whether perf later enters finals in a report lane too — the store makes it additive,
  not a rework. Relates to [[shared-drawer-spec]], [[perf-sheet-drift-fix]], [[perf-sheet-point-in-time]].
