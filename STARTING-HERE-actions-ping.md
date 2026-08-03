# Actions ping + sheet export — start here

Worktree `worktree-actions-ping` off `main` @ c2f74ce (has Losing Money v2).
Spec: `thoughts/shared/weekly-report-v1/HANDOFF-ping-and-sheet-export.md`. **Post/sheet-writes ONLY from main.**

## Task 1 — Thursday EOD ping (needed Thu Aug 6) — IN PROGRESS
`alert/thursday_actions_ping.py` — reads flagged set (snapshot buckets_final.defend.losing_money.
existing+new) + actions store (`?action=action_list`, bucket=losing_money), joins, renders Slack
blocks: ✅ Actioned (CE·action·owner·comment, worst first) + ⚠️ Review (no action / empty comment).
**Done:** read + join + message builder + severity sort + `--dry-run` (validated on a synthetic
v2 fixture). Fail-soft when the store is unreachable.

**Left to wire:**
1. POST path (marked TODO in `main()`): `post_message.post_message_chunked(token, CHANNELS[slug], blocks)`;
   token = env `REVENUE_ALERT_SLACK_TOKEN`; channel = `market_channels.json[slug]`.
2. Ledger dedupe guard — don't double-post a market-week (pattern: `alert/posted_ledger.json`).
3. Transition-week actions read — `fetch_actions` currently reads the exact week only; add the
   −1d fallback (Mon→Sun key straddle; template pulls −7/−6d, mirror it).
4. Thursday sweep runner (cron) — pattern `run_market_alert_sweep.py`; one Thu-evening IST run;
   main-checkout guard.
5. **Integration test before live:** build ONE real v2 snapshot (`weekly_market_report.py italy
   --no-open`) — a real BQ scan — and dry-run against it. (No v2 snapshot in `.cache` yet; all
   cached ones are v1 `bleeders/...` schema.)
6. (needs Task 3) "deviations" section — where perf's final action ≠ growth's input.

## Task 2 — Weekly Flagged tab auto-export — NOT STARTED
Into the actions spreadsheet, perf's exact layout (identity + 4 weekly metric blocks W0-first +
new_existing/tier + v2 extras + joined action cols). Wire into `publish_weekly.py` (main only).

## Task 3 — two-layer GM-vs-perf action model — NEEDS AARADHYA
One `status` per (week,CE,bucket) = last-write-wins; GM & perf overwrite. Cheapest: 2nd bucket key
`losing_money_perf`. Decide before building.

## Verify
`WR_NOTES_SCRIPT_URL="" python3 alert/thursday_actions_ping.py --slug <s> --week <sun> --dry-run`
