# Mini Audit release readiness — 9 September 2026

**LIVE — production activation and smoke checks completed on 9 September 2026.**

- Production: `dpl_D2euUUHotTC4BJckLrpeFzXF6iGE`,
  `https://market-notebook-6x3wnhako-headout.vercel.app`, serving the main
  `market-notebook.vercel.app` report URL and project production URL.
- Activated the exact tested transcript-only Preview artifact with Production
  environment settings and prepared Apps Script backend version 15.
- All 312 tests pass in the current shared checkout. The headline test already
  permits explanatory “not percentage points” copy while retaining its relative
  change contract; no additional test edit was needed for activation.
- User explicitly chose to retain the September 2 MMP execution export. Headout's
  September target remains unavailable in the approved source and is not inferred.
- Authenticated production smoke: CE7006 thread #2, four completed actions,
  weekly CE memory and full history refresh pass. Transcript processing and
  repeat-import replay pass; the test creates no CE action. Manual Slack summary
  returned no new replies and retained the prior summary in memory. No Slack
  messages or alert broadcasts were sent.
- Before/after comparison confirms every original row unchanged across comments
  (7), work (19), weekly commentary (12), threads (11), imports (1) and suggestions
  (36). Smoke checks added one new-week commentary row and one test import batch;
  unmatched test text was not assigned to a CE. No original data was removed.

The first production attempt could not retrieve Review data and was immediately
rolled back. Production proxy, ingest and summary signing secrets were aligned
with the existing backend properties through the authorized settings UI without
printing their values. A new production build passed reads and transcript tests.
Because rollback pinned the main URL, the corrected build was explicitly promoted.
The prior deployment `dpl_2ch1dV3w3oG3haZftBTvsz1PXD2p` remains the rollback anchor.
Preview configuration and Apps Script properties were unchanged by this repair.

Earlier readiness entries below are historical where superseded by this status.

## Earlier candidate and pre-cutover production

- Preview: `market-notebook-review-preview.vercel.app`, deployment
  `dpl_CiKhHAWghgqhK97x1zngfkZoBvw9` (transcript-only next-week package, 2026-09-06).
- Candidate backend: Apps Script version 6 on separate deployment
  `AKfycbyJ6A3uDqyi58vNLX-nkM8NRNcoZp-uaRV1uxiyWXTkUHBNsvJC90bUmtZAF19UqzS8`.
- Shared Review Sheet and existing record IDs are retained. The original
  weekly-report history workbook remains a read-only history source.
- Production inspected read-only on 9 September: `dpl_2ch1dV3w3oG3haZftBTvsz1PXD2p`,
  `market-notebook-7azcbbjyn-headout.vercel.app`, serving both
  `market-notebook.vercel.app` and `market-notebook-headout.vercel.app`.
  Its aliases and environment settings were not changed.

## Transcript-only verification

144 Mini Audit/Review tests pass. Full suite is 311/312: the existing, untouched
headline test `test_v2_weekly_comparisons_use_relative_percentages_everywhere`
fails on “percentage points” in the current template. This is separate from
meeting imports and remains a release issue. Browser fixture and full-site
preflight passed; 94 historical V1 archives remain byte-identical.

## Remaining release gates

1. **Passed:** removed the exact legacy five-minute trigger from the Sheet-bound
   project and prevented the HEAD installer from recreating it. Candidate version
   6 uses manual summaries. Original deployment versions are preserved.
2. **Passed:** base/summary binding persisted beyond two former sync intervals
   and a page reload. CE7006 discussion #2 retained its summary.
3. **Passed:** live two-CE transcript, ambiguous-CE handling, owner/date extraction,
   approval, completion, dismissal and repeat import. Replays returned zero new
   suggestions and preserved both decisions. Added durable extraction batches in
   the same Sheet and behavioral race/replay tests; 302 tests pass.
4. **Removed from scope by user:** Granola link import. Meeting imports now use
   pasted transcripts only. The report has no link field or link-ingestion client;
   packaging removes inherited Granola link/pull/webhook routes. Historical
   meeting notes, source links and action records remain readable. Granola plan
   access and a live-link test are no longer release gates.
5. Run the canonical all-market plus Headout generation and package checks for the
   release week. For the current next completed week, the prepare-only command is:

   ```sh
   python3 scripts/weekly_report/run_v2_release.py --week 2026-09-06 \
     --notebook-dir .cache/weekly_report/mini_audit_release_2026-09-06
   ```

   All 18 snapshots finished; parity, current market goals, OKR and full-site
   Review packaging pass. The separate recovery receipt records the target refresh
   after login repair. Native Preview verification confirms the next-week CE loads
   existing Slack discussion #2, all four completed canary actions, and the
   previous week’s notes/summaries with source links. Full history refresh finished.
   Headout’s approved September target remains unavailable in the source.
   All 17 market alert/RCA dry runs passed; no Slack alerts were sent.
   Preserve unrelated existing CSEE/Nordics, targets and renderer changes.
6. **Prepared:** user explicitly approved the temporary OpenAI key for Production.
   `REVIEW_OPENAI_API_KEY` now retains Preview and includes Production;
   `REVIEW_AI_PROVIDER=openai` is saved for Production. Backend version 15 is
   frozen and deployed separately, with source hash matching the tested candidate.
   The active production endpoint and website have not switched. Production
   authenticated smoke testing must follow the separately approved activation.

## Target credential recovery — Google Drive scope

The 17-market `2026-09-06` parity gate passed, but live monthly targets were
unavailable. The authoritative BigQuery external table returned HTTP 403:
`Permission denied while getting Drive credentials` (source spreadsheet
`1TkLFdt8wWi-fkUqXn9o8USWvc0mSaSJY6rjmIaT1Dp4`). The existing Google Cloud
CLI login was checked through token scope metadata and also has no Drive scope.
No token value was printed, saved, or put in a URL.

The user approved and completed a Google login refresh with Drive read-only
scope. The canonical North America September target query now succeeds (one
approved market target; 54 CE target rows). All 17 market snapshots and Headout
finished in the original run. Its final alert dry run failed because targets
were absent. Recovery reruns the canonical combined target/parity gate, shared
report, staging and alert dry run using those exact saved snapshots; no core
snapshot is queried again. The recovery receipt is
`.cache/weekly_report/mini_audit_targets_recovery_2026-09-06.json`.

The next-run check also found that the V2 publisher omitted the Mini Audit
bootstrap and summary/import routes. Its V2 packaging step now stages the full
Review runtime and injects market pages, preserves V1 archives, and excludes
Headout. A real-renderer integration test covers fresh packaging and repeat
injection; a broken V2 mount stops staging. The standalone weekly package is
combined with the existing complete notebook's missing assets before full-site
preflight; it does not replace the monthly home or erase historical reports.
All 17 market goal states are current. Headout has no approved September target
record; a read-only source check also found no company/Headout row. Its target
is left unavailable. Full baseline verification now passes 312 tests. The next
week package preserves 94 original V1 archives and the monthly homepage.
Preview: `https://market-notebook-review-preview.vercel.app/weekly-report-north-america-2026-09-06?view=review&ce_id=7006`.
Production was re-inspected and remains on the same deployment listed above.

## Prepared production configuration (activation pending)

Prepared backend version **15**, deployment
`AKfycbwJ5HWaNwt2cikPHiD4xewKNYrIgI-MKpVe306M4zkiBXJQfiRSPppxfSoqAX-o3aQy`,
uses the tested Apps Script source from `scripts/weekly_report/notes/review_apps_script.js`
(SHA-256 `9f7847d11cb827e3702ed08226d02f1b3d81777ff10c8e529ce8a40a66a860ef`) in a separate immutable deployment of the existing Sheet-bound
production project `1PcyDdbEK8zpSm_L8lhopGOIJlode56Y1bMBSiABcQ0GoBqcIpcKRRsP6`.
Keep the separate Preview service and its properties isolated. The canonical
spreadsheet stays `1iM8v31-Ti7le_Y-6Nivn--ddqPJ43EvXCurBL2h3RmA`.

The key/provider settings are saved for a future deployment. The endpoint switch
and website activation remain pending explicit approval:

| Location | Setting | Proposed value |
| --- | --- | --- |
| Vercel Production | `REVIEW_MODE_APPS_SCRIPT_URL` | Switch to prepared version 15 during approved activation |
| Vercel Production | `REVIEW_AI_PROVIDER` | `openai` — saved, user approved |
| Vercel Production | `REVIEW_OPENAI_API_KEY` | Existing temporary secret, scoped to Production and Preview by user approval |
| Production Apps Script | `REVIEW_MODE_AI_WEBHOOK_URL` | `https://market-notebook.vercel.app/api/review-summary` |
| Production Apps Script + Vercel | Proxy / ingest / summary signing secrets | Confirm matching values in secret stores; never print them |
| Production Apps Script | Scheduled review sync | None; manual summaries only |

The Preview service currently calls the Preview summary endpoint. Do not point
production at that service and leave its webhook targeting Preview. Preserve
original endpoint/configuration values privately for rollback before changing
them. The key/provider environment settings changed as authorized; no production
website deployment or alias switch occurred. Existing Apps Script properties
were read without printing secrets: Sheet ID and production callback are correct,
access enforcement is enabled, Slack and signing secrets are present. The
original script HEAD was restored exactly after freezing version 15; its prior
deployments remain untouched. Existing secrets are write-only in Vercel and were
preserved; a decrypted export does not prove they are empty.

## Rollback preparation

Re-inspect production immediately before any approved cutover; the deployment ID
above is the currently verified rollback anchor, not a promise it remains current
after another weekly run. Preserve the prior deployment and backend versions.

If an approved production cutover must be rolled back, the CLI-supported command
for the currently captured deployment is:

```sh
vercel rollback dpl_2ch1dV3w3oG3haZftBTvsz1PXD2p --yes
```

Run only with production rollback authorization. Verify both production aliases
and authenticated report/API behavior afterward. A website rollback does not
restore or undo Sheet records, external Slack messages, Apps Script triggers, or
project environment edits. Preserve comments, actions, summaries and thread IDs;
do not restore an old workbook over midweek activity. The competing writer must
be resolved independently before any production cutover.

The heartbeat remains paused. Granola API access is no longer required for this report. Nothing in
this document authorizes a production deployment or Slack alert broadcast.

Final prepare-only recovery status: **passed**. All 17 market alerts and RCA
payloads completed in dry-run mode. Target warning above is still open. The
report uses the configured MMP snapshot dated 2 September 2026; refresh that
source for production if a newer approved export is required.


## Latest data-source check

- Approved `Goals Input Sheet` / `Revenue Goals` contains 822 data rows and no
  Headout/company/total row. An alternative top-down sheet also contains market
  rows with different targets; it is not silently substituted for the approved
  report source. A company target needs an authoritative value/source.
- `MMP Planning MMP Details Export - 2026-09-08`, Sheet
  `1c5qrTao3I-ziS-IEiVtvIMgTHCKfumDpe0B2juakKWY`, has 93 planning rows and no
  execution/handover-date columns. It cannot replace the execution history.
- The legacy live `Market Kit V2` / `MMP Execution Data` has 266 rows and was last
  modified August 6. The canonical loader explicitly prefers the user-provided
  pinned execution export over this older sheet. Local downloads contain no
  newer compatible export. Retained September 2 CSV: 928 rows, parsed into 668 CE
  records. No execution dates, missing rows or company targets were invented.
- User has been asked for the approved company target and a newer compatible MMP
  execution export, if one exists. Source schemas and history were left intact.
