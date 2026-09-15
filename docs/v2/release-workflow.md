# Weekly V2 release procedure

This is the operator contract for `run_v2_release.py`, `release_integrity.py`,
`prepare_delivery.py` and `safe_delivery.py`. For latest observed deployment and
activation evidence, consult `recurring-run-closeout-2026-09-15.md`;
`unattended-release-readiness-2026-09-11.md` is historical evidence.
Implementation and local tests are not a supervised live-run pass.

## Prepare

1. Resolve the exact checked-out commit and latest remote state without discarding
   unrelated changes. Use a completed Sunday–Saturday week, explicitly its Sunday
   start in Asia/Kolkata. Data maturity inside buckets is not permission to shift
   the report headline to an older week.
2. Identify the verified complete production notebook artifact and its deployment
   as the preservation/rollback base. Stage into a separate empty directory. The
   seed includes notebook/auth/API/archive files but excludes credentials and build
   caches. Only this week's current/dated report files and weekly index/state may
   change; unrelated added files also fail the gate.
3. Check read-only BigQuery access and approved target sources. Google/Bing raw
   evidence, including TY/LY comparisons, follows the existing metric definitions;
   missing source fields stay unavailable. See `future-platform-history-2026-09-11.md`.
4. Before authorized deployment, run `python3 alert/v2/delivery_access.py`. All
   configured markets plus Headout must support Slack history/thread reads. The
   runtime token is `REVENUE_ALERT_SLACK_TOKEN`; never print or commit it. Private
   Headout requires `groups:history` and app membership. Only an authorized app
   collaborator/admin can change scopes and re-authorize the app.

```sh
python3 scripts/weekly_report/run_v2_release.py --week YYYY-MM-DD \
  --base-notebook /absolute/path/to/verified-complete-notebook --plan
```

Review the plan. Omit `--plan` for local package generation with read-only source
queries; no deployment, Slack posts or Sheet writes occur by default. Do not run
the build twice into the same package: the immutable bundle and nonempty-stage
guards intentionally stop accidental regeneration.

## Authorized release

For a newly approved release, add `--deploy --post-alerts` to that command only
when the user has authorized both. The sequence is baseline/access gates → seed
complete notebook → all markets + true-global Headout → goals/OKRs/parity → shared
CSEE/Nordics page → readiness/staging → frozen alert/RCA bundle → preservation
manifest → explicit Vercel deployment → live verification → frozen delivery.

All Top/Bottom CE RCA is prepared before delivery. The preparation deduplicates CE
queries and constrains batches; byte-cap failures split the batch without raising
the cap. Missing/failed RCA stops the batch before any parent is posted. The
shared CSEE/Nordics page continues to contain separate datasets, not combined
totals; aggregation remains paused.

Never substitute `run_weekly.py --alert-version v2 --post` or the V1 poster. The
staged V2 command is dry-run-only; V1 code remains the explicit fallback, not an
automatic retry path.

## Browser verification handoff

Browser mode is the default because the user selected their signed-in browser.
The run pauses with `awaiting_browser_verification` after deploying when no
observations exist. Its receipt's `planned_steps` retains the exact verification
and delivery commands; `steps` records only attempted work. Neither a pause nor
deployment means alert completion. Do not rerun generation/deployment to resume.

Use CUA to freshly visit every route in `artifact.json.browser_files`. For each:

- Confirm the canonical final URL and inspect the displayed market/week and UI.
- Read each `browser_components` selector/index individually using DOM text
  access; bulk array evaluation can truncate large report-data strings.
- Compute SHA-256 of each UTF-8 script/style text, then SHA-256 of JSON.stringify
  of the ordered objects `{tag,sha256,src}`. Use the manifest's original components;
  do not include browser-extension-injected nodes or fabricate observations.
- Record `{file,url,sha256,visible_text,observed_at}`. Do not access cookies,
  storage, authentication codes or session tokens.

Save the observation array into the package's `browser_observations.json`, then
execute the receipt's planned `verify-live-reports` command. Coverage, canonical
URLs, data/UI fingerprints and timestamps are checked. Evidence must be under
one hour old; collect it again on expiry or deployment change. Optional HTTP mode
requires an approved externally supplied session and verifies exact file hashes;
it is not a workaround for browser authentication.

## Delivery and recovery

Run the receipt's planned `post-alerts` command only after successful live proof.
It binds the frozen bundle's headline hashes to the verified artifact, preflights
all Slack destinations, locks delivery and reconciles existing parent/reply state.
The only supported retry is that same command with the same immutable bundle,
existing `alert/posted_ledger.json` and persistent delivery journal.

- Never clear, replace or rebuild a ledger/journal to retry.
- Never repost existing parents or overwrite matching complete RCA threads.
- Lost acknowledgements are reconciled by deterministic IDs and Slack read-back.
  Ambiguous absence, deleted messages, changed content or duplicate matches stop
  for review; they are not permission to send another message.
- Final fresh Slack reads must verify every parent and RCA chunk. A post API
  acknowledgement, local ledger or no-new-replies smoke alone is insufficient.
- Report market-by-market parent/RCA/missing status. If a later market fails,
  retain earlier completed state and resume the frozen bundle after diagnosis.

## Activation

Commit/push does not deploy or enable scheduling. Activation requires working
access, a supervised completed-week release with every report link and Slack
thread verified, and explicit user authorization. The September 14 run met the
live verification gates after recovery; the user authorized recurring operation
on September 15. See `recurring-run-closeout-2026-09-15.md` for the verified base
and the schedule's operating contract. Preserve comments, Mini Audit, CE memory,
historical pages, Sheets and OKRs. The Monday 11 AM IST deadline remains a target,
not a proven guarantee; record actual runtime and upstream availability.
