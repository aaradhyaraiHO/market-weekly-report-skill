# Mid-week sidebar release — 10 September 2026

## Scope

User approved the remaining deployment, live Mini Audit verification, access/data
audit and reproducibility work, excluding new CSEE/Nordics aggregation. Existing
shared-page selection is preserved; no combined totals are introduced.

- Left navigation collapses from 196px to 68px on desktop. The right notes panel
  remains visible; the mistaken Hide notes/Show notes implementation is removed.
- Embedded metric headers remain within their data pane, below the toolbar.
- Empty seasonality copy: “Seasonality adjustments will be shown here.”
- No report metric refresh, new alert run, parent-alert repost, storage migration,
  OKR change or change to monthly pages.

## Frozen artifact and local gates

- Source: `.cache/weekly_report/midweek_mini_audit_resilient_release_2026-09-09`.
- Candidate: `.cache/weekly_report/sidebar_release_2026-09-10`.
- Its adjacent receipt verifies all 111 V2 pages preserve every prior payload
  value and order; unrelated files remain byte-identical. Preview notices and
  latest-week routing are retained. Initial activation retained Apps Script 17;
  the live test subsequently exposed and repaired the backend issue below.
- 323 tests passed in the shared checkout, including one unrelated bucket test;
  `git diff --check` passed. Unrelated bucket cleanup is excluded from this commit.
- Desktop/mobile/keyboard/state-preservation checks are detailed in
  `MINI_AUDIT_LAYOUT_FIX_2026-09-09.md`. Production checks are recorded below after
  activation, not inferred from the local mock.

## Preservation and live-test authority

Read-only baseline captures all 29 tabs in current and historical workbooks:
`.cache/weekly_report/mini_audit_followup_backend_2026-09-09/sidebar-before-*`.
The user explicitly authorized a dummy message in any CSEE CE. The test will be
clearly labelled verification-only, with no business finding or action requested.
Selected CE: 3286, Temple of Poseidon & Cape Sounion, week August 30.

## Fresh data audit

The prior statement that the completed-week Headout September goal was missing
was stale. Its published goal is $14,217,164; a fresh bounded BigQuery query of
`analytics_reporting.revenue_goals` confirms the same total across the 25 approved
September Market rows. Combined Entity rows are not added to Market rows.
The dated September 6 incomplete preview still lacks the goal sidecar.

Optional Google/Bing fields cannot safely be blanket-backfilled from today's
source without refreshing frozen parent metrics. Date-constrained source queries
captured 30,808 TY and 23,253 LY CE-week rows. Example CE3286 / August30: published
paid conversions 12, current BQ 14; published CM1 246.9136, current BQ 272.475369.
No frozen values were overwritten. Capture location:
`.cache/weekly_report/platform_source_audit_2026-09-10`.

## Production results

Frontend `be90b3c` is live as deployment
`dpl_7hwEu84YY4fpred9HD8VsihyGR4F` at `https://market-notebook.vercel.app`
(immutable deployment `https://market-notebook-rmfjwjzer-headout.vercel.app`).
All 111 V2 pages received the presentation-only upgrade. All 38 latest and
September 6 routes were opened in the production browser: 17 markets, Headout
and the existing CSEE/Nordics shared page, each at both routes. All passed header,
navigation and week/preview checks. Latest is August 30–September 5; September
6–12 remains explicitly an incomplete-week preview. CSEE/Nordics aggregation
was deliberately not changed.

### Live Mini Audit regression and repair

The authorized dummy test used CE3286, CSEE, week August 30:
https://headout.slack.com/archives/CSQ10TALA/p1789016453095459

One new verification-only Mini Audit discussion and two replies were posted.
This is not a market-alert parent or a repost. Independent Slack reads confirmed
the exact parent and both replies. No operational action was approved; the
test-only suggested check was dismissed with its source retained.

The second reply exposed a real v17 failure: the same-week starter moved forward,
earlier exact sources were excluded, and the unchanged human scan cursor plus
unchanged source count could incorrectly return `current` for a different reply.
The UI then said “Discussion updated” while retaining old summary content.

Commit `1e89137` fixes the boundary and freshness checks:

- Continuing the same weekly discussion preserves its first saved post.
- Exact sources with a matching immutable thread binding and exact market/CE/week
  remain eligible, including sources excluded by the prior moving boundary.
- Summary freshness includes app-relayed reply timestamps independently of the
  human scan cursor, so unread paginated human replies cannot be skipped.
- Other-week, other-thread and unproven legacy sources remain excluded.

New regression first failed against v17, then passed with the fix. Full baseline:
323 tests passed in the shared checkout (322 approved tests plus the unrelated
bucket cleanup test). Whitespace gate passed. Only the two repair files were
committed; unrelated cleanup remains unstaged.

Backend immutable **version 18** is active on the same existing endpoint;
SHA256 `992ac1d5fb28c1777b9e5ae3310f4771e606a39bb7cd1940343cbcd36afc37c0`.
Manifest, properties, other deployments and original editable HEAD were preserved.
First verification GET was stale, so an independent fresh GET and frozen-source
read confirmed v18; activation was not repeated. Rollback is v17. Receipt:
`.cache/weekly_report/mini_audit_reply_cursor_2026-09-10/activation-receipt.json`.
The frontend artifact receipt records its original v17 source reference; this
backend-only repair supersedes that reference without changing frontend assets.

On the exact live frontend/backend pair, summarization then produced and saved:

> The Slack discussion was a dummy test for CE 3286 to verify Slack message
> delivery and summary persistence.

The saved summary also states no business change/action is requested. It cites
all three exact Slack source references, including the new reply. Its timestamp
is `2026-09-10T05:14:52.327Z`, version 7, with source cursor
`1789016810.756329`. Reload showed identical visible text. A repeat summary
changed neither the summary nor any backend/history cell value. Open work and
pending suggestions remained zero. Initial Actions read timeout recovered via
Retry; this release does not promise zero network/transient failures.

The test covers a genuine app-to-Slack reply and real AI/storage integrations,
not a simulated source. It does not add a new human-authored Slack-client reply;
the human scanner path has regression coverage and prior historical-source
verification.

### Preservation and interface evidence

Read-only comparison across all 29 tabs confirms every pre-test row and header
is preserved; historical workbook values are exactly unchanged. The repeat-run
backend values are also exactly unchanged. Evidence:
`.cache/weekly_report/mini_audit_followup_backend_2026-09-09/sidebar-final-preservation.json`
and `sidebar-repeat-preservation.json`.

Live desktop collapse preserved an unsent draft, changed rail width 196→68px,
and kept the notes pane visible. Keyboard expansion worked; the test draft was
cleared without saving/sending. At 1280px after CE scrolling, the copied header
top and CE data pane top were both 157px, exactly below the toolbar; the header
was horizontally contained in the data pane. No Hide notes control remains.
The seasonality placeholder was confirmed live in North America. Local mobile
checks at 390/768px are recorded in the layout report. Live mobile emulation could
not be independently repeated: the browser viewport override returned without
changing the actual CSS viewport. Do not represent those attempts as live mobile
passes; all temporary overrides were reset.

Headout's existing Monday summary and Top/Bottom parents were read directly in
authenticated Slack. Both point to the dated August 30 report; its September
target is present ($14.2M rounded). The Top/Bottom parent shows 10 replies, but
their individual RCA bodies were not re-audited in this slice. Parent:
https://headout.slack.com/archives/C0975BGAX0B/p1788765108024799

Alert ledger SHA256 remains
`14ad1074ae3bbd3457cfd0d1221d0d1b494b926a489702e645df80926151fe4f`.
No report metrics, existing comments, alert parent messages, OKRs, monthly pages
or original review history were overwritten.

### Still open, not silently completed

- Historical Google/Bing enrichment needs a coordinated frozen-data refresh;
  today's BigQuery operands differ from the published parent metrics. Future
  snapshot capture includes the optional platform operands, but old reports
  were not blanket-backfilled.
- The September 6 Headout incomplete preview still lacks its goal sidecar; the
  completed-week Headout target is verified present. The generic future Headout
  goal producer needs an explicit all-market path rather than a literal market
  filter for “Headout (all markets)”.
- Live mobile breakpoint verification remains unconfirmed as explained above.
- CSEE/Nordics true aggregation is deferred by the user, not part of this release.
