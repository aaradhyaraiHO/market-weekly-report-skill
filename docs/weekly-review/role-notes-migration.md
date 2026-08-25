# Review role-note storage migration

The `review_weekly_commentary` Sheet remains the CE/week authority. Migration is additive and does not rewrite existing rows.

Existing `bgm_note`, `bgm_author`, `bgm_updated_at`, and `note_deleted_at` columns retain their meaning and become the BGM-note fields. The isolated Review backend appends these columns when absent:

- `performance_note`, `performance_author`, `performance_updated_at`, `performance_note_deleted_at`
- `bdm_note`, `bdm_author`, `bdm_updated_at`, `bdm_note_deleted_at`

`review_weekly_note_upsert` accepts `note_type` (`bgm`, `performance`, or `bdm`) and mutates only that role's four fields. Omitting `note_type` preserves the legacy BGM behavior. Authors continue to come from the authenticated Review identity; a claimed role or Slack membership never grants access.

Slack discussion text is transient request data (`discussion_text`, `discussion_author`). It is posted and its thread metadata is retained, but it does not populate or overwrite any role-note field. The backend temporarily accepts legacy `bgm_note`/`bgm_author` Slack payload keys as a transport fallback without saving them as a note.

Rollback is code-only: older clients continue reading and writing `bgm_note`; the new optional columns are ignored. No source rows are migrated, deleted, or reclassified.
