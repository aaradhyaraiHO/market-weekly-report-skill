# Levers disclosure — 10 September 2026

Status: implemented locally, not committed, pushed or deployed.

Levers visibility starts collapsed. Its whole header is a native HTML summary
that expands both existing subsections together. Tagged-lever and prepurchase CE
counts remain visible when closed. V1, calculations, bucket membership, report
payloads, notes, backend and alert delivery are unchanged.

## Scoped interface review

Mode: full. Scope: Levers visibility disclosure and its existing child tables.
Framework: plain HTML/CSS/JavaScript with existing Oak/Eevee tokens. The change
matches the native disclosure used by Iteration / Untapped. No new styling
framework, runtime dependency or animation was introduced.

| Category | Evidence inspected | Result |
| --- | --- | --- |
| Typography | Closed and expanded header at 1024px and actual 390px CSS viewport | Existing title/copy styles retained; count wraps without clipping |
| Surfaces | Mouse, Enter/Space, focus ring, table scroll containment | Full header is a touch target; visible 2px focus ring; no page overflow at 390px |
| Animations | New CSS and native disclosure interaction | Instant state change; no new animation, so 10%-speed replay not applicable |
| Icons | Closed/open state in browser | Existing static right/down chevron convention retained |
| Performance | Template diff and repeated toggles | Native disclosure retains rows in DOM; no fetch or new event handler on toggle |

## Change

| Severity | Location | Before | After | Why |
| --- | --- | --- | --- | --- |
| MEDIUM | `scripts/weekly_report/template/report_v2_template.html:303`, `:1001` | Levers card always expanded, with no disclosure affordance | Closed native details/summary, visible row counts and chevron, hover/focus feedback, wrapping header with minimum 44px target | Progressive disclosure and minimum hit area: reduce page length without hiding the section's existence or losing keyboard access |

## Considered but rejected

| Location | Candidate | Rejected because |
| --- | --- | --- |
| Levers card | Custom JavaScript accordion and animated height | Native details already supports keyboard and accessibility semantics without added state or motion |
| Two subsections | Separate collapse controls | User asked to collapse the whole card; nested controls add unnecessary interaction |

## Verification

- Targeted tests: `python3 -m unittest discover -s tests/weekly_report -p test_levers_disclosure.py` — 3 passed. Covers empty and populated data, escaped names, unchanged source objects, default closed markup, counts, focus and mobile styles.
- Full suite: `python3 scripts/weekly_report/verify_baseline.py` — 338 passed, including V1 baseline/parity tests.
- `git diff --check` — passed.
- Mechanical previews of the exact existing North America, North Africa and Headout August 30 artifacts differ only in the Levers renderer and added disclosure CSS. All embedded report data remains byte-identical.
- Browser: North America closed by default, mouse-open shows all 22 rows and both headings; Enter closes, Space opens, Enter closes again. Focus remains on summary with visible 2px outline.
- Browser: actual 390×844 CSS viewport has document scroll width 390; open table scrolls within the card. Closed header measures 360.8×151.5px. Temporary browser viewport override reset.
- Browser: Headout closed header shows 336 PP CEs; expansion retains all 336 rows. North Africa retains its two rows and the empty tagged-lever message.
- Empty-both-sections scenario verified in runtime tests, not a live market.
- Not verified: production deployment, physical devices, screen-reader audio, or live note/Slack integrations. None was changed or invoked by this UI action.

Verdict: Approve the scoped local UI patch. Production remains unchanged until
explicit deployment approval.

Skills used: weekly-market-report-v2 for frozen-data/V1 preservation and
make-interfaces-feel-better for matching disclosure styling, focus and touch behavior.
