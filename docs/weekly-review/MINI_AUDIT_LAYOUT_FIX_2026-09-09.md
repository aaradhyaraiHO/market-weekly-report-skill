# Mini Audit header and collapsible left navigation — local verification

Status: **implemented and verified locally; not deployed**. The live mid-week
release remains `dpl_42kTYc2YkRwhMffBVpjENTfXtZBy` / backend version 17.

Scope: the floating table header and **left report navigation rail**. The earlier
Hide notes / Show notes implementation was removed following the user's
clarification. The right-hand notes/actions/memory panel remains visible.
Existing pipeline, report calculations, snapshots, backend, comments,
Slack threads, histories and unrelated dirty checkout changes were not edited.

## Interface review — full, scoped to these two controls

Framework: existing plain HTML/CSS/JavaScript with the report's Oak/Eevee tokens.
The weekly-report skill kept the preview on frozen production data. Interface
review guided accessible controls and an instant, state-preserving layout toggle.

| Category | Evidence inspected | Result |
| --- | --- | --- |
| Typography | Collapse sidebar label, compact-rail tooltips, mobile labels at 390, 768, 1024 and 1280 CSS px | Clear; no new type system |
| Surfaces | Navigation rail, unchanged notes divider, clipped floating header, expanded/collapsed widths | Two issues fixed below |
| Animations | Toggle implementation and styles | Instant layout change; no custom animation, so slow-motion check not applicable |
| Icons | Left-rail toggle and three compact navigation icons | 20px inline SVG, currentColor, consistent 1.5px strokes, decorative SVG hidden from assistive technology; buttons retain their names and tooltips |
| Performance | Toggle handler, floating-header scheduler and runtime tests | No panel rerender, network request or new animation machinery on toggle |

| Severity | Location | Before | After | Why |
| --- | --- | --- | --- | --- |
| HIGH | `report_v2_template.html`, floating table header | Embedded CE tables pinned their copied header to viewport y=0, covering the report title | Use the embedded pane's visible bounds; clip horizontally and hide behind the CE picker | Keep the table header inside its own scroll area |
| MEDIUM | `report_v2_template.html`, report sidebar | Left navigation always consumed 196px of desktop width | Collapse sidebar / Expand sidebar changes only the left rail to 68px; all three destinations remain accessible as 44px icon buttons | Recover 128px for the workspace without hiding notes |

Collapsing and expanding change only the shell class and toggle label/ARIA state.
The CE and note/action DOM are not recreated or accessed by the toggle. Collapse
state survives navigation and CE-picker open/close. Under 901px, the existing
horizontal navigation remains labelled, regardless of desktop collapse state.
No reload persistence of unsaved text or sidebar preference is claimed.

Considered but rejected:

- Re-rendering the whole workspace on collapse: unnecessary risk to unsaved text,
  focus and an in-flight save.
- Disabling every sticky header: would remove useful table context and change
  unrelated Overview/drawer behavior.
- Animated grid-width transition: repeated table reflow provides no benefit for
  this frequent utility control; the explicit label provides clear feedback.
- Hiding the right-hand notes: rejected by the user; both evidence and notes
  remain available while the left navigation becomes compact.

## Verification

- `python3 scripts/weekly_report/verify_baseline.py`: **322 tests passed**.
- Actual-JavaScript runtime test allows the toggle to access only the shell and
  its button. Any attempt to access CE/notes DOM, rerender, or perform network
  work fails. Tests also cover ARIA state, header rescheduling, removal of the
  wrong notes toggle, embedded viewport clipping, and unchanged ordinary
  report/modal header boundaries.
- `git diff --check`: passed.
- Local fixture only; all review/Slack/AI requests simulated in memory.
- The preview's embedded report JSON is **byte-identical** to the deployed
  North America page: SHA256
  `8be3085e6cab66ec9cbaee759f10b6f27400d26e0eae4739468ddfe1954c6e6c`.
- At 1024 CSS px, evidence widened **414 → 478 px**; at 1280 CSS px,
  **542 → 606 px**. Notes also gained 64px and remained visible. Total workspace
  gain is 128px, not a doubling of the CE pane.
- A local unsaved draft remained unchanged through mouse collapse, keyboard
  reopen, Overview → All CEs → Mini Audit navigation, CE picker and resizing.
  The keyboard toggle retained focus. All three compact navigation routes worked.
- At 1024 CSS px after scrolling, the copied header and embedded pane both began
  at **149.8 px** with the rail collapsed. Expanding the rail caused the toolbar
  to wrap; both resynchronized to **191.4 px**, below the toolbar rather than y=0.
  CE picker suppressed the floating header.
- At 390 and 768 CSS px, document width equalled viewport width, mobile navigation
  retained all labels, and the desktop-only collapse control was hidden.
- Browser error log: empty for the tested preview.

Verdict: **Approve for the tested local slice**. Not verified/deployed live for
this new layout patch; no production notes, Slack posts or backend mutations were
used as fixtures. This does not close the separately outstanding genuinely-new
Slack delivery / new AI summary live gate.

Preview generator:

```sh
python3 tests/weekly_report/build_layout_preview.py \
  .cache/weekly_report/midweek_mini_audit_resilient_release_2026-09-09/weekly-report-north-america.html \
  .cache/weekly_report/mini_audit_layout_preview_2026-09-09/weekly-report-north-america.html
```
