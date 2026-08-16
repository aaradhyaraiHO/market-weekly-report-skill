# Final WBR review-mode implementation audit

Status meanings:

- **Wired mockup** — the committed HTML interaction works and persists locally for review.
- **Backend contract** — code and storage contract exist in the repository.
- **Live** — deployed and verified against the real report, Sheet, Slack or Granola source.

| Finalized workflow | Wired mockup | Backend contract | Live | Remaining work |
|---|---:|---:|---:|---|
| Review queue and Open work switch | Yes | Yes | No | Connect the real weekly review set and cross-CE work query. |
| Review treatment, last-reviewed state and finish receipt | Yes | Yes | No | Call `review_receipt_upsert` from the production Review mode and verify authorization. |
| Open CE metric drawer without losing review state | Yes | Existing CE drawer | No | Mount Review mode in the real report and preserve state across the drawer transition. |
| One BGM note per CE × market × week | Yes | Yes | No | Deploy the updated Apps Script/proxy and connect the production composer. |
| Save, edit and delete BGM note with audit retention | Yes | Yes | No | Verify real Sheet writes and tombstone rendering end to end. |
| One persistent Slack thread per CE | Yes | Yes | No | Deploy and verify a real post, durable thread mapping and source permalink. |
| Natural-name Slack tagging | Represented | Yes | No | Sync the Slack people directory, curate aliases and test ambiguous names. |
| Automatic Slack reply summary back into Review mode | Represented | Yes | No | Install/verify the recurring sync trigger and AI endpoint in production. |
| Slack-derived commentary/action/check suggestions | Yes | Yes | No | Verify extraction, deduplication and BGM accept/ignore against a live thread. |
| Action/check owner, status, due date and scheduled review | Yes | Yes | No | Connect Review-mode controls to `review_work_items`; the current mockup uses local state. |
| Operational states: already actioned, self-recovering, monitoring and no action needed | Yes | Yes | No | Verify carry-forward and close-out behavior against real records. |
| Manual action creation, editing, completion and Open work roll-up | Yes | Yes | No | Build the production Review/Open-work UI over the existing work-item API. |
| Automatic Granola meeting matching | Represented | Adapter exists | No | Deploy the Granola adapter and provide the live meeting feed/matcher. |
| Manual Granola-link fallback in the bottom dock | Yes | Link inbox exists | No | Add the trusted worker that fetches the pasted meeting, extracts suggestions and clears `awaiting_import`. |
| Granola commentary to Commentary; actions/checks to Actions | Yes | Yes | No | Verify destination writes and source links after production deployment. |
| CE Memory: Story, Work and Sources | Yes | Memory endpoint exists | No | Replace static Kennedy examples with `review_memory` plus the Perf history sidecar. |
| Historical EGER comments and read-only Perf decision history | Yes | Import/read contracts exist | Partial | Validate all markets and CE-key matching; do not rewrite source records. |
| BGM-only mutation access | Represented | Yes | No | Populate the BGM allowlist and enable `REVIEW_ENFORCE_ACCESS` after a permissions test. |

## Production blockers

1. The standalone final mockup is not mounted in the generated weekly report application.
2. Apps Script, the authenticated Vercel review proxy and the Granola adapter changes are not yet deployed together.
3. The manual Granola-link flow currently queues `awaiting_import`; no live worker fetches and processes that link yet.
4. Action/work-item storage exists, but the production Review-mode UI is not connected to it.
5. Slack posting, reply sync, AI summaries, suggestions and source reconciliation still need one end-to-end production verification.
6. CE Memory is interactive in the mockup but still uses static Kennedy examples rather than live `review_memory` results.

