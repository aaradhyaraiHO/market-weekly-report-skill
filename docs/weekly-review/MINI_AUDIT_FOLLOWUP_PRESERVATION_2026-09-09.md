# Saved-note follow-up: backend preservation audit

Read-only baseline captured at 2026-09-09 14:40 UTC. After the coordinating ready message, backend version 17 was activated at 14:51:20 UTC and verified at 14:52:47 UTC. The coordinating “Check report readiness” task owns frontend promotion and release sequencing.

## Baseline

Private complete cell-value backups, metadata, code, deployment configuration and per-tab hashes are under `.cache/weekly_report/mini_audit_followup_backend_2026-09-09/` (backup files mode 0600).

- Review backend: all 16 tabs captured, including 6 weekly records, 2 comments, 5 work items, 3 Slack bindings, 3 suggestions and 1 timeline event. The second comment was added since the earlier release receipt and is included.
- Established weekly history: all 13 tabs captured, including 440 Performance/action rows, 61 notes and 8 legacy work items.
- Backend raw snapshot SHA256: `4c2fefd4da56f7c758df91d5ac49aaa472ace70cda6effc4f4d114c478905a71`.
- History raw snapshot SHA256: `544fae8bba52f7e7067fce8f3fe4c0f69624560470da0fc367e0f5465051a93f`.
- Live backend: immutable version 16, source SHA256 `33454dc008222bed9c3454a627ed4539867bbcb03e9ec02fb3a9be1abc455caf`.
- Candidate: SHA256 `429d69be805496c482a043ce869637996d4f31c251032255583331f0fdca175d`.

## Compatibility

The entire candidate-versus-v16 diff is confined to `reviewCommentUpsert`. All 14 defined backend table headers exactly match live headers. No schema change, migration, data reset, script-property update, endpoint replacement or Slack repost is required.

The candidate retains note identity, original authorship, source attribution and creation time. Existing text is archived as a revision before replacement. New clients provide an expected version timestamp; stale versions and concurrent changes are rejected with the draft retained. Old clients without that field remain accepted; they do not gain optimistic conflict detection, but the previous text is retained in the revision timeline. In-memory execution verified this old-client path and replay deduplication. The full project runtime suite additionally covers stale/conflicting saves and deleted notes.

Both existing comments are read by the selected-week paginated query. The only existing approved weekly summary has matching summary/thread bindings and appears inline. Current per-CE weekly history is at most four rows, within the eight-row frontend read. The coordinator was asked to fix two latent visibility edges before staging: filter memory summaries only when actually visible inline, and query the selected week explicitly using the backend's `week` parameter.

The comment pagination cursor is currently timestamp-only. More than 50 notes with exactly the same creation timestamp could skip peers at a page boundary. This is absent from the current data; any cursor change requires a new frozen candidate hash and tests.

## Prepared activation and rollback

`deploy_followup.py --activate-approved` ran after the coordinating ready message. It checked the frozen source hash, editable HEAD and existing v16 deployment; created immutable version 17 with the unchanged v16 manifest; restored editable HEAD; and updated only the existing deployment. The first deployment listing was stale (v16), so its guard stopped. A direct deployment GET and a fresh listing then independently confirmed v17; no second activation request was made. `finish_verification.py` completed source, manifest, URL, other-deployment and preservation checks. A v16 rollback request is retained. No Sheet mutation or Slack message was sent.

Immediately before and after activation, compare all business-record rows against the baseline. Preserve any new concurrent user activity; do not restore an entire snapshot over the live workbook.

Immediate pre/post activation comparison passed for every existing row across all 29 tabs. All cell-value hashes were exactly unchanged, including both current notes; there were zero added, removed or modified rows. Receipts: `activation-receipt.json` and `activation-preservation.json` in the private backup folder. The coordinator received the version, hashes and note identities before frontend promotion.

The existing NA CE2567 August 30 discussion provides a real-source candidate for a no-new-replies summary repeat. Sending an actual Slack reply or creating a new parent requires message-send authorization and reviewed content. Neither has been done in this follow-up.

## Live repeat after frontend promotion

The coordinator promoted frontend deployment `dpl_DSRYByVSkS1oZFcre1nzbbFZmZ7H`, independently verified both CE2567 August 30 notes and the original approved summary, and clicked Summarize discussion once. After that completion signal, a fresh full-workbook capture was compared with the after-activation snapshot. All 29 tabs were exactly unchanged, including telemetry. Comments remained 2, weekly records 6, suggestions 3, work items 5, bindings 3 and timeline events 1. No duplicate records or source/cursor/summary-version changes occurred. Evidence: `after-live-repeat-snapshot.json` and `live-repeat-preservation.json` in the private backup folder. No new Slack message, note save or action mutation was part of the live check.

## Live read failure and recovery

A subsequent fresh production reload timed out while loading weekly discussion and suggestions. Both notes remained visible, but the summary appeared absent and suggestion loading failed. This was a frontend read/recovery issue, not data loss: the complete post-repeat Sheet snapshot was unchanged, and the exact downloaded version-17 `reviewFilter`/`reviewPage` functions returned the approved CE2567 August 30 row from that snapshot. Direct API navigation was blocked by the browser client, so that local function check is not represented as a successful remote GET.

The coordinator retried the live read and recovered the exact saved summary and original counts. It is preparing a separate frontend hardening release: 45-second selected-CE read timeout, visible discussion loading/error/retry states, cached summary retention, summarization disabled until the discussion read succeeds, and no false All done/zero state when action or suggestion reads fail. Backend version 17 remains unchanged; no additional backend activation or data mutation is required. Final frontend promotion/recheck is owned by the coordinator.

## Final release preservation

The coordinator promoted the final API-only release `dpl_42kTYc2YkRwhMffBVpjENTfXtZBy` (`market-notebook-2wriifj2o-headout.vercel.app`) with bounded GET retry; all 230 staged HTML pages were byte-identical to the preceding verified UI release. Backend version 17 remained unchanged.

After that promotion signal, the final read-only capture and comparison passed for all 29 tabs: every original row, cell value and header was retained exactly. The sole concurrent addition was one telemetry row (150 → 151); it was preserved. All business tables retained the same contents and counts, and the entire historical workbook was unchanged. No snapshot restoration or external mutation was performed.

- Final backend raw SHA256: `e8efdbb805d84b5a091b9f9cf16804367d42c4dd9a042b69a12844bb8b915490`.
- Historical raw SHA256: `544fae8bba52f7e7067fce8f3fe4c0f69624560470da0fc367e0f5465051a93f`.
- Private proof: `final-release-snapshot.json` and `final-release-preservation.json` in the backup folder.
- No new Slack send, genuine note edit, or action mutation was performed as a test. The successful real-source check remains the unchanged-source summary repeat and saved-note read/edit-cancel verification.
