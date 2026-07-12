"""
Bucket B4 — Scale Windows (weekly).

Spec: thoughts/shared/market-report-weekly-v1-spec.md §5 (B4). B1–B3 hand out
homework; B4 hands out BUDGET, so the burden of proof runs the other way — a CE
must clear a lane's gate to earn a scale signal.

Three lanes (2026-07-09):
  (a) slow/sticky — in the 80%-gains set >=2 wks AND ROI above target+margin
  (b) ⚡ NEW WAVE — a B2 up-alert, entering immediately, BUT only if structural
      revenue >= 0 (the Louvre guard: margin-up + revenue-down = pricing/TR
      investigation, never scale); probe-capped +~20%
  (c) 🔄 LOADING — ROI improving >=2wks AND crossing 110% AND CVR rising;
      exempt from the above-target gate (it isn't above target yet — the point)

Gain floor = max($500, 0.5% of trailing-4w weekly market revenue). SIS gate and
supply-headroom are spec gates but SIS is deferred (weekly pull not built) — the
action notes "check SIS/supply" rather than blocking. Zero-spend flip: spend=$0
=> "launch campaigns", never "scale". Ranked by est. incremental $/wk.

Emits snapshot['bucket_b4'].
"""
from __future__ import annotations

ROI_TARGET_PCT = 145.0        # market ROI target (perf 2026); lane-a gate = target + margin
LANE_A_MARGIN_PP = 10.0       # "above target+margin" headroom for full-size scaling
LOADING_CROSS_PCT = 110.0     # lane-c: ROI must cross this
PROBE_UPLIFT_PCT = 20.0       # probe-capped action size for NEW WAVE / LOADING
GAIN_FLOOR_ABS = 500.0        # flat arm of the gain floor
GAIN_FLOOR_PCT = 0.005        # proportional arm: 0.5% of trailing-4w weekly market rev
MIN_STICKY_WEEKS = 2


def _mean(vals):
    v = [x for x in vals if x is not None]
    return (sum(v) / len(v)) if v else None


def _roi_improving_2wk(roi_series):
    """True if ROI rose in each of the last 2 weeks (>=3 points needed)."""
    r = [x for x in roi_series if x is not None]
    if len(r) < 3:
        return False
    return r[-1] > r[-2] > r[-3]


def _cvr_rising(cvr_series):
    r = [x for x in cvr_series if x is not None]
    if len(r) < 2:
        return False
    return r[-1] > r[-2]


def build_bucket_b4(ces, struct_by_ce, up_swing_ids, market_weekly):
    """
    struct_by_ce   : {ce_id: W0 structural delta $} (from flows.per_ce_structural)
    up_swing_ids   : set of ce_ids with a B2 up-alert this week (NEW WAVE feeder)
    market_weekly  : for the proportional gain floor (trailing-4w weekly rev)
    """
    # gain floor from trailing-4w weekly market revenue
    recent = [w.get("revenue") or 0.0 for w in market_weekly[-4:]]
    mkt_wk_rev = (sum(recent) / len(recent)) if recent else 0.0
    gain_floor = max(GAIN_FLOOR_ABS, GAIN_FLOOR_PCT * mkt_wk_rev)

    ce_by_id = {c["ce_id"]: c for c in ces}
    rows = []

    def _emit(ce, lane, lane_label, roi_w0, gain, gate_note, action):
        wk = ce.get("weekly") or []
        spend_w0 = (wk[-1].get("spend") if wk else None) or 0.0
        rows.append({
            "ce_id": ce["ce_id"],
            "ce_name": ce["ce_name"],
            "lane": lane,
            "lane_label": lane_label,
            "roi_w0_pct": round(roi_w0, 1) if roi_w0 is not None else None,
            "structural_gain_wk": round(gain, 0),
            "est_incremental_wk": round(gain * (PROBE_UPLIFT_PCT / 100.0), 0) if lane != "a" else round(gain, 0),
            "spend_w0": round(spend_w0, 2),
            "gate_note": gate_note,
            "action": action,
        })

    seen = set()
    for ce_id, struct in struct_by_ce.items():
        ce = ce_by_id.get(ce_id)
        if ce is None:
            continue
        wk = ce.get("weekly") or []
        if not wk:
            continue
        roi_w0 = wk[-1].get("roi_pct")
        roi_series = [w.get("roi_pct") for w in wk]
        cvr_series = [w.get("cvr_pct") for w in wk]
        spend_w0 = wk[-1].get("spend") or 0.0
        rev = [w.get("revenue") for w in wk]

        # zero-spend flip — a scale signal on $0 spend is a launch, not a scale
        zero_spend = spend_w0 <= 0

        # --- lane (b) ⚡ NEW WAVE: B2 up-alert + Louvre guard (structural rev >= 0) ---
        if ce_id in up_swing_ids and struct >= 0 and struct >= gain_floor:
            act = ("[Growth] launch campaigns (spend $0)" if zero_spend
                   else f"[Perf] probe scale +{PROBE_UPLIFT_PCT:.0f}% — check SIS/supply before")
            _emit(ce, "b", "⚡ NEW WAVE", roi_w0, struct, "B2 up-alert · structural rev ≥ 0", act)
            seen.add(ce_id)
            continue

        # --- lane (a) sticky: in gains set, sticky >=2wks, ROI above target+margin ---
        if struct >= gain_floor and roi_w0 is not None and roi_w0 >= ROI_TARGET_PCT + LANE_A_MARGIN_PP:
            # stickiness proxy: revenue grew in each of the last 2 weeks
            sticky = len(rev) >= 3 and rev[-1] is not None and rev[-2] is not None and rev[-3] is not None \
                and rev[-1] > rev[-2] > rev[-3]
            if sticky:
                act = ("[Growth] launch campaigns (spend $0)" if zero_spend
                       else "[Perf/Growth] scale — sticky gainer above target")
                _emit(ce, "a", "sticky gainer", roi_w0, struct,
                      f"≥{MIN_STICKY_WEEKS}wk sticky · ROI ≥ target+{LANE_A_MARGIN_PP:.0f}pp", act)
                seen.add(ce_id)
                continue

        # --- lane (c) 🔄 LOADING: ROI improving >=2wks, crossing 110, CVR rising ---
        if (roi_w0 is not None and roi_w0 >= LOADING_CROSS_PCT
                and _roi_improving_2wk(roi_series) and _cvr_rising(cvr_series)):
            act = f"[Perf] probe scale +{PROBE_UPLIFT_PCT:.0f}% — loading (ROI rising, CVR up)"
            _emit(ce, "c", "🔄 LOADING", roi_w0, max(struct, 0.0),
                  "ROI improving 2wk · crossed 110% · CVR rising", act)
            seen.add(ce_id)

    # rank by est incremental $/wk desc
    rows.sort(key=lambda r: -r["est_incremental_wk"])
    return rows
