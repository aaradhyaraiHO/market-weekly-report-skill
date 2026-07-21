---
date: 2026-07-21
repo: ~/market-weekly-report-skill
topic: "10-market fan-out + Slack alerts SHIPPED; Headout-level report — MVP built (wrong arch) + plan for the true global build"
main_head: 3f26709
worktree: worktree-headout-global @ a8dde04 (unmerged)
status: fanout live; headout MVP in worktree needs re-architecture to true-global
---

# Handoff — Weekly Report: fan-out live + Headout-level report (2026-07-21)

## TL;DR
1. **10-market fan-out + Slack alerts are LIVE** (week 2026-07-13) — reports on the Ledger, alerts in each market channel.
2. **Headout-level report:** an MVP exists in `worktree-headout-global` but it's built the **WRONG way** — it *sums the 10 per-market snapshots*, which undercounts real Headout by **~17.5% ($2.69M vs $3.26M)** and misses **59 of 69 markets**. Decision made: rebuild it as a **true global query (no market filter)**. Plan below. NOT started.
3. **A regression fix is stranded in the worktree** (CVR-sparkline revert) that **must reach main** — big-market per-market rebuilds on main currently fail at the byte cap until it merges.

## Git state
- **main @ 3f26709** — has the 10-market fan-out, the alert bundle (`alert/`), config with all 10 markets, AND the CVR-sparkline **regression** (from merging worktree-CE-drawer). Big-market snapshot rebuilds on main FAIL (see Gotchas).
- **worktree-headout-global @ a8dde04** (5 unmerged commits): `build_global.py` (merge-based MVP) + guarded template additions + the **CVR-sparkline revert + cap→80GB** (a8dde04, the regression fix).
- `.cache` in the worktree is a **symlink** to main's `.cache` (so build_global reads the shared snapshots). Snapshots for 2026-07-13 were rebuilt this session (restated: fuller maturity, PP populated, +sis fields) — deployed reports are static/unchanged (cache drift, harmless).

## What shipped LIVE this session (main)
- Fan-out 3→**10 markets** (config.MARKETS): na, italy, oceania, france, united_kingdom, iberia, csee, east_asia, sea(=“South East Asia”), uae.
- Per-market reports built for 07-13, Slack digests curated (9 via parallel agents), published to Ledger, **deployed**.
- **Slack alert bundle** (`alert/`): weekly_alert → weekly_rca_helper (BQ RCA) → post_message; update_posts_weekly for in-place edits. Posted to all 10 real channels. Market greeting `Hello team @<market>` (cosmetic, matches monthly). Alert tables source `buckets_final` (§4), NOT raw bucket lists. Report link uses ledger-slug (fixed a 404).

## Headout report — the RE-ARCHITECTURE (the main open work)
**Why the MVP is wrong:** `build_global.py` merges the 10 snapshots. True Headout = ALL 69 `business_market` values. Proof (07-13): all-markets $3,261,473 vs our-10 $2,691,758 → **$570K / 17.5% missing**.

**The plan (agreed): `build_global` v2 = query the producer globally, no `business_market` filter.**
Dry-run cost facts (free to re-check):
- `combined_entity_stats` 12wk ALL markets = **~21 MB** → market-level totals/metrics/breakdown/trend are ~FREE.
- `mixpanel_user_page_funnel_progression` (7.7 TB) 1 week ALL CEs = **~41 GB/window** → per-CE RE-SOURCE drawers (`ce_funnel`, `ce_tgid_funnel`, W0/W-1/LY) ≈ 120 GB+ if run for ALL CEs.

**Key design decision:** market-level is free; the expense is per-CE Mixpanel drawers. So **compute RE-SOURCE drawers ONLY for the surfaced CE set** (flagged in buckets + top movers + top-N revenue), never all ~thousands. Bounds Mixpanel to ~one big-market's cost.

**Phasing (do Phase 1 first):**
1. **Market-level global** — accurate $3.26M total + per-market breakdown (all 69, top-N + “rest”) + metrics + trend + structural. ~free, high value. This IS the "Headout overall" headline.
2. **Global buckets/movers/fluctuations** — CE-level across all markets (fct_orders/ads daily; dry-run before running).
3. **Per-CE drawers** — Mixpanel funnel/tgid for surfaced CEs only.

**Reusable:** the template additions already built are data-driven and work for the global version — market-breakdown table (§1), Market filter+group (§3), Market column (§4), §2-by-market, §3 cap note. All guarded by `_isHeadout(M)` / `M.market_breakdown` / `meta.ce_cap` / rows carrying `market` → per-market reports unaffected. Only `build_global.py`'s merge logic gets replaced.

**Implementation:** add "global" variants to ~12 `fetch.py` functions (drop the `WHERE business_market=@market`), a global `build_market`-equivalent, and the surfaced-CE gating for RE-SOURCE. Est. multi-step (~2-3 sessions).

## Open TODOs (priority order)
1. **Merge the CVR-sparkline revert to main** (from worktree, commit a8dde04) — un-breaks big-market per-market rebuilds on main. Can cherry-pick just that if not merging the whole worktree yet.
2. **Build true-global Headout** — Phase 1 (market-level) first, verify $3.26M, then Phases 2-3.
3. Pending per-market refresh (surface PP for 7 markets + fuller maturity) — separate; cache already restated, needs re-render+republish.
4. Follow-up §2 + Market Review textarea → wire GM notes (see [[followup-wiring]]).
5. Legacy bucket_b1 cleanup ([[legacy-b1-cleanup]]).

## Gotchas / learnings
- **CVR-sparkline (9ab0ed4) is a cost regression on main.** Its 12-week `ce_weekly_funnel` scans up to **320 GB/run** on big markets (7.7 TB table). REVERTED in the worktree (a8dde04) to the cheap 2-week path. Must reach main. Don't chase the byte cap — the query was the problem.
- **Don't backfill-rebuild snapshots for marginal metric polish** ([[dont-over-serve-marginal-polish]]). SIS/contribution exact wasn't worth rebuilding 10 markets; the cheap producer emit (kept) makes it exact for free on the NEXT normal weekly build.
- **Alert tables MUST source `buckets_final`** (§4 processed buckets), never raw `bucket_b1`/`bucket1_fluctuations` (Parag flagged; fixed).
- **Failed over-cap queries bill $0** (BQ rejects pre-scan) — the scary 141/320 GB failures cost nothing.

## Key commands
```bash
# Headout MVP (current merge-based — WRONG arch, kept for reference):
cd <repo>/scripts/weekly_report && python3 build_global.py --week 2026-07-13
python3 render.py ../../.cache/weekly_report/snapshot_headout_2026-07-13.json --no-open
# report → thoughts/shared/weekly-report-v1/report_headout_2026-07-13.html
# dry-run any query cost (free): bq query --use_legacy_sql=false --dry_run '<sql>'
```
Memory: [[headout-level-report]], [[weekly-fanout-and-alerts]], [[dont-over-serve-marginal-polish]].
