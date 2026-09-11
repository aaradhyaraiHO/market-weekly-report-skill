# RPC / CM1 ROI comparison precision — 2026-09-11

## Scope

Keep Revenue labels, bucket membership, ordering, thresholds, verdicts, RPC
L3W swing, CVR definitions and CSEE/Nordics configuration unchanged.

The daily Google Search diagnostic producer now retains optional
`weeks[].roi_unrounded` after its existing validity gates. Its rounded `roi`
field is untouched, including its use in authoritative bucket decisions.
The V2 projection adds `roi_wow_pct` using adjacent equal-length windows.
This also supports newly generated partial-window reports without comparing
them to full calendar weeks.

Frozen reports use their matching cached Google Search weekly operands only
for explicit seven-day blocks. Rounded ROI, spend, clicks, CPC and CM1 per
conversion must reconcile. Missing, mismatched or partial-window evidence
renders ROI WoW unavailable, not a rounded-operand estimate. No BQ requery or
historical platform backfill is performed.

## Example

North America, CE 6853, week 2026-08-30:

- W0 Google Search CM1 $674.8328 / spend $384.8132.
- W-1 Google Search CM1 $785.9147 / spend $273.6421.
- Exact ROI relative change: -38.94043235%, displayed **-38.9%**.
- Previously displayed: -39.0%, from rounded 175 / 287.
- RPC swing remains -50.3%; verdict remains watch.

Headout's frozen blocks for the same CE span six days. They cannot use these
seven-day operands and are deliberately left unavailable. New runs retain
the original daily-window operand instead.

## Frozen artifact

`release_rpc_precision.py` stages from the verified ROI/Levers release and
changes only optional fluctuation-row JSON fields. All HTML/CSS/JS outside
the JSON, existing payload values, API handlers, notes runtime, report dates,
latest links and alert history are preserved.

- 111 V2 pages; 137 other files byte-identical.
- 660 available, 365 unavailable precision fields, counting aliases/history/
  country copies separately. These are not unique CE counts.
- North America latest: 9/9 fluctuation comparisons available.
- Headout latest: 0/50 (frozen partial windows; not a new source query).
- 356 tests passed, including unchanged V1 contracts and frozen-release tests.

## Scheduling readiness audit

The canonical `run_v2_release.py` plan exists, but is **not yet sufficient for
unattended completion**:

1. Source reconciliation completed after explicit approval: the five existing
   cleanup files matched the conflict-free combined tree byte-for-byte. They
   were committed separately as `280052e`, then `origin/main` was merged as
   `b2d1ea8`. The combined checkout passes all 356 tests. Push/readback is still
   required before choosing the scheduler's immutable source revision.
2. Headout reports are generated, but the batch alert step uses `all`, which
   resolves only the 17 markets. Headout delivery needs an explicit step.
3. V2 RCA failures currently leave parents sendable without CE replies. Require
   complete enrichment and resumable delivery/ledger handling before scheduling.
   The current poster records parent timestamps only after the message loop and
   does not enforce successful delivery of every reply. A crash can leave posted
   parents unrecorded; a retry must reconcile Slack before sending anything new.
4. There is no live report-week/content verification step between deploy and
   posting, nor a final Slack-thread completeness gate in the canonical plan.
   The runner also creates an empty default notebook directory while the
   publisher adds weekly pages/APIs but not the full site's `index.html` and
   archives. Seed staging from the verified full notebook and enforce complete-
   site/archive preservation before deployment; do not deploy the empty-base
   default package as the whole site.
5. User confirmed the deadline: **Monday 11 AM IST**, reports and alerts ready
   by then (not merely started at 11). Choose an execution host, persisted
   duplicate ledger, unattended credentials and a failure-notification route.
   A laptop-based schedule cannot run while the laptop is off.
6. Run one supervised complete-week release through those exact gates before
   enabling recurrence. As of Friday September 11, September 6–12 is incomplete;
   the next Monday run is September 14. Do not promote its preview early.

Historical Google/Bing evidence gaps and true CSEE/Nordics aggregation remain
explicitly deferred. They are not reasons to fabricate data or block new-week
generation where fresh source data is complete.
