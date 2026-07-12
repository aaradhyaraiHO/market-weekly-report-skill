"""
Bucket B3 — Losing Ground (weekly forecasting bucket).

Spec: thoughts/shared/market-report-weekly-v1-spec.md §5 (B3). The only
*forecasting* bucket — B1/B2 report what happened; B3 makes a falsifiable
prediction: "this Pro+ CE is on pace to end the month ≥1 band lower."

Band infra is IMPORTED from scripts/ce_buckets/bands.py (shared, cross-cadence),
same pattern as B1's truth-table constants.

APPROXIMATION NOTE: the spec projects month-end via MTD ÷ LY-month daily-shape
(weekday-corrected), which needs monthly daily data the weekly mart doesn't
carry. V1 uses a weekly-run-rate pace signal instead: recent-4wk run-rate band
vs the established trailing-13wk band. Same intent (recent momentum has dropped
below the held level), falsifiable, no monthly fetch. Reconcile with the team
band sheet in a later hardening pass.

Emits snapshot['bucket_b3'].
"""
from __future__ import annotations

import os
import sys

WEEKS_TO_MONTH = 4.345               # weekly revenue -> monthly run-rate
RECENT_WEEKS = 4                     # recent-pace window
MIN_WEEKS_ON_PACE = 2                # one week is weather, two is a trend
DORMANT_CLICKS_YOY = -0.85           # paid clicks 4w YoY < this = dormant (revive first)
RPC_FALL = -0.20                     # recent RPC vs established < this = inputs decaying
ROI_OPT_IMPROVE_PP = 20.0            # ROI YoY improved >= this pp ...
ROI_OPT_FLOOR = 120.0                # ... AND ROI > 120  => volume-for-efficiency (loosen)
ROI_OPT_STANDALONE = 160.0           # OR ROI > 160 alone


def _import_bands():
    here = os.path.dirname(os.path.abspath(__file__))
    for root in [os.path.abspath(os.path.join(here, "..", "..")), os.path.expanduser("~/analytics")]:
        if os.path.isdir(os.path.join(root, "scripts", "ce_buckets")):
            if root not in sys.path:
                sys.path.insert(0, root)
            from scripts.ce_buckets import bands  # noqa: E402
            return bands
    return None


_BANDS = _import_bands()


def _rr(series):
    """Monthly run-rate ($) from a weekly-revenue list (mean × weeks-per-month)."""
    vals = [v for v in series if v is not None]
    if not vals:
        return 0.0
    return sum(vals) / len(vals) * WEEKS_TO_MONTH


def _reason(recent_clicks, ly_clicks, rpc_recent, rpc_est, roi_ty, roi_ly):
    """First-match cascade (spec §5 B3): dormant -> inputs -> paid-opt -> manual."""
    # 1. dormant — dead campaigns make every downstream metric meaningless
    if ly_clicks and recent_clicks is not None:
        if (recent_clicks / ly_clicks - 1) < DORMANT_CLICKS_YOY:
            return "dormant", "[Perf] revive paused campaigns"
    # 2. inputs — each click worth less (LP/feed/pricing)
    if rpc_est and rpc_recent is not None:
        if (rpc_recent / rpc_est - 1) < RPC_FALL:
            return "inputs", "[Perf/SP] fix LP/feed/pricing (RPC decaying)"
    # 3. paid optimization — volume traded for efficiency, partly self-inflicted
    if roi_ty is not None and roi_ly is not None:
        if ((roi_ty - roi_ly) >= ROI_OPT_IMPROVE_PP and roi_ty > ROI_OPT_FLOOR) or roi_ty > ROI_OPT_STANDALONE:
            return "paid-optimization", "[Perf] loosen ROI floor / scale"
    # 4. manual — a human owes a diagnosis
    return "manual", "[Growth] structural investigation"


def _mean(vals):
    v = [x for x in vals if x is not None]
    return (sum(v) / len(v)) if v else None


def build_bucket_b3(ces):
    """
    Rows for Pro+ CEs projected to fall >=1 band, on pace >=2 consecutive weeks.
    Ranked by projected monthly loss $ (established RR − recent RR). 🍂 seasonal
    tag deferred (needs the events registry) — noted, not excluded.
    """
    if _BANDS is None:
        print("  [bucket_b3] WARN: bands.py not importable — B3 skipped")
        return []

    rows = []
    for ce in ces:
        wk = ce.get("weekly") or []
        wly = ce.get("weekly_ly") or []
        if len(wk) < RECENT_WEEKS + 2:
            continue
        rev = [w.get("revenue") for w in wk]
        established_rr = _rr(rev[:-RECENT_WEEKS] or rev)      # trailing level (excl. recent window)
        recent_rr = _rr(rev[-RECENT_WEEKS:])                  # recent pace

        band_est = _BANDS.band_for(established_rr, "monthly")
        band_recent = _BANDS.band_for(recent_rr, "monthly")
        if not _BANDS.is_pro_plus(band_est):
            continue
        fall = _BANDS.band_rank(band_est) - _BANDS.band_rank(band_recent)
        if fall < 1:
            continue

        # weeks-on-pace: consecutive trailing weeks below the established weekly level
        est_weekly = established_rr / WEEKS_TO_MONTH
        streak = 0
        for r in reversed(rev):
            if r is not None and r < est_weekly:
                streak += 1
            else:
                break
        if streak < MIN_WEEKS_ON_PACE:
            continue

        # cascade inputs
        recent_clicks = sum((w.get("clicks") or 0) for w in wk[-RECENT_WEEKS:])
        ly_clicks = sum((w.get("paid_clicks") or 0) for w in wly[-RECENT_WEEKS:])
        rpc_recent = _mean([w.get("rpc") for w in wk[-RECENT_WEEKS:]])
        rpc_est = _mean([w.get("rpc") for w in wk[:-RECENT_WEEKS]])
        roi_ty = _mean([w.get("roi1_pct") for w in wk[-RECENT_WEEKS:]])
        roi_ly = _mean([w.get("roi1_pct") for w in wly[-RECENT_WEEKS:]])
        reason, action = _reason(recent_clicks, ly_clicks, rpc_recent, rpc_est, roi_ty, roi_ly)

        band_peak = max((_BANDS.band_for(r, "monthly") for r in rev if r), key=_BANDS.band_rank, default=band_est)
        proj_loss = round(established_rr - recent_rr, 0)

        rows.append({
            "ce_id": ce["ce_id"],
            "ce_name": ce["ce_name"],
            "band_now": band_est,
            "band_projected": band_recent,
            "band_peak": band_peak,
            "fall_bands": fall,
            "weeks_on_pace": streak,
            "reason": reason,
            "action": action,
            "established_rr": round(established_rr, 0),
            "recent_rr": round(recent_rr, 0),
            "projected_monthly_loss": proj_loss,
            "rpc_change_pct": round(100.0 * (rpc_recent / rpc_est - 1), 1) if (rpc_est and rpc_recent is not None) else None,
            "clicks_yoy_pct": round(100.0 * (recent_clicks / ly_clicks - 1), 1) if ly_clicks else None,
            "roi1_yoy_pp": round(roi_ty - roi_ly, 1) if (roi_ty is not None and roi_ly is not None) else None,
        })

    rows.sort(key=lambda r: -r["projected_monthly_loss"])
    return rows
