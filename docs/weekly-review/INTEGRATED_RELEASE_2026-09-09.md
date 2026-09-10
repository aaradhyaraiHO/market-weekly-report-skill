# Integrated weekly release — 9 September 2026

## Frozen candidate

- Artifact: `.cache/weekly_report/integrated_release_2026-09-09`
- Source production artifact: `.cache/weekly_report/mini_audit_release_2026-09-06`
- Receipt: `.cache/weekly_report/integrated_release_2026-09-09_receipt.json`
- Source rollback anchor: `dpl_D2euUUHotTC4BJckLrpeFzXF6iGE` (`market-notebook-6x3wnhako-headout.vercel.app`).
- 92 dated V2 pages upgraded; 40 current/preview snapshot parity checks passed. Historical payloads before August 30 retained, without rehydration from subsequently repaired snapshots.
- All pre-existing parent metric values, comparisons and series retained. Only additive drawer YoY/platform properties are attached after exact parent-operand equality. Missing optional platform operands remain unavailable, not zero.
- Latest aliases and weekly ledger restored to August 30–September 5. September 6–12 dated artifacts retained with an explicit incomplete-week preview notice.
- Monthly and V1 HTML artifacts verified byte-identical to the source release.
- Backend: existing Apps Script deployment now immutable version 16, source SHA256 `33454dc008222bed9c3454a627ed4539867bbcb03e9ec02fb3a9be1abc455caf`. Activation receipt and version-15 rollback request retained in `.cache/weekly_report/mini_audit_binding_deploy_2026-09-09/`.

## Automated and responsive checks

- 317 unittest tests passed; `git diff --check` passed.
- Mini Audit and Overview inspected at mobile 390px and tablet 768px. Document scroll width equals viewport width. Earlier integrated preview also inspected at 1080px.
- Overall/Paid switching and Google/Bing expansion work with Mini Audit open. Combined parent values remain intact; unavailable CTR/RPC/CM2/ROI platform operands are explicitly labelled.
- Responsive inspection caught a blank single-market selector: `.filter-field { display:grid }` overrode `hidden`. Added an explicit hidden rule and regression test. Reloaded the final staged artifact and verified `display:none`.
- Temporary viewport overrides reset.
- Used weekly-market-report-v2 for frozen-source parity and cutover gates, and make-interfaces-feel-better for responsive inspection. No visual redesign was introduced.

## Live summary source and baseline

- CE 2567, Niagara Falls (US) Tours, report week August 30.
- Slack parent: https://headout.slack.com/archives/C0BQHT29WMB/p1788876228790149
- Asfan's real reply: “Note: Clicks grew because campaigns had positive seasonality.”
- The later September 6 bot test is not a new human reply and must not be used as business evidence.
- Read-only pre-summary backend baseline: `.cache/weekly_report/mini_audit_live_summary_2026-09-09/before-summary.json`, captured 11:39:47 UTC.
- Before: August 30 summary absent, weekly binding absent, one already-approved human source. No duplicate source references or idempotency keys. September 6 summary absent, zero human replies.

## Activation and live verification

- Production deployment `dpl_4Y8NJeuJR1WReyqoA1NSmdU6i8HX`, immutable URL https://market-notebook-aav8l9fnn-headout.vercel.app, built with Production settings and promoted successfully to https://market-notebook.vercel.app. Existing authentication and hosting settings were preserved.
- Matching backend version 16 is active on the unchanged endpoint/deployment. Source activation receipt is recorded above.
- Live production CE 2567 / August 30 generated a **new** summary from Asfan's existing human reply: “Clicks increased due to positive seasonality in campaigns.” The UI reported “Summary saved to CE memory” at 17:17 IST.
- Independent after-first-summary snapshot: `.cache/weekly_report/mini_audit_live_summary_2026-09-09/after-first-summary.json`, captured 11:49:06 UTC. August 30 summary was approved, source reference is only `C0BQHT29WMB:1788876261.476069`, and the missing August 30 binding was restored to `thb_0d21ec79-5742-4b47-96b9-5decf68b1a2d` / discussion 2. The original source, comment, cursor and reply count were retained. Other three weekly records and both Slack registry records were unchanged.
- No Slack message or parent alert was posted by this test. One pending, unapproved suggested check was extracted; no new work record was created. Its model-inferred date is not a human commitment and must not be treated as approved work.
- A transient suggestions-read error recovered after Retry; the final visible panel showed one suggestion, zero open actions and one pre-existing completed action.
- **Fresh-load and repeat verification passed** in a separate authenticated in-app production tab. The first fresh load displayed the saved 17:17 summary, Asfan's original note and saved finding, and 1 suggested / 0 open / 1 completed. One explicit repeat entered “Reading Slack replies and summarizing…” and returned successfully. Reloading after the repeat retained the same summary, source and counts.
- Read-only `.cache/weekly_report/mini_audit_live_summary_2026-09-09/after-confirmed-repeat.json` is identical to the first-summary snapshot across all six raw backend tables: weekly commentary 6 rows, suggestions 3, comments 1, work 5, bindings 3, timeline 1. Independently normalized `.raw` SHA256 for both snapshots: `bb5cff453ebfd7e4903e5105efcbfcf2e462cf8f55cdb8de8926c8a10e2bbf3c`. No duplicate suggestion/work, no cursor/version change and no September 6 change.
- **38/38 final production routes passed** authenticated browser checks on `market-notebook.vercel.app`: every latest route displays August 30–September 5, and every dated September 6 route displays September 6–12 plus the incomplete-week preview notice. No latest route displays that notice. All expected market/shared pages include Mini Audit; Headout intentionally does not. Unauthenticated requests redirect to Google login; those redirects were not counted as report verification.
- Route pairs checked: `north-america`, `italy`, `oceania`, `france`, `united-kingdom`, `iberia`, `csee`, `nordics`, `east-asia-jpn-sk-hk`, `sea-sin-tha`, `united-arab-emirates`, `gcc`, `north-africa`, `rest-of-mea`, `benelux`, `south-america`, `mexico-central-america`, `headout`, `csee-nordics`. Each pair is `/weekly-report-{suffix}` and `/weekly-report-{suffix}-2026-09-06`.
- The production binding / new-summary / persistence / duplicate-verification blocker is cleared. This is not a claim that the separate scope below is completed or that every possible failure mode has been eliminated.

## Separate remaining scope

- CSEE/Nordics shared shell still selects between datasets; it is not yet a true combined-total report.
- Historical snapshots do not contain every optional platform operand.
- Headout September target is unavailable in the approved source; Headout Slack thread access remains unverified.
- Monday market alert presence audit remains 148/148 expected CE explanations across all 17 markets; no parent alert reposts are needed or performed by this release.
