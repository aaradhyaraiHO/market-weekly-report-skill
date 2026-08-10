# Handoff — Slack context integration (worktree-SLACK ↔ worktree-CE-drawer)

_Last updated: 2026-07-17. Owner of Slack work: worktree-SLACK. This doc coordinates the merge into the CE-drawer branch (the bigger drawer/template rework)._

## Objective (the to-do)
"Link relevant Slack conversations into CE drawers (consolidated context)" + market-level §2.
- **CE-scoped** Slack cards render inside that CE's drawer under a **"Slack context"** section.
- **Market-scoped** cards render in the **§2 Market Review** tab.

## State by worktree

| Worktree | Commit | Slack status |
|---|---|---|
| **worktree-SLACK** | `6e32b04` | ✅ Built: card schema (SKILL.md S3), `ceSlackContext()` + `_ctxCard`/`_catChip` + §2 routing in template, `market_review_context: []` in snapshot. |
| **worktree-CE-drawer** | `34ea686` | ❌ No Slack. Heavy drawer/table rework (per-metric expand, TGID band-collapse, TOTAL row, Overall/Paid tabs, paid-metric definition fixes). |

Both branch off the same ancestor (`db3806d`) and **both modify `report_template.html` + `build_snapshot.py`** → must be merged deliberately, not landed independently.

## Data contract (from worktree-SLACK — do not change)

**Card object** (in `snapshot.market_review_context`, a list):
```
scope      : "market" | "ce"        # routing: ce → drawer, market → §2
ce_id      : "<combined_entity_id>"  # for scope=ce
category   : one of the 9 (closed vocab, see below)
author     : str
channel    : str   (e.g. "#mkt-usa")
permalink  : str   (Slack thread link)
timestamp  : str   (human date)
text       : str   (the card body / so-what)
source     : str   (default "slack")
```
**Category vocab** (`_CAT_LABEL` in template): `commission_change`(TR change) · `availability` · `campaign_decision`(campaign) · `promo_start_end`(promo) · `new_launch` · `competitive_intel`(competitive) · `supply_issue`(supply) · `bug` · `strategy`.

**Population:** SKILL.md S3 (agent step) reads Slack → emits cards → injects into `snapshot.market_review_context`. (Note: legacy `.cache/weekly_report/slack_context_*.json` sidecars are the OLD **name-keyed** format — stale vs this ce_id schema. Regenerate via the new S3 step; the old name-matching was unreliable — only ~4/10 matched, hence the ce_id switch.)

## Merge collision points & exact edits

### 1. `report_template.html`

**(a) Helpers — clean add.** worktree-SLACK adds `_CAT_COLOR`, `_CAT_LABEL`, `_catChip(cat)`, `_ctxCard(c)` right **before `function renderFollowup(M){`**. CE-drawer did **not** touch that region (renderFollowup is at CE-drawer line **623**) → applies clean.

**(b) `ceSlackContext(ceId)` — clean add.** New function (SLACK ~line 1545):
```js
function ceSlackContext(ceId){
  const cards = (MARKETS[mi].market_review_context||[]).filter(c=>c.scope==='ce' && c.ce_id===ceId);
  if(!cards.length) return '';
  return '<div class="dr-sec-t">Slack context · '+cards.length+' item'+(cards.length>1?'s':'')+'</div>'+
    '<div class="mr-context">'+cards.map(c=>_ctxCard(c)).join('')+'</div>';
}
```

**(c) openDrawer insertion — THE ONE MANUAL RECONCILE.** CE-drawer restructured the drawer; the concat is at **CE-drawer line 1783**:
```js
      kmBlock + shapBlock + resourceBlocks(ce) +          // ← line 1783
      '<div class="dr-sec-t">Notes · persists week-over-week</div>'+   // ← line 1784
```
Insert `ceSlackContext(ce.ce_id) +` between them so it becomes:
```js
      kmBlock + shapBlock + resourceBlocks(ce) +
      ceSlackContext(ce.ce_id) +
      '<div class="dr-sec-t">Notes · persists week-over-week</div>'+
```
(SLACK places it identically — after resourceBlocks, before Notes.)

**(d) §2 Market Review — verify.** SLACK filters market cards with `c.scope!=='ce'`. CE-drawer did not change §2 rendering → applies clean.

**(e) CSS — clean add.** Append SLACK's styles (not present in CE-drawer): `.mr-context`, `.mr-context-item`, `.mr-context-item .mr-src`, `.mr-context-item .mr-txt`, `.mr-when`. `_catChip` reuses existing `.chip` color classes (violet/amber/blue/green/red/ghost) — already in CE-drawer.

### 2. `build_snapshot.py`
CE-drawer snapshot dict tail is at **lines 1097–1102** (`bucket_cascade` … `transitions` … `_diagnostics`). Add the SLACK line:
```python
        "market_review_context": [],   # populated by S3 Slack digest (agent step)
```
No logic conflict — pure additive key.

## Recommended sequence
1. **Land worktree-CE-drawer first** (the structural drawer/template rework).
2. **Rebase worktree-SLACK onto it.** Expected outcome: (a)/(b)/(d)/(e) apply clean; **only (c)** needs the one-line manual insert at the restructured openDrawer (line 1783) + the (2) snapshot key. Both are trivial and documented above.
3. Regenerate sidecars via the new S3 schema (ce_id + scope), rebuild, verify: CE-scoped cards land in the right drawers (exact ce_id match — no name fuzzing), market-scoped in §2.

## Not in scope for this handoff
CE-drawer's metric work (paid = Google Search + Bing, RPC/CM2 paid-attributed, TGID bands, overall CVR, etc.) is independent of Slack — no overlap beyond sharing the two files above.
