# Weekly release verification — 9 September 2026

This is the **pre-repair audit** of deployment `dpl_D2euUUHotTC4BJckLrpeFzXF6iGE`. For the subsequently promoted integrated release and live repair evidence, see [Integrated release](INTEGRATED_RELEASE_2026-09-09.md). Findings below are retained as the historical baseline, not the current deployment status.

## Result: not ready for sign-off

Audited production deployment `dpl_D2euUUHotTC4BJckLrpeFzXF6iGE` (Ready, created 9 September at 15:41 IST), rechecked at the end of this audit. Its immutable hostname is https://market-notebook-6x3wnhako-headout.vercel.app. Tested using the authenticated production browser.

The current shared checkout passed all 312 baseline tests and `git diff --check`. That does not establish parity between the newer local UI and the deployed artifact.

## Release blockers / remaining work

1. **Latest points to an unfinished week.** All 38 dated/latest routes tested below render 6–12 September 2026. On 9 September, this is not a completed week. Monday 7 September's completed reporting period is 30 August–5 September. Live CSEE even says “Revenue through 12 Sept”. Restore the completed-week latest selection, or explicitly segregate/label the September 6 package as an in-progress preview. Add a completed-week guard before publishing and alerting.
2. **Fresh summary creation is not verified and an actual binding failure is reproducible.** Details below. Do not call the live workflow complete.
3. **Approved Overview improvements are not all deployed.** Live NA still shows “Weekly evidence · V1 baseline” rather than the current “Weekly performance” section and lacks the new scope / platform-breakdown controls. The current local integrated render includes those changes. Freeze a single candidate, commit it, deploy that exact artifact and repeat live checks.
4. **CSEE + Nordics is not an aggregate report.** The shared production URL has a selector with CSEE and Nordics, shows CSEE's $326.4K headline by default and CSEE-only OKR contributions. This is two selectable datasets in one page, not the combined totals requested.
5. **New paid platform fields are not fully populated in old snapshots.** On the latest integrated local render from the unchanged September 6 snapshot, platform clicks/spend/conversions/CVR expand, but CTR and RPC show “Platform data unavailable” for Google/Bing. Do not turn these into zeros. Populate required source operands if full platform coverage is expected.
6. **Headout September target remains unavailable in the approved source**, as recorded in the release recovery / activation evidence. Do not manufacture a target. Headout's Monday Slack content could not be independently checked with the current connector (channel_not_found).

## Mini Audit live summary test

Source discussion: https://headout.slack.com/archives/C0BQHT29WMB/p1788876228790149

Direct Slack read confirmed:
- Parent is CE 2567, Niagara Falls (US) Tours, W/C 2026-08-30.
- Human reply: “Note: Clicks grew because campaigns had positive seasonality.”
- A later bot-posted “test” reply links to the September 6 cycle. No new human reply exists in that later cycle.

Production test:
- September 6 page: no summary initially. Clicking Summarize discussion returned “No replies to summarize yet.” This is not evidence of fresh summary creation; the real human reply belongs to August 30.
- Opened the explicitly dated August 30 page with the same CE. It showed Continue discussion #2 and no summary.
- Clicking Summarize discussion returned **“CE thread changed. Refresh before summarizing.”**
- Reloaded the page and retried once. The same error remained; no summary was produced.
- The backend deliberately rejects a requested binding that differs from the saved weekly binding (review_apps_script.js). The UI/historical binding mismatch needs diagnosis and repair without overwriting historical thread associations.

No Slack parent alerts, replies, business actions, or synthetic business notes were created by this audit. Only the authorized summary controls were invoked. No report, snapshot, OKR, deployment or duplicate-ledger changes were made.

## Responsive / integration checks

Built a local-only integrated render using the current renderer + Mini Audit injector and the existing September 6 NA snapshot. Used the provided simulated-backend preview; no integrations write externally. Preview: /tmp/wbr-release-audit.Brl4ZF/weekly-report-north-america-2026-09-06.html.

- Live Mini Audit visually inspected at desktop, ~1024px and ~391px CSS widths; page-wide horizontal overflow absent. Mobile uses stacked, independently scrollable evidence/discussion areas.
- Current integrated candidate visually inspected at 1080px, 768px and 390px. At 768 and 390, document scrollWidth equalled viewport width.
- Overall/Paid switching works with Mini Audit open.
- Show breakdown expands Google Search/Bing Search rows; combined parent values retained.
- Scope chips and metric-header definitions present, including the clarification that the approved “Revenue” bucket heading is Google Search CM1, not booking revenue.
- Mobile Overview visually inspected without page-wide overflow.
- Browser viewport overrides restored after testing.
- This is representative layout coverage, not proof of every device, hover/scroll interaction, or full live persistence lifecycle.

## September 6 production routes

Each dated and latest URL below was opened in the authenticated browser. Every one displayed its expected market title and **6–12 September 2026**. Headout intentionally has no Mini Audit. CSEE/Nordics shared route is an additional route, not an additional market.

| Market | Dated report | Latest | Result |
|---|---|---|---|
| North America | [Sep 6](https://market-notebook.vercel.app/weekly-report-north-america-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-north-america) | Opens; unfinished-week warning |
| Italy | [Sep 6](https://market-notebook.vercel.app/weekly-report-italy-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-italy) | Opens; unfinished-week warning |
| Oceania | [Sep 6](https://market-notebook.vercel.app/weekly-report-oceania-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-oceania) | Opens; unfinished-week warning |
| France | [Sep 6](https://market-notebook.vercel.app/weekly-report-france-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-france) | Opens; unfinished-week warning |
| United Kingdom | [Sep 6](https://market-notebook.vercel.app/weekly-report-united-kingdom-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-united-kingdom) | Opens; unfinished-week warning |
| Iberia | [Sep 6](https://market-notebook.vercel.app/weekly-report-iberia-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-iberia) | Opens; unfinished-week warning |
| CSEE | [Sep 6](https://market-notebook.vercel.app/weekly-report-csee-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-csee) | Opens; unfinished-week warning |
| Nordics | [Sep 6](https://market-notebook.vercel.app/weekly-report-nordics-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-nordics) | Opens; unfinished-week warning |
| East Asia | [Sep 6](https://market-notebook.vercel.app/weekly-report-east-asia-jpn-sk-hk-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-east-asia-jpn-sk-hk) | Opens; unfinished-week warning |
| South East Asia | [Sep 6](https://market-notebook.vercel.app/weekly-report-sea-sin-tha-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-sea-sin-tha) | Opens; unfinished-week warning |
| United Arab Emirates | [Sep 6](https://market-notebook.vercel.app/weekly-report-united-arab-emirates-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-united-arab-emirates) | Opens; unfinished-week warning |
| GCC | [Sep 6](https://market-notebook.vercel.app/weekly-report-gcc-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-gcc) | Opens; unfinished-week warning |
| North Africa | [Sep 6](https://market-notebook.vercel.app/weekly-report-north-africa-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-north-africa) | Opens; unfinished-week warning |
| Rest of MEA | [Sep 6](https://market-notebook.vercel.app/weekly-report-rest-of-mea-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-rest-of-mea) | Opens; unfinished-week warning |
| Benelux | [Sep 6](https://market-notebook.vercel.app/weekly-report-benelux-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-benelux) | Opens; unfinished-week warning |
| South America | [Sep 6](https://market-notebook.vercel.app/weekly-report-south-america-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-south-america) | Opens; unfinished-week warning |
| Mexico & Central America | [Sep 6](https://market-notebook.vercel.app/weekly-report-mexico-central-america-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-mexico-central-america) | Opens; unfinished-week warning |
| Headout | [Sep 6](https://market-notebook.vercel.app/weekly-report-headout-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-headout) | Opens; unfinished-week warning |
| CSEE + Nordics shared shell | [Sep 6](https://market-notebook.vercel.app/weekly-report-csee-nordics-2026-09-06) | [Latest](https://market-notebook.vercel.app/weekly-report-csee-nordics) | Opens; not aggregated |

## Monday 7 September alerts (report week August 30)

Read all 17 market Top/Bottom Slack threads directly. Compared the first five gainers and first five droppers in each frozen August 30 source snapshot to CE IDs in live replies. Each expected CE has Drivers of Revenue Change, Demand RCA and CVR RCA sections. This verifies explanation presence, not a new BQ recalculation of every figure. Smaller markets legitimately have fewer than ten movers.

All 148 expected market CE explanations are present. Parent report hyperlinks read from these threads are explicitly pinned to August 30; CSEE/Nordics both point to the shared report with their market selector. No repost is needed. Headout has a ledger entry but could not be read through the connector, so it remains unverified rather than marked missing.

| Market | Parent alert | Top/Bottom RCA | Missing/Failed RCA |
|---|---|---|---|
| North America | [Verified](https://headout.slack.com/archives/CNSHDD2H1/p1788763129912649) | 10/10 | 0 missing |
| Italy | [Verified](https://headout.slack.com/archives/C045L2WQ79P/p1788763148742609) | 10/10 | 0 missing |
| Oceania | [Verified](https://headout.slack.com/archives/CHKRLFDPU/p1788763168161069) | 10/10 | 0 missing |
| France | [Verified](https://headout.slack.com/archives/CH64TEB71/p1788763187821009) | 10/10 | 0 missing |
| United Kingdom | [Verified](https://headout.slack.com/archives/CKTFHT4AF/p1788763206932419) | 10/10 | 0 missing |
| Iberia | [Verified](https://headout.slack.com/archives/CH2LRMJF2/p1788763226086839) | 10/10 | 0 missing |
| CSEE | [Verified](https://headout.slack.com/archives/CSQ10TALA/p1788763244992909) | 10/10 | 0 missing |
| Nordics | [Verified](https://headout.slack.com/archives/CSQ10TALA/p1788763270636829) | 10/10 | 0 missing |
| East Asia | [Verified](https://headout.slack.com/archives/CQD6220VB/p1788763293761329) | 10/10 | 0 missing |
| South East Asia | [Verified](https://headout.slack.com/archives/C5WFYN82H/p1788763313462979) | 10/10 | 0 missing |
| United Arab Emirates | [Verified](https://headout.slack.com/archives/C046622L80Z/p1788763332061799) | 10/10 | 0 missing |
| GCC | [Verified](https://headout.slack.com/archives/C0889D22PM5/p1788763351735849) | 6/6 | 0 missing |
| North Africa | [Verified](https://headout.slack.com/archives/C0889D22PM5/p1788763364749159) | 8/8 | 0 missing |
| Rest of MEA | [Verified](https://headout.slack.com/archives/C0889D22PM5/p1788763380538529) | 3/3 | 0 missing |
| Benelux | [Verified](https://headout.slack.com/archives/CL13UPZ6V/p1788763389153669) | 8/8 | 0 missing |
| South America | [Verified](https://headout.slack.com/archives/CH2LRMJF2/p1788763404889679) | 9/9 | 0 missing |
| Mexico & Central America | [Verified](https://headout.slack.com/archives/C012949PQ81/p1788763421930179) | 4/4 | 0 missing |
| Headout | [Ledger only; access unavailable](https://headout.slack.com/archives/C0975BGAX0B/p1788765108024799) | Unverified | Not assessed |

The old v2_run_2026-08-30.json has an August 31 timestamp and stale “running” status; it is not a reliable receipt for Monday September 7. September 7 parity manifests and direct Slack reads are stronger evidence. Preserve the existing posted ledger.
