# Tools navigation release — 2026-10-01

Production: https://market-notebook.vercel.app

- Deployment: `dpl_9nQqc9izA4ZKd2B24bpcaoiEcrR3` (project `market-notebook`, never Central Tracking).
- Verified complete notebook: `.cache/weekly_report/tools_nav_release_2026-10-01-final/notebook`.
- Receipts alongside it: `deployment_receipt.json`, `preservation.json`, `initial_live_verification.json`, `live_verification.json`.
- This is the newer complete production baseline; do not seed a later release from the September 28 notebook without preserving this navigation.

Navigation-only additions to all 268 HTML pages. All original page text, scripts and data preserved; 17 non-HTML files (including Mini Audit client/proxy, auth, state and configuration) unchanged. No generation, data refresh, alerts, note writes or permission changes.

Tools contains OKR Tracker, Churn Tracker, All CEs Trend and CE Trends. New CE Performance and Seed+/CE opportunity remain omitted until URLs are supplied.

Verification: 407 weekly tests and 2 monthly Tools tests pass. Signed-in browser checks passed on 38 current routes (all 17 monthly reports, 19 weekly routes, both homepages). Archive-only follow-up changed 94 old V1 pages to keep the existing jump bar below Tools and behind its dropdown. Six final-production route checks passed, including current and historical weekly, monthly, both homepages and the corrected archive. Desktop/mobile menu and sticky-position checks passed locally. This is not a new Mini Audit backend end-to-end test.

Weekly and monthly generation templates have matching local Tools components. Those source changes are not yet committed/pushed. The monthly checkout contains unrelated user changes: isolate only the navigation diff when committing; do not sweep the checkout. The scheduled source-verification gate must not be bypassed.

## Weekly source verification — 2026-10-05

The weekly navigation changes are included in the commit containing this entry.
Fresh verification passed all 407 weekly tests and the full baseline verification.
The final staged whitespace check noted one harmless blank line at EOF in
`notebook_tools.py`, retained to preserve byte parity with the monthly copy.
The Ledger output is byte-identical to the previous
committed renderer after removing the approved menu fragment and wrapping class.
No metric, bucket, alert or source-query formulas changed. The monthly checkout
is not committed or modified by this weekly source closeout.

The October 1 artifact is no longer the current production baseline. Production
now resolves to the October 2 monthly release. The preservation regression found
during this check is documented in `release-blocker-2026-10-05.md`; do not deploy
from either old artifact without resolving that regression.
