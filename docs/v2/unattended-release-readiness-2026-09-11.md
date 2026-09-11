# Weekly unattended release readiness — 11 September 2026

## State: NOT ACTIVATED

Maintained operator instructions: `release-workflow.md`. This dated record is
verification evidence, not permission to deploy, send, or activate scheduling.

Google/Bing future comparison evidence is committed in `5275f70`. Shared metric
SQL, formulas and bucket classification are unchanged. No historical report
backfill or snapshot-archiving infrastructure was added.

The hardened V2 path is implemented with local regression tests, but has NOT
completed a supervised production generation/deploy/new-Slack-delivery run.
Do not describe code tests as live end-to-end verification.

A bounded real CSEE canary subsequently passed fresh generation, preview
deployment, two browser route checks, two test parents plus ten RCA replies,
and duplicate-free retry. It exposed and fixed Slack text-normalization handling.
See `csee-test-channel-canary-2026-09-11.md` for exact evidence and limitations.
This is not the full production runner/all-market gate. Latest suite: 391 tests.

Verification evidence: 389 local weekly/V1 tests passed, including interrupted
delivery, RCA batch constraints, notebook preservation and browser-proof tests.
The additional handoff checks retain unexecuted verification/delivery commands
in atomic run receipts and reject unrelated files newly added to the artifact.
The existing full artifact passed the preservation/latest-route inspection for
18 headlines and 41 HTTP targets (38 report routes plus landing/index/state).
This was a local artifact check, not a fresh deployment. The existing Slack ledger
SHA-256 remained `14ad1074ae3bbd3457cfd0d1221d0d1b494b926a489702e645df80926151fe4f`.

Codex scheduling is selected on this Mac; the user will keep it awake, powered,
online, and Codex open. A Monday 06:00 local-time task is PAUSED, targeting
completion by 11:00 Asia/Kolkata after readiness is established. It must remain
paused until the following blockers are resolved and the supervised run passes.

## Live blockers established by read-only checks

- All 17 market channels permit history and existing-thread reads.
- Headout's exact parent `C0975BGAX0B / 1788765108.024799` returns
  `missing_scope`, needed `groups:history`. It matches the preserved ledger.
  An app administrator must approve that scope and install/re-authorize the
  app as appropriate. Do not change the channel or repost to work around it.
  The signed-in Aaradhya browser account was rechecked: app management for
  `A07ECLRAHTP` still says to contact an app collaborator. Workspace sign-in alone
  does not permit editing this app's scopes.
- The user clarified that notebook verification must use their signed-in
  browser, not a machine credential. Browser mode is the default. It captures
  original report script/style fingerprints (including the complete report-data
  payload) and visible UI evidence for every current/dated report plus notebook
  landing/weekly pages. No cookies are extracted. Fresh North America production
  data and UI-code hashes matched the existing verified local release during
  development; this is a one-page smoke, not all-route or new-release E2E proof.
- As of Friday 11 September, 6–12 September is incomplete. The completed-week
  gate will not permit its release before Sunday 13 September. Do not label the
  existing preview a completed-week report. The previous completed week's
  parents already exist; do not post new parents as an E2E test.

## Safety implemented

1. Require a complete verified base notebook, seed a separate empty directory,
   exclude secrets/build caches, and preserve all files outside this week's
   current/dated reports and weekly index/state. Reject unexpected API, auth,
   archive, or landing-page changes.
2. Require all 18 market/Headout current and dated routes plus the unchanged
   two-dataset CSEE/Nordics shared report. Confirm latest dates, identical
   current/dated artifacts, and headline hashes.
3. Prepare one immutable alert bundle for all 18 scopes. Deduplicate CE queries
   across scopes. Constrain RCA batches to ten IDs; byte-cap failures split the
   batch without increasing the cap. Unrecoverable/missing RCA prevents any
   parent from being sent. Missing source data is not replaced by invented data.
4. Verify canonical URLs through the signed-in browser against staged report
   data/UI-code fingerprints and visible page evidence. Redirects, login pages,
   stale weeks and mismatches fail. Bind alert headline hashes to that manifest;
   require observations less than an hour old before delivery/retries. Optional
   HTTP mode uses exact byte hashes and a legitimate externally supplied session.
5. Use a release lock and delivery lock, atomic ledger updates, persistent
   per-message write-ahead journals and deterministic Slack client IDs. A lost
   acknowledgement is reconciled via Slack reads, not a blind resend. Ambiguous
   absence stops for review. Legacy parent mismatches also stop, never overwrite.
6. Require fresh Slack reads of every parent and RCA chunk before completion.
   Preserve existing ledger records, notes, comments, Mini Audit and CE memory.

These scripts do not change live report UI. The current notebook deployment
remains the previously verified RPC-precision release; there was no deployment
or Slack write during this hardening work.

## Supervised run and activation

After permissions and approved notebook access are configured, rerun
`python3 alert/v2/delivery_access.py`. Verify the exact source commit and current
base deployment, then review the no-write plan:

```sh
python3 scripts/weekly_report/run_v2_release.py --week 2026-09-06 \
  --base-notebook /absolute/path/to/verified-complete-notebook --plan
```

Only after the week is complete and readiness passes, execute with the approved
`--deploy --post-alerts` flags. Preserve the base directory as rollback material.
Do not bypass a failed preservation check or deploy with incomplete credentials.

The default browser mode stops with `awaiting_browser_verification`, not success,
after deployment. The scheduled Codex agent then uses CUA on the user's signed-in
browser to visit every `artifact.json.browser_files` route freshly. Follow the
manifest's `browser_components` selectors/order. Read each component individually
with locator.textContent (array evaluation truncates large strings), calculate
SHA-256 of each UTF-8 text, and hash JSON.stringify of the ordered objects
`{tag,sha256,src}`. Ignore only extra browser-extension nodes not present in the
artifact's component list. Capture URL, visible page text and ISO observed_at.
Never capture cookies, storage or session tokens. Compare all returned fingerprints
and inspect the displayed market/week; do not fabricate an observation receipt.

Save observations as an array of `{file,url,sha256,visible_text,observed_at}` in
the package's `browser_observations.json`, using apply_patch. Validate them with
the `verify-live-reports` command in the run receipt (release_integrity.py browser),
then run the frozen `post-alerts` command from `planned_steps` (the complete plan,
including steps not attempted before the browser pause). Fresh evidence is required after an
hour or a changed deployment. The agent must report the final Slack result,
not interpret the pre-browser generation receipt as workflow success.

If delivery is interrupted after preparation/deployment, do not regenerate the
bundle or restart with the legacy poster. Resume the same immutable bundle:

```sh
python3 alert/v2/safe_delivery.py \
  --bundle .cache/weekly_report/v2_package_2026-09-06/delivery.json \
  --ledger alert/posted_ledger.json \
  --state-dir .cache/weekly_report/delivery_state \
  --artifact .cache/weekly_report/v2_package_2026-09-06/artifact.json \
  --verified-release .cache/weekly_report/v2_package_2026-09-06/live_verification.json
```

The bundle, ledger and delivery state must stay on persistent local disk. Never
clean them to retry. Generation/deployment failures are not blindly retried;
inspect their receipt and preserve any already-staged bundle.

After the supervised run, inspect all Slack threads, publish a market-by-market
status, and only then activate the paused Codex schedule. Do not claim a Monday
deadline is guaranteed until real runtime and upstream data availability are
measured. CSEE + Nordics aggregation remains paused.

The weekly-market-report-v2 skill kept this work in orchestration/delivery and
additive evidence; OpenAI Docs guided the local, paused scheduling setup.
