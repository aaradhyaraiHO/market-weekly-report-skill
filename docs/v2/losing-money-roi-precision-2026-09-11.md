# Losing Money ROI WoW precision

Status: implemented and verified locally; not committed, published or deployed.

## Scope

V2-only presentation fix for Existing and New Losing Money rows. The Python
view model adds `roi_wow_pct`, using the original same-week CM1 and spend from
the frozen CE weekly series. It mirrors the producer's Google Search versus
pre-split scope and preserves its ROI validity gate. The template formats this
percentage rather than dividing the integer-rounded bucket ROI cells.

Only adjacent, matching weeks with valid operands and matching rounded bucket
ROI are accepted. Missing evidence or a zero prior ROI displays unavailable;
there is no fallback to rounded operands for these enriched rows.

Existing bucket fields, classification, sorting, V1 outputs and cached snapshots
are untouched. RPC/CM1 table precision and the Revenue column label are outside
this change. The pre-existing Levers disclosure patch remains separate.

## Evidence

Kennedy Space Center (3111), North America, 30 Aug–5 Sep 2026:

- W0: CM1 19551.8507 / spend 15400.4898 = ROI 126.9560316192%.
- W−1: CM1 27135.8601 / spend 20064.0294 = ROI 135.2463134848%.
- Relative change = −6.1297655011%, rendered as −6.1% (formerly −5.9%).
- Local browser verified the actual table cell, including United States filtering.
- 36 cached Aug 30 / Sep 6 snapshots: all 1,099 LM rows remain identical after
  removing the new presentation field; 1,077 have valid precision operands and
  22 remain unavailable. No source snapshot mutation.
- Eight new regression tests cover the example, source scope, legacy inputs,
  missing/invalid/zero evidence, date alignment, both lanes, and the real JS cell
  renderer (including explicit null and zero changes).
- Full weekly suite: 346 tests passed. `verify_baseline.py` and
  `git diff --check` passed.

No BQ queries, Slack posts, Sheet writes or live report changes were made.
