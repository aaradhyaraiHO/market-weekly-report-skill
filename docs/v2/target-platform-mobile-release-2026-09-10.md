# Target, platform-history and mobile release — 10 September 2026

## Live release

- Main site: https://market-notebook.vercel.app
- Deployment: `dpl_FCiGn87uuT2tySE5q2hyPTiqN8sc` (READY; promoted).
- Immutable URL: https://market-notebook-bsk641h4e-headout.vercel.app
- Artifact: `.cache/weekly_report/target_platform_mobile_release_2026-09-10`.
- Previous deployment retained: `dpl_EDhKpPA3QTDVBRKYrD7GBT717vAC`.
- Backend unchanged: existing v19. No notes, Slack posts, actions, Sheet writes or summary-generation calls in this release.
- CSEE + Nordics retain the existing shared page with separate datasets. No aggregation change.

## Headout September goal — fixed

The [Final H2 Goals tab](https://docs.google.com/spreadsheets/d/1WWFfm855kb-_WMbo5_LQOmlagZYMMOJEKhoGpp-TPFM/edit?gid=1732201896#gid=1732201896), row 27, confirms the September total **$14,217,164**. It equals the BigQuery sum of 25 approved Market-grain rows. Region/subtotal rows and CE targets are not added to that total.

The previous builder filtered the warehouse for a literal Headout market. Headout now queries the whole business, requires approved Market-grain goals, and preserves its freshly queried CE targets when generated alone or alongside partial market sidecars.

Only the [September 6 dated preview](https://market-notebook.vercel.app/weekly-report-headout-2026-09-06) received the goal repair. Its live UI shows $14.2M goal, $13.9M projected close (98%), and revenue through September 9. The preview warning remains. Forecasting uses actual MTD plus the latest four **complete** weeks' run rate; future days and the incomplete week are not treated as completed evidence. The completed August 30 report retains its existing September 5 pacing inputs.

## Historical Google/Bing enrichment — partial, not fully closed

`backfill_platform_history.py` checks every stored paid operand/ratio against a bounded source extract before adding missing platform operands. It only fills null display values; it never replaces existing numbers, rankings or comparisons. Google/Bing ratios are recomputed from platform operands, not averaged or rescaled.

Across the 36 dated August 30 / September 6 market and Headout reports, **4,875 CE/report combinations** gained missing values. Current aliases and the existing CSEE + Nordics wrapper received the same additive enrichments. Across all affected copies, 753,484 numeric nulls were filled. These are cell counts, not unique CEs.

**Remaining:** 8,765 source-drift CE-week comparisons across 2,056 dated CE/report combinations were withheld. These can overlap the combinations that gained other historical weeks. There were zero snapshot-to-published-parent mismatches. Empty weeks with no frozen paid evidence remain unavailable rather than being invented as zero.

The warehouse reports Google/Microsoft source tables created on September 10. A read-only September 7 time-travel query returned 404; the dataset itself has a 168-hour time-travel setting. Current source values demonstrably differ from the frozen run, so they are not an exact historical substitute. For example, CSEE CE 3286 reconciled for 22 of 24 TY/LY weeks; two were withheld.

To close the remaining backfill, obtain the original run-time Google/Microsoft Search operands (including Google coupon/wallet, offline revenue and impressions) keyed by stable CE ID and week, then rerun the guarded enrichment. Do not refresh report totals to force reconciliation. Future snapshots already retain complete platform operands.

Receipts:

- `.cache/weekly_report/target_platform_mobile_release_2026-09-10_platform_receipt.json`: source hashes, counts and exact unresolved CE/page list.
- `.cache/weekly_report/target_platform_mobile_release_2026-09-10_goal_receipt.json`: target authority and non-goal preservation.
- `.cache/weekly_report/target_platform_mobile_release_2026-09-10_final_receipt.json`: 111 V2 page hashes and allowed-change audit.

## Full scoped interface review

Scope: Overview navigation, All CEs search/detail, Mini Audit queue/data/notes and expanded paid metrics at mobile/tablet widths. Existing plain HTML/CSS/JavaScript and shared purple/white tokens were retained. This is responsive browser verification, not a physical-device or broad accessibility certification.

| Category | Evidence inspected | Result |
| --- | --- | --- |
| Typography | Live 390px and 768px layouts, long CE title, metadata wrapping, numeric tables | No new clipping; tabular numerals preserved |
| Surfaces | Drawer close button, navigation, Mini Audit controls, queue overlay and pane boundaries | Tap-target fixes below; no horizontal page overflow |
| Animations | No animation or loading-state implementation changed | Timing/10%-speed motion replay not verified; outside this static sizing patch |
| Icons | Close icon and existing navigation glyphs in live screenshots | Existing assets/states retained; close target no longer shrinks |
| Performance | Diff review: CSS-only sizing, no new JS handlers or dependencies | No new runtime dependency; no error logs observed in live checked tab. Broad performance benchmarking not performed |

### Minimum hit area

| Severity | Location | Before | After | Why |
| --- | --- | --- | --- | --- |
| MEDIUM | `scripts/weekly_report/template/report_v2_template.html:672`; `scripts/weekly_report/review/review-view.css:476` | Navigation 42px, several mobile controls 40px; CE close button shrank to about 22px wide | Mobile controls at least 44px high; CE close has fixed 44px flex basis/minimum width; metric toggles at least 44px wide | Easier touch interaction without overlapping invisible targets or changing desktop density |

### Considered but rejected

| Location | Candidate | Rejected because |
| --- | --- | --- |
| Mini Audit data/notes layout | Redesign into different navigation or hide notes | Existing user-requested structure works; a new information architecture is outside scope |
| Cards and drawers | Replace shared shadows/borders and typography | Existing styling is consistent; cosmetic churn would not improve the identified mobile issue |
| Frozen platform evidence | Refresh totals or scale platform values to force a match | Would mix source generations and violate preservation of published metrics |

### Verification and verdict

- `python3 -m unittest discover -s tests/weekly_report -p 'test_*.py'`: **335 tests passed**. Tests use mocked integrations; no external sends.
- `git diff --check`: passed.
- Final artifact audit: all **111 V2 pages** inspected; **137 unrelated files** byte-identical. Only goal fields on the named Headout preview and null-to-number platform additions changed. Every latest alias remains an exact copy of its August 30 dated report. Preview warnings retained.
- Alert ledger SHA-256 remains `14ad1074ae3bbd3457cfd0d1221d0d1b494b926a489702e645df80926151fe4f`.
- Authenticated live Headout preview: target and cutoff visible, preview warning present.
- Live North America CE 2567 at **390×844**: document width/scroll width both 390; navigation and tested Mini Audit controls measure 44px. Queue overlay bounds 0–390.
- Live North America at **768×1024**: document width/scroll width both 768; existing note, seasonality comment and saved Slack summary visible. After expanding Paid ROI, visible metric header bounds 222–259.75 lie inside the CE pane (222–682.80). No browser error logs in the checked tab.
- Packaged mobile drawer: close control 44×44, contained in the 390px viewport; All CEs search and CE opening work.
- Live CSEE CE 6855 at 390px: All CEs search, drawer opening and closing work; close control measures 44×44 at x=328–372, with document scroll width 390. Temporary viewport override reset afterwards.
- Live CSEE CE 6855: newly filled Google Search ROI **15.80%**, Bing **0.00%**; combined parent **9.42%** unchanged. CE 2567 still honestly shows unavailable current platform ROI where source drift prevents a fill.
- Anonymous HTTP and CLI checks reached authentication pages, not report assets. They are explicitly **not** counted as hash-verification passes. Production was checked through the authenticated browser and the exact promoted deployment ID. Per-page authenticated remote byte comparison of all 111 files was not performed.

Verdict: **Approve the scoped interface patch**; physical-device coverage, broad performance profiling and motion replay are not claimed. Headout goal and mobile work are complete. The historical backfill remains **partially blocked on exact original source operands**, not marked complete.

Skills used: weekly-market-report-v2 (frozen-data parity), Google Drive / Google Sheets (read-only goal authority), make-interfaces-feel-better (mobile sizing and scoped review), sites-hosting (retain the existing Vercel hosting workflow).
