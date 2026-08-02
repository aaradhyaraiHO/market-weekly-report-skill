# Losing Money v2 — blindspot pass (2026-08-03)

> **Status update (same day):** #1 partially fixed (Sun→Sat week shipped for the whole
> report build — W0 now has 2 maturation days by the Monday run; and re-bucketing the
> full 12-wk history each build means no 6-day transition week, which also closes #5).
> #3 fixed (New = never Pro+ in prior 4 quarters via combined_entity_stats; metadata
> fallback only). #4 fixed (engine emits `flagged_lw` → "new this wk"/"repeat" tags +
> last-week action pulled from the Sheet backend; "⚠ repeat · unactioned" when absent).
> Still open: #2 (own-target gate — needs Adi), #6–#13.

Evidence-based review of what the locked C1–C4 logic does NOT handle. Each item:
what breaks, evidence, and the cheapest sane fix. Tiers = urgency, not severity.

Verified NOT broken (cross-checked on Italy/NA/Oceania, 74 flagged rows): criteria
membership both directions, labels, sort, deltas, 90d, driver=argmin reconciliation,
weeks payload, and the full partition — every funded CE lands in exactly one of
{flagged, paused, tracking_gap, subthreshold, clean}; sub-$1k in burn line.

## Tier 1 — will bite on Monday runs

### 1. Maturity churn: ~15–25% of Monday's flags are provisional
W0 paid attribution settles ~3 days after week end; the report runs Monday on raw W0.
**Experiment** (Italy, W0=2026-07-13: flags at report-time data vs same W0 fully matured):
23 flagged at build → 21 matured. **4 ghost flags** (Airport Services Rome, Rome Pantheon,
Airport Transfers Rome, Blue Lagoon Malta — fired Monday, dissolve once data settles) and
**2 late flags** (Matterhorn Glacier Paradise −$265, Last Supper Milan −$237 — real losses
invisible on Monday). This is the mechanism behind perf's "skip: already recovering" pattern.
- The planned Sat–Sun window shift *reduces* this (2 extra maturation days) but doesn't fix it.
- Options: (a) accept + say so in the how-to ("marginal flags near thresholds may settle out");
  (b) tag rows whose fired delta is within ~20% of its threshold as ⏳ provisional;
  (c) run LM on the matured week like Fluctuations does (lags the report by a week — probably
  unacceptable, meeting wanted current week).
- Recommendation: (a) now, (b) if ghosts annoy reviewers, revisit after the window shift.

### 2. Fixed ROI<140 gate punishes intentionally-low-target CEs
The soft band ($200–500 drop) gates on a global 140%. But targets vary hugely.
**Italy this week: 5 of 17 flags are CEs BEATING their own target** while under 140:
Cruises-Venice (ROI 108 vs own tROAS 74) · Jungfraujoch (124 vs 83) · St. Mark's (126 vs 86) ·
Aquarium of Genoa (102 vs 54) · Duomo Milan (113 vs 78). By the meeting's own logic
("running as expected → don't intervene") these are noise rows.
- Also interacts with the dormancy plan: relaxing dormant-CE ROAS targets monthly will push
  MORE such CEs into this trap (the notes already say relaxation "must feed back into losing
  money flagging logic" — this is where).
- Option: soft band fires only when ROI < 140 **AND ROI < tROAS_L4W** (own-target check;
  falls back to 140-only when no tROAS). Hard $500 band unchanged. ~3 lines in buckets.py.
- NEEDS SIGN-OFF (criteria change) — take to Adi. Data says yes.

### 3. new_vs_existing metadata is thin — the table split rests on it
Italy raw: only 46/870 CEs explicitly "Existing"; 508 "New"; 302 Unknown/NULL (defaulted to
Existing). At the funded layer it's saner (38 Existing / 12 New / 2 Unknown) but one of this
week's flagged rows is a defaulted Unknown: **San Siro Tickets** — flagged as Existing while
its own season tag says "New / thin history". Mis-routing swaps criteria sets (C4) and tables.
- Action: verify the field's source definition (dim/evolution basis) matches what the meeting
  means by "new series"; decide Unknown routing explicitly (candidate: Unknown + first click
  < 12 months → New, using the launch map we already fetch).

## Tier 2 — logic edges

### 4. Action feedback loop: last week's fix becomes this week's flag
A scale-down/pause actioned last week mechanically drops this week's CM2 → C2 fires → the CE
is re-reviewed as if unowned. The meeting explicitly wanted last week's status visible
("we'll have last week's… was actioned last week"). Not implemented yet.
- Fix: read prior-week action from the notes Sheet during build; render a muted
  "last wk: scale_down · A." chip in the Action cell. Surface, don't suppress.

### 5. Sat–Sun transition week will mass-fire C2/C3
The one 6-day week during the window shift is mechanically ~14% lighter → CM2 drops
everywhere → a wall of false flags exactly when the team is validating the new cadence.
- Fix: for the transition week only, per-day-normalize the deltas (or suspend C2/C3 and say so).

### 6. $0 < spend < $50 weeks mislabeled as tracking gap
ROI computes only at ≥$50/wk spend. A winding-down CE spending $18 reads roi=None →
"feed gap — verify tracking", which is wrong and cries wolf.
- Fix: treat spw < WEEKLY_SPEND_FLOOR as paused-like ("effectively paused") in the footnote.

### 7. Persistence/chronicity signal dropped
Perf's sheet leaned on 2-wk-negative persistence; old engine had wks_neg. v2 rows don't say
how LONG a CE has been negative — reviewers must count red micro-rows.
- Fix: cheap "neg Nw" mini-tag next to the Status chip, computed from cm2_series.

### 8. Post-peak seasonality fires C3 market-wide
Known + accepted in the meeting ("smart logic later"). Partial mitigation already shipped:
season-phase chips render on each row. Cheap nudge: when phase = winding-down, pre-tint the
guideline toward negative seasonality in the row (display only, no criteria change).

## Tier 3 — workflow / system

9. **Mandatory comment is client-side only.** Apps Script happily stores status with blank
   note (direct edits, races). The meeting's Thursday Slack ping ("descending actioned list +
   flag no-comment CEs") is the real enforcement layer — not built yet. Build the ping, and
   the gap closes.
10. **Attribution**: wr_author still blank for most users (parked Option-A prompt TODO) —
    "who actioned" will be empty in the Sheet backend history.
11. **Global (headout) build untested** with the new schema — market-level only. Run
    build_global once before Monday; the drawer/tagging paths differ.
12. **Bing blind spot**: decisions are Google-only by design; a Google-bleeding CE can be
    Bing-profitable. Fine while actions are Google-scoped — the guideline should say so
    explicitly so nobody pauses a CE's whole paid presence off this table.
13. **90d ≈ 84d**: C4's window is the 12-wk series, labeled "~90d". Fine; just never present
    it as exact when finance asks.

## Suggested order
1 (howto note, 5 min) → 3 (verify metadata definition, 30 min) → 2 (own-target gate, needs
Adi) → 4 + 7 (last-week action chip + neg-Nw tag, biggest reviewer QoL) → 5 before the window
shift → 9 with the Thursday ping build. 6, 8, 12 opportunistic.
