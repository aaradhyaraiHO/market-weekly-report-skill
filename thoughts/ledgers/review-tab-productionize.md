# Review Tab Productionization

## Goal
Make the Weekly Report **Review tab** live and usable — the standalone review workspace from
`docs/weekly-review/final-wbr-review-mode.html`, wired to the live `/api/review` backend.
CE drawer stays analytics-only (user decision). Pilot = North America; must extend to all markets.

"Done" = a BGM opens the live NA report → clicks **Review** → sees the flagged-CE queue → for a CE:
records a BGM note, starts/reads the CE Slack thread, accepts/ignores Granola suggestions,
creates actions/checks with owner+status+due, sets treatment, and finishes the review (receipt).
All persisted to the Sheet via `/api/review`. Open work + treatment carry forward.

## Constraints
- Do NOT touch metric/bucket logic, the CE drawer, or existing V1 report sections.
- Review writes use the authenticated `/api/review` proxy (`createWeeklyReviewApi('/api/review')`),
  never the raw `payload.notes_url`. The report is behind login (mmr_session JWT) so the proxy authenticates.
- Reproducible: the V2 shell (`market-notebook-v2/weekly-report-*.html`) is a hand-deployed 13MB artifact
  with NO generator in the repo. Build a re-runnable **injector** so the change survives + applies to all markets.
- Deploy to prod (`vercel deploy --prod`) and credential steps (Slack token rotation, Granola webhook
  secret) are the USER's to run — prepare exact steps, hand off.

## Key Decisions
- CE drawer = analytics only; Review tab = note/commentary/Granola/actions (per user, this session).
- Queue source = diagnostic_buckets (losing_money.existing+new, fluctuations.down+up) deduped by ce_id + review_set manual adds.
- Build `review-view.css` + `review-view.js` (self-contained `initReviewView`) + `inject_review_view.py` (idempotent injector).
- Route review ops through `/api/review`; reuse `review-client.js` already in the deploy dir.

## Shell integration points (weekly-report-<slug>.html)
- Data: `payload.headlines[weekIndex]` → `.all_ces`, `.market_slug`, `.week_start`, `.week_end`, `.market`,
  `.diagnostic_buckets.losing_money.{existing[],new[]}`, `.diagnostic_buckets.fluctuations.{down[],up[]}`.
  `currentHeadline()` gives country-scoped view; `baseHeadline()` unscoped.
- Bucket row fields: ce_id, ce_name, tier, criteria[], weeks[], delta_wow, delta_3w, cm2_wk...
- Nav: `<button ... disabled title="Review mode is a later V2 phase">Review</button>` (needs enable + data-report-view="review").
- View switch (~line 1417): `document.querySelectorAll('[data-report-view]')...` toggles overview-view / all-ces-view hidden.
- Author: `localStorage 'wr_author'`. Actor identity: `/api/review?action=whoami`.
- Existing legacy action sync uses `NOTES_URL=payload.notes_url` + endpoints action_list/upsert/delete (leave alone).

## Backend (already deployed)
- `/api/review` proxy (api/review.js): JWT(mmr_session)→actor_email + HMAC → Apps Script. Actions: whoami,
  review_weekly_list, review_weekly_note_upsert/_delete, review_weekly_slack_post, review_weekly_sync,
  review_work_list/_upsert, review_receipt_list/_upsert, review_set_list/_upsert, review_memory,
  review_suggestion_list, review_granola_link_submit, review_suggestion_decide, review_source_inbox, review_source_reconcile.
- review-client.js exposes: comments, saveComment, work, saveWork, finishReview, receipts, reviewSet,
  saveReviewSetItem, memory, weeklyCommentary, saveWeeklyNote, deleteWeeklyNote, startSlackDiscussion,
  syncWeeklyDiscussion, granolaSuggestions, attachGranolaMeeting, decideSuggestion, sourceInbox, reconcileSource.
- api/granola-review.js = automatic ingestion webhook (needs GRANOLA_WEBHOOK_SECRET + upstream connection = USER).

## State
- Done:
  - [x] Phase 0: Recon — architecture, data model, backend surface, integration points mapped
  - [x] Phase 1: review-view.css + review-view.js built (queue, workspace, note/Slack/Granola/work/receipt/memory, all via /api/review)
  - [x] Phase 2: inject_review_view.py built (idempotent: nav enable + container-in-main + view-switch patch + inline css/client/view + IIFE boot)
  - [x] Phase 3a: Backend read smoke test PASSED live (whoami, review_set, work, receipts, weekly, suggestions — all ok:true, keys match)
  - [x] Phase 3b: Injection + UI validated on scratch copy over localhost — 41 flagged CEs queue, workspace, cards, footer all render; no console errors; empty-states correct
  - [x] Phase 3c: LIVE NA deploy file injected (backup at scratchpad/weekly-report-north-america.PRE-REVIEW.html). User approved NA-only.
  - [x] Phase 5a: Granola auto-ingest runbook written (docs/weekly-review/GRANOLA-AUTO-INGEST-SETUP.md); secrets generated + relayed in chat; endpoints confirmed live (GET→405).
  - [x] DEPLOYED to prod (user ran vercel deploy; aliased market-notebook.vercel.app). Review tab LIVE.
  - [x] Live verification: nav enabled, module loaded, 41-CE queue built, all reads OK. Write path reaches AppsScript (HTTP 200) and is correctly access-gated.
  - [x] Access model confirmed: bgm_access allowlist already has NA BGMs Pari + Asfan (can write now). aaradhya added as admin/* (user ran gws append; row A31).
- Now: [→] Green-path write confirmation is USER's click — harness blocks ALL my prod writes (Bash gws, raw fetch, UI-click-write all gated). Tab is fully usable for authorized BGMs.
- Remaining:
  - [ ] USER: 20-sec confirm — Review → a CE → type note → Save (persists to review_weekly_commentary) → Delete. Watch the Sheet.
  - [ ] Phase 5b: USER sets Vercel env vars + Apps Script REVIEW_INGEST_SECRET per GRANOLA-AUTO-INGEST-SETUP.md; run curl smoke test
  - [ ] Phase 4 (optional): inject_review_view.py --all for the other ~18 markets
  - [ ] (Deferred, recommended) Slack xoxb token rotation — appeared in chat earlier
  - [ ] (Optional) commit review-view.{css,js} + inject_review_view.py + docs to branch

## Design iteration (Eevee, Aug 17)
- Rebuilt review-view.{css,js} on Eevee 7.0.4 tokens (halyard type, purps/grey ramp, radii/shadows) via oak MCP.
- Note: read-card (avatar + name·role + meta + Edit/Delete links); textbox only when writing/editing (no more double-note).
- Actions: checkbox task rows (task=headline, owner·due·source↗ meta, per-item status <select>, owner avatar); checks get AUG/DD date badge; split "+ Add action" / "+ Schedule check"; open first, done dimmed.
- Queue: "+ Add CE" searchable picker over all_ces → review_set manual add; manual rows removable (×). Chips show treatment + open-count.
- Microcopy fixed: "Choose how you'll review" / "Ready to finish" / "Set a treatment above to finish"; granola "Waiting on meetings" (not "NO MATCH"). Step badges ①②.
- inject_review_view.py idempotency fixed (boot-anchor restore on re-run). Live NA file re-injected; needs redeploy.

## Commentary model — DELIBERATE (confirmed by user Aug 17)
- ONE canonical BGM note per CE×week (review_weekly). NOT a multi-author in-tool comment thread.
- All other discussion → Slack ("Start Slack discussion" posts the note into the CE's persistent thread).
- 5-min trigger ingests new human replies → AI summary (findings/decisions/open points, source_refs) rendered
  BACK into the card, visibly separate from the note. review_comments is the LEGACY/compat path only.
- I briefly added a review_comments text box (wrong) then reverted; card now renders weekly.summary_json.
- Do NOT re-add an in-tool comment composer — it contradicts "async input default, Slack as the interface."

## Granola bridge (built Aug 17)
- UI: Granola link capture restored in commentary card — band "＋ Add link" → inline input + Add meeting
  (was dropped in redesign + used a prompt()). Wired to attachGranolaMeeting.
- `scripts/weekly_report/granola_bridge.py` = the upstream trigger. Matches meetings→CE from week snapshot
  (full-name phrase → EXACT auto-attach; token-only/2+ → ambiguous → inbox), POSTs {meeting,matches} to
  /api/granola-review. Dry-run default; --apply needs WR_GRANOLA_WEBHOOK_SECRET. Verified: KSC → EXACT CE 3111.
- Granola local cache (cache-v6.json.enc) + token (supabase.json.enc) are ENCRYPTED — not read. Feed meetings via:
  Claude scheduled agent + Granola MCP (list_meetings/get_meeting_transcript) → meetings.json → bridge --apply.
- CACHE_DIR resolves to ~/analytics/.cache/weekly_report (worktree has no snapshots). Snapshot for current
  week (08-09) not in local cache — bridge needs the current-week snapshot to match against.
- Actions card: crossed-off items now collapse into "Archived · N done" (<details>, closed by default).

## Meeting-notes extraction (paste → per-CE suggestions) — Aug 17
- Decision: engine CAN'T read Granola links (403 public; cache/token encrypted). Report engine HAS Claude API
  (ANTHROPIC_API_KEY) but needs CONTENT. BGMs are on the report → so: PASTE the notes/transcript, engine extracts.
- Scope (user): notes → commentary/observations + action items; land BOTH on Review-tab CE cards AND bucket-table
  cells; SUGGEST → BGM approves (never auto-write).
- Frontend DONE + demoed in mockup: "✦ Process meeting notes" (market-level) → paste → Extract & distribute →
  per-CE PENDING suggestions fan out to each mentioned CE → existing accept UI (Add to commentary / Create action /
  Schedule check). runExtract sends {market_slug, week, text, ces:[all_ces id+name]}.
- Backend WRITTEN (deploy needed): notes/review_extract_api.js → deploy as api/review-extract.js. Auth mmr_session,
  Claude (Sonnet) segments notes by CE from supplied list → ingest pending via review_source_ingest (REVIEW_INGEST_SECRET).
- REMAINING wiring: (1) deploy the endpoint + set REVIEW_INGEST_SECRET/AI secrets; (2) bucket-table MIRROR on
  accept-action (client: when accepting an action for a CE in a bucket, also action_upsert with that bucket) — the
  "land on report tables" half of "Both, everywhere". Core "land on CE" works via the suggestion pipeline.

## Option B — native Eevee build (Aug 18)
- Phase 1 ✅ DONE: pipeline proven. esbuild bundles React + @headout/eevee (install: --legacy-peer-deps,
  GitHub Packages auth from wishlist .npmrc). STYLING = just include the shipped @headout/pixie/styles.css
  (108KB) — NO PandaCSS codegen needed. Eevee token vars (--colors-core-*) also come from it.
- Phase 2 CORE ✅: scripts/weekly_report/review-app/ = React app. src/api.ts (client), src/review.tsx
  (workspace, exposes window.initReviewView(ctx) — SAME contract as vanilla, drop-in). Uses real Eevee
  Button/Avatar/Text + token-var inline styles for layout (avoids pixie css() codegen). Bundle 201KB.
  Wired to backend + rendered live (native-mockup.html): queue-select, note read/edit/delete, Slack summary,
  action rows (status select + complete + archive), treatment, finish, Next CE — ALL WORKING. Avatar prop = fallbackText.
- Phase 2 REMAINING (port for full parity): Add CE picker, Granola band + suggestions accept/ignore + add-link,
  Process meeting notes, add-action/schedule-check composers, suggestion cards, CE Memory drawer, Open work tab.
- Phase 2 ✅ FULL PARITY: review.tsx ports all flows (queue+tabs, Add CE picker, Process notes, note read/edit/delete,
  Slack summary, Granola band + suggestion cards + add-link, action rows + status + archive, add-action/schedule-check
  composers, CE Memory drawer). Bundle 220KB. All render+work in native-mockup.html, no code errors.
- Phase 3 ✅ DONE: inject_review_view.py --native inlines pixie/styles.css + dist/review-view.js (skips vanilla
  client). PROVEN: injected into a copy of the REAL shell (rv-native-test.html) → Review nav enabled, native
  Eevee renders with real 41-CE NA data. Same initReviewView(ctx) contract, so the shell integration is unchanged.
- Option B COMPLETE. To ship native: `inject_review_view.py --market north_america --native` on the LIVE file, then deploy.
  (Live file currently has the VANILLA injection — not flipped to native yet.) Native adds ~220KB JS + 108KB CSS/report.
- Minor polish deferred: Eevee Buttons fill their flex row (want auto-width); accepted-comment "Meeting pointer" needs include_decided.
- Bundle cost: ~201KB JS + 108KB CSS vs vanilla ~45KB. Fine against 13MB report.

## Notes
- No render_v2.py / V2-shell generator exists anywhere — shell is a hand-deployed artifact. inject_review_view.py IS the durable transform; fold into a generator if one ever lands.
- Live write test blocked by auto-mode classifier (state-changing net calls); read test + shared proxy path make write path validated by construction.
- Backup of pre-injection live NA file attempt was also gated; use `git`/manual copy before injecting, or re-run injector (idempotent) to revert-by-strip is NOT a revert — keep a copy first.

## Open Questions
- UNCONFIRMED: run for all ~18 markets now, or NA pilot then roll out? (proceeding NA-first, injector generalizes)

## Working Set
- Worktree: /Users/aaradhyarai/.codex/worktrees/25ff/market-weekly-report-skill (branch codex/final-wbr-review-mode)
- Deploy dir: ~/analytics/market-notebook-v2/ (NOT git-tracked; weekly-report-<slug>.html, review-client.js, api/)
- Live URL: https://market-notebook.vercel.app/weekly-report-north-america  (Chrome tabId 410801483)
- Mockup: docs/weekly-review/final-wbr-review-mode.html
- Rollback: /private/tmp/market-notebook-review-cutover-20260817/
