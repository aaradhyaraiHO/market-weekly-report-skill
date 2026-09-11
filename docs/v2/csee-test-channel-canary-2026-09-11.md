# CSEE real test-channel canary — 11 September 2026

## Result: PASS for the bounded canary, not full production activation

The user designated `#revenue-alert-testing` (`C0B6U94PGJ0`). The existing bot's
membership and read access were verified. The test used CSEE for the completed
30 August–5 September week, with no BGM mentions and TEST ONLY labels.

The canary called the real shared builder, V2 renderer/parity gate, target query,
RCA helper and frozen delivery engine. Its small isolated harness used a preview
origin and separate state, not the production runner's canonical-host/all-market
gate. That gate was neither disabled nor marked passed.

## Evidence

- Fresh read-only BigQuery build: 1,078 CEs. V1/V2 parity passed with no gate
  warnings. Google/Bing current and historical source nulls were flagged and
  retained, not replaced. Source completeness is not implied by a parity pass.
- Monthly goals were fetched. Existing pinned MMP and same-week
  `_okr_results_v2_2026-08-30.json` evidence was reused, not refreshed.
- All ten selected Top/Bottom CE RCA entries were freshly prepared before any
  Slack send. Two parents and ten RCA replies were generated.
- Preview deployment: `dpl_B3obrUKuR1NzwdxopJFjLFRRc2vT`,
  `https://market-notebook-lt6w9jekm-headout.vercel.app`.
- Authenticated preview alias:
  `https://market-notebook-review-preview.vercel.app`.
  Previous preview target retained for rollback:
  `https://market-notebook-n5d07y1zg-headout.vercel.app`
  (`dpl_CiKhHAWghgqhK97x1zngfkZoBvw9`).
- Signed-in browser verified both `/weekly-report-csee` and
  `/weekly-report-csee-2026-08-30`: test label, CSEE/week, and complete original
  script/style fingerprints match the staged artifact:
  `76a6ab20a7a4b2deddbe458f6c20ed2f65029aea5a0ab3f42d1660d795b4dd50`.
- Slack parent timestamps: `1789114186.193709`, `1789114186.585439`.
  [Summary](https://headout.slack.com/archives/C0B6U94PGJ0/p1789114186193709)
  and [movers/RCA thread](https://headout.slack.com/archives/C0B6U94PGJ0/p1789114186585439).
- Fresh API reads verified all 12 messages. A repeated delivery invocation was
  instrumented to fail on any attempt to post; it passed without a write. A
  separate verify-only invocation also passed.

## Defect found and fixed

The first final read-back failed after successful delivery because Slack returns
emoji as colon aliases and escapes ampersands. The frozen plan and journal were
preserved; no parents or replies were replayed to recover.

`safe_delivery.matches` now tolerates the known alert/RCA emoji aliases and
Slack's three supported text entities only within text objects. It does not
rewrite payload hashes, strip content, ignore numbers, or relax URL/mention
identity. Unknown formatting transformations still fail closed.
See [Slack's text format contract](https://docs.slack.dev/messaging/formatting-message-text/).

Two regressions cover normalized read-back/retry and rejection of changed
amounts, links, mentions and non-text fields. Full suite: **391 tests passed**.

## Preserved and still unverified

- Production alias/deployment and all production reports were untouched.
- Only the two CSEE pages changed in the preview package; 245 other staged
  notebook files were byte-identical. No Mini Audit note, summary, action, Sheet
  or backend mutation was part of this canary.
- Production ledger SHA-256 stayed
  `14ad1074ae3bbd3457cfd0d1221d0d1b494b926a489702e645df80926151fe4f`.
- Test bundles, browser observations, journal, ledger and receipt are isolated
  under ignored `.cache/weekly_report/canary_2026-09-11/`. Keep them for retries;
  do not clear them to repeat a test.
- All-market + Headout generation, canonical production deployment/link gates,
  fresh OKR generation and a new Mini Audit write/summary on the exact combined
  release are not established by this single-market canary.
- Headout private-channel `groups:history` remains unresolved. Scheduling stays
  paused; this result does not authorize production activation.
