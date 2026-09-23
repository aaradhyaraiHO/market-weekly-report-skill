# CE Memory UX patch — 21 September 2026

Status at initial review (September 21): implemented and verified locally. The user authorized commit, push and production deployment on September 23; completed live results are recorded in the [production release closeout](ce-memory-ux-release-2026-09-23.md).

## Scope and coverage

Full review within the four reported CE Memory interactions. Vanilla JavaScript and existing plain CSS tokens; no new styling framework. Preview used the frozen September 13 North America report with the repository's simulated Mini Audit service. It did not contact Slack, Sheets, or the production review backend.

| Category | Evidence inspected | Result |
| --- | --- | --- |
| Typography | Inline source/author/date labels and original records at desktop and 390px width | Clear; wrapping stays within the page |
| Surfaces | Citations, original-record focus, Refresh, disclosures | Exact record highlighted; citations 44×44px, Refresh 76×44px |
| Animations | Citation navigation and native disclosures | Immediate navigation replaces smooth scrolling; no animation added, so slow-motion inspection not applicable |
| Icons | Existing native disclosure markers | Retained; keyboard collapse verified |
| Performance | Pending/completed refresh, in-flight deduplication and simulated failure/retry | Only memory read requested; cached records preserved on failure; no production latency claim |

## Changes

| Severity | Location | Before | After | Why |
| --- | --- | --- | --- | --- |
| MEDIUM | `scripts/weekly_report/review/review-view.js:685`, `review-view.css:488` | Similar notes lacked inline provenance | Each passage labels every contributing source, author and date; metadata and text wrap | Distinguishes legitimate records without changing their wording or merging differing notes |
| MEDIUM | `scripts/weekly_report/review/review-view.js:417`, `:724`, `review-view.css:501` | Citation opened the group heading | Each citation carries the original ID; opens, focuses and scrolls to that record with a visible highlight | Arrives at the selected evidence, including a separately clickable citation for each identical-text source |
| MEDIUM | `scripts/weekly_report/review/review-view.js:395`, `:413`, `:727` | Refresh reloaded unrelated resources with no memory-specific progress | Independent memory read, pending/updated/retry feedback, disabled pending button, coalesced clicks; previous records remain on failure | Makes request state explicit and reduces unnecessary reads; errored cached reads remain retryable |
| MEDIUM | `scripts/weekly_report/review/review-view.css:485` | Small citation/Refresh targets | At least 44px tall with existing purple hover/focus tokens | Easier pointer/touch activation and keyboard focus visibility |

## Considered but rejected

| Location | Candidate | Rejected because |
| --- | --- | --- |
| History prose | Semantically merge similar notes | Would risk discarding different saved accounts; all originals must remain |
| Disclosure defaults | Expand every week and all sources | Adds unnecessary reading volume; retained current disclosure defaults |
| Undated sources | Infer review week from edit date | Edit time is not proof of review-week ownership |

## Verification

- `node --check scripts/weekly_report/review/review-view.js`: passed.
- `node tests/weekly_report/js/review_memory_ux_runtime.cjs`: passed. Exercises exact-record focus, disclosure persistence, escaped metadata, separate citations for identical text, preservation of differing text, refresh deduplication, failure preservation, retry and stale CE response isolation.
- `python3 -m unittest discover -s tests/weekly_report`: 401 tests passed.
- `python3 scripts/weekly_report/verify_baseline.py`: passed (401 tests).
- `git diff --check`: passed.
- Browser: expanded CE Memory, opened August 9 history, clicked source 2. Focus became `Source 2 · Slack summary · Discussion 1`, record `summary:chi-week-1`, visibly highlighted within desktop viewport.
- Browser: Refresh showed “Refreshing CE history… Previously loaded records remain below.” then “History updated”.
- Mobile 390×844: same source focus verified; page scroll width 390px, no horizontal overflow; measured citation/Refresh sizes above. Temporary viewport reset afterward.
- Keyboard Enter collapsed the historical week.
- Console: one pre-existing browser-extension content-script exception; no report-script errors observed.

No notes, summaries, source rows, metrics, buckets, live reports, delivery records, or alerts were modified. Existing unrelated `alert/posted_ledger.lock` left untouched.

Verdict: **Approve for the local UI patch**. Not verified: deployment/live behavior of this new version, screen-reader announcement quality, physical touch, new-save-to-memory against the real backend, or production backend reliability. These UI improvements do not claim to solve a backend outage.

The `make-interfaces-feel-better` skill guided provenance, focus, wrapping and touch-target improvements using the existing CSS system. The `weekly-market-report-v2` skill kept report data and saved history unchanged. Browser-verification skills guided desktop/mobile preview checks, performed through CUA.

## September 23 release preparation

- Fresh full suite and baseline: 401 tests passed in each; diff check passed.
- Production resolved to `dpl_9UFjfeRxkNDwyrDz9H1R2cupp1Qs`, matching the verified complete `.cache/weekly_report/v2_package_2026-09-13/notebook` artifact.
- Separate staging directory: `.cache/weekly_report/ce_memory_ux_release_2026-09-23/notebook`.
- Strict byte comparison proved only the canonical view JavaScript and CSS changed across 123 current/historical report pages. All remaining 143 notebook files, API implementations, Headout pages, report data and non-UI report code remain unchanged.
- Preservation and 40-route browser manifests retained beside the staged notebook. No report generation or alerts are part of this release.
