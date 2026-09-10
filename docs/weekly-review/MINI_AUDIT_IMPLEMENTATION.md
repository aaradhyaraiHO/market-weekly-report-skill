# Mini Audit — report implementation

Implemented locally on 9 September 2026. No production deployment or live Slack, Sheets, or AI writes were performed.

## BGM workflow

1. Open **Mini Audit**, or **All CEs → CE drawer → Open Mini Audit**. The actual CE data stays on the left; the audit occupies the right half. Search any CE without an add/nomination form.
2. Write once. **Save note** appends to CE memory. **Reply in Slack** sends the same writeup to the active CE thread with resolved mentions. Choose **Start a new thread** when starting a separate discussion; the writeup stays in place, sending creates the thread, and earlier threads and approved summaries remain in memory. Channel routing is configured in the backend.
3. **Summarize discussion** reads the bound thread, saves the summary to memory, and exposes proposed actions under **Needs review**. Confirm/edit/dismiss them. Approved items enter the same **Open** register across weeks; completing an item moves it to **Completed**.

**Add meeting notes** is a report-level entry. Paste the meeting transcript, select **Find CE summaries & actions**, then open each CE to review proposed notes/actions. Imported notes enter CE memory after approval. Unmatched passages are shown for clarification with explicit CE names/IDs; repeat imports preserve previous decisions. Granola links are no longer an input.

The main workspace has no review-path selection, finish checklist, separate topic/request fields, nomination reason, separate memory drawer, scheduling step, or duplicate approved-summary panel. Existing dated work remains accessible through Open and Completed.

## Reliability changes

- Fixed `reviewWeeklyBase` dropping `thread_binding_id` and `slack_discussion_number` during ordinary mutations. This broke later exact-thread summary approval. Legacy missing bindings recover only when the thread association can be established unambiguously.
- Summarization can start from an existing CE thread without first posting a weekly starter. Sources and generated summaries retain the exact thread binding. A late model response cannot overwrite a newly selected thread.
- AI failure is an explicit retryable error; earlier summaries and source replies survive. Unchanged source sets avoid an unnecessary model call. Human writeups sent through the report are included as source context.
- Continuing a discussion does not skip replies that have not yet been summarized. Repeated identical action suggestions use stable source identities.
- Notes, manual actions, and Slack sends retain request identities for retries. Drafts survive CE switching. Read caches are invalidated after confirmed writes; earlier reads cannot repopulate the cache with stale data.
- Notes, suggestions, threads, work, and memory load independently. Browser reads time out after 15 seconds; mutations/extraction after 90 seconds. Model calls have a 45-second timeout. These limits provide recovery states; they are not a promise of live latency.
- Sheet handles are reused during a backend invocation. Current headers are no longer rewritten for every read.
- Transcript extraction returns persisted suggestion IDs, enabling approval from the report. The injector stages `/api/review-extract` alongside the other review APIs.

## Verification

The full weekly suite and `verify_baseline.py` pass: **296 tests**. `git diff --check` and JS/Python syntax checks pass.

Production-function runtime tests use in-memory service boundaries to check: existing-thread bootstrap, exact-thread source isolation, legacy binding recovery, successful summary approval, AI outage preservation, stale-result rejection, unchanged-source short circuit, repeated suggestion deduplication, note/action/send retries, preserved scan cursors, client timeouts, authentication errors, and cache invalidation races.

Browser walkthrough on a real North America snapshot with explicitly simulated integrations checked: CE drawer → split workspace, note save, new-thread choice and send, summary failure/retry/save, isolated drafts across Kennedy/Hawaii, return to All CEs, and meeting extraction → CE selection → action approval. The fixture does not test real Slack delivery, Granola access, AI output quality, or production latency. Desktop layout was visually inspected; narrow-screen CSS is implemented but not yet browser-verified.

No shared V1 metric or calculation code was changed for Mini Audit. Existing unrelated grouped-market and rendering changes in the checkout were preserved. The baseline suite includes V1 fixtures. No default renderer/cutover setting was changed by this work.

## Reproduce the local preview

```sh
python3 scripts/weekly_report/render_v2.py .cache/weekly_report/snapshot_north_america_2026-08-30.json --out .cache/weekly_report/mini_audit_preview/weekly-report-north-america-2026-08-30.html
python3 scripts/weekly_report/inject_review_view.py .cache/weekly_report/mini_audit_preview/weekly-report-north-america-2026-08-30.html --deploy .cache/weekly_report/mini_audit_preview
python3 tests/weekly_report/mini_audit_preview_server.py .cache/weekly_report/mini_audit_preview --port 8771
```

Open `http://localhost:8771/weekly-report-north-america-2026-08-30.html?view=review&ce_id=3111`. The yellow banner labels all simulated integrations. Fixture records exist only in server memory and reset when the process restarts.

## Release boundary

Deploy the dedicated Review Apps Script and report/API package together when release is authorized. The suggestion schema adds `thread_binding_id` at the end; existing columns retain their order. Older ambiguous thread sources are retained but excluded from a new thread's AI context.

Existing Review access enforcement, market channel mapping, Slack credentials, AI webhook credentials, and Granola access must remain configured. Verify the live note → Slack → summary → memory path before activation. The dedicated legacy diagnostic service and V1 renderer remain separate fallback paths. No live deployment or migration was performed here.

## CE memory integration correction

Mini Audit projects the existing `review_memory` response by market and stable CE ID across weeks. It does not create a memory table or copy legacy records into Review storage. It includes original BGM/BDM/Performance notes, historical CE comments and Performance actions, approved discussion summaries, meeting notes, decisions, review receipts, and references to the canonical work records. Original source records win over their duplicate timeline projections. Summary sections retain findings, decisions, and open questions; an already approved summary remains visible while a replacement draft is pending.

Memory is grouped into one block per stored review/origin week, with the latest week expanded by default. Each block presents recorded notes and approved summary wording as a sourced account, followed by references to work from that week. Original records expand under Sources. Missing week identity stays visibly undated; updated/completed dates do not move work between weeks. Work references navigate to the same Open/Completed action, including completion evidence and recorded outcomes in memory. Historical Performance records retain status, owner and bucket and remain read-only. Source-specific outages are distinct from empty history; failed refreshes retain the prior response. This is a view of stored records, not a claim that every historical status transition or economic outcome was recorded by the legacy service.

The memory response no longer truncates weekly commentary, comments, closed work, receipts, threads or timeline records. The action client follows pagination, with a stable timestamp + work-ID cursor to retain timestamp ties. No historical source writes or migration are involved. Runtime coverage checks 65 weekly records, 40 comments, 30 closed tasks, sibling CE/market isolation, deduplicated projections, tombstones, approved summaries during regeneration, and 205 actions with identical timestamps.

A richer, explicitly simulated Chicago history is available by running the preview fixture with `--port 8772`. Browser verification covered older Performance/CE comments, structured summaries, meeting provenance, and navigation to the canonical completed task. Existing 8771 fixture sessions may still carry their earlier in-memory sample state. Production integration deployment and live latency verification remain outstanding.


### Weekly account presentation

The main memory surface no longer divides the reader's account into Observations / Discussion / Actions or individual event cards. It presents the recorded prose and approved summary points together, preserving unresolved questions explicitly and retaining differing accounts. Exact repeated passages share source references. This is a lossless presentation of saved content, not a new AI synthesis or an inferred consensus. Source-only weeks retain their original wording. Operational events remain accessible in Sources; links there retain the complete Performance metadata and thread history. Follow-through points to the same canonical work IDs, with current status and recorded evidence. Runtime checks cover grouping by origin week despite later completion, undated records, multiple sources per week, conflicting statements, and source-only weeks.

CE memory itself now starts collapsed, with user-controlled expansion retained during the session. Historical Performance passages show their owner, recorded status and update date inline in the weekly account; full original metadata remains under Sources. Status-only rows remain visible without inventing an action description. Legacy diagnostic statuses describe selections such as ROAS change or seasonality; they must not be interpreted as task completion. The legacy checkbox confirms seasonality rather than generic action completion. Browser verification covered the collapsed default and expansion to the inline Performance record; all 296 tests and baseline checks passed.


### Shipped UI cleanup

Removed 19 unreferenced legacy render/helper functions from the canonical browser script, including the old memory drawer, finish bar, role-note forms, reconciliation card, imported-comment cards and Granola dock. Removed the injector's alternate `--native` React bundle option; the injector now uses the report's canonical Mini Audit source only. Historical mockup/reference files and the separate legacy backend remain outside the shipped UI path. Shared backend routes and Sheet tables are retained for older report links and background ingestion compatibility. Contract tests now check active weekly memory, inline writeup, queue and approval controls rather than matching text in the removed renderers. This cleanup does not deploy anything or complete the remaining weekly-release integration.
