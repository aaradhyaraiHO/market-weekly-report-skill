"""
Bucket B1 — ROI / CM2 Movement (weekly flow view).

Spec: thoughts/shared/market-report-weekly-v1-spec.md §5 (B1). This is the
weekly *movement* view of the monthly ROI/CM2 Optimization bucket: a CE renders
only when its ROI state CHANGED this week (entered / escalated / exited), never
standing membership.

Cross-cadence consistency (spec §5 "one shared constants file imported by both
cadences"): the ROI truth-table thresholds are IMPORTED from
`scripts.ce_buckets.classify`, not re-hardcoded. The only weekly-specific
additions are the movement triggers (30pp WoW drop, 100% floor, hysteresis) and
the chronic clock in WEEKS (monthly uses months).

Emits one row per CE that moved this week -> snapshot['bucket_b1'].
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import pandas as pd

import config

# --------------------------------------------------------------------------- #
# Shared constants — imported from the monthly ce_buckets engine (spec §5).
# Resolve the repo that carries scripts/ce_buckets: the merged repo (this tree
# after worktrees land in main) or the main analytics repo during isolated
# worktree development.
# --------------------------------------------------------------------------- #
def _import_ce_bucket_constants():
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.abspath(os.path.join(here, "..", "..")),   # merged: <repo>/scripts/weekly_report -> <repo>
        os.path.expanduser("~/analytics"),                  # isolated worktree -> main repo
    ]
    for root in candidates:
        if os.path.isdir(os.path.join(root, "scripts", "ce_buckets")):
            if root not in sys.path:
                sys.path.insert(0, root)
            from scripts.ce_buckets.classify import (  # noqa: E402
                ROI_PAUSE_FLOOR, ROI_TRANSITION_FLOOR,
                RPC_CLIFF_THRESHOLD, RPC_GRADUAL_THRESHOLD,
            )
            return dict(
                PAUSE_FLOOR=ROI_PAUSE_FLOOR, TRANSITION_FLOOR=ROI_TRANSITION_FLOOR,
                RPC_CLIFF=RPC_CLIFF_THRESHOLD, RPC_GRADUAL=RPC_GRADUAL_THRESHOLD,
            )
    # Fallback (import unavailable): mirror the shared constants, flagged.
    print("  [bucket_b1] WARN: scripts/ce_buckets not importable — using mirrored constants")
    return dict(PAUSE_FLOOR=20.0, TRANSITION_FLOOR=70.0, RPC_CLIFF=-0.25, RPC_GRADUAL=-0.10)


_C = _import_ce_bucket_constants()
PAUSE_FLOOR = _C["PAUSE_FLOOR"]            # ROI% < this -> Pause/Critical
TRANSITION_FLOOR = _C["TRANSITION_FLOOR"]  # 70..100 -> Transition
RPC_CLIFF = _C["RPC_CLIFF"]                # rpc_vs_4w < this = a recent cliff (new input signal)
RPC_GRADUAL = _C["RPC_GRADUAL"]            # -0.25..-0.10 = structural gradual decay

# Weekly-specific additions (spec §5 shared-constants list; weekly adds these).
ROI_FLOOR = 100.0            # bleed floor: spend*(ROI-1) is only negative below 100
ROI_DROP_PP = 30.0           # CLIFF trigger: >30pp WoW ROI drop AND lands < target
CHRONIC_WEEKS = 6            # weekly chronic clock (monthly = CHRONIC_MONTHS=3)
CRITICAL_FLOOR = PAUSE_FLOOR # ROI < 20 = Critical
HYST_EXIT = 105.0            # EXIT hysteresis: back above this to leave (proposed; §9.5 pending perf)
SPEND_FLOOR_4W = 1000.0      # B1 spend floor (matches monthly ROI/CM2 gate)
MARKET_ROI_TARGET_PCT = 145.0  # fallback target when a CE has no campaign tROAS (perf 2026 target)


# --------------------------------------------------------------------------- #
# Weekly truth table — forked from classify.roi_cm2_recommendation, keyed on
# WEEKS (CHRONIC_WEEKS) instead of months, + the weekly-only Monitor/Cliff
# branch (spec gap #18: cliff entry with ROI still >=100).
# --------------------------------------------------------------------------- #
def weekly_roi_recommendation(roi, weeks_below_100, rpc_vs_4w):
    """(recommendation, sub_reason) from ROI band, weekly patience, RPC diagnosis."""
    roi = roi if roi is not None else 0.0
    weeks = weeks_below_100 or 0
    rpc = rpc_vs_4w if rpc_vs_4w is not None else 0.0

    if roi >= ROI_FLOOR:
        # weekly-only branch: a cliff entry can land above 100 (gap #18)
        if rpc < RPC_CLIFF:
            return "Monitor", "Cliff"
        return "", ""   # healthy — no recommendation

    if roi < CRITICAL_FLOOR:
        return "Pause", "Critical"

    if roi < TRANSITION_FLOOR:  # 20..70
        chronic = weeks >= CHRONIC_WEEKS
        cliff = rpc < RPC_CLIFF
        if chronic and not cliff:
            gradual = RPC_CLIFF <= rpc <= RPC_GRADUAL
            return "Pause", ("Structural" if gradual else "Chronic")
        if chronic and cliff:
            return "Investigate", "Chronic + new signal"
        if not chronic and cliff:
            return "Investigate", "Input-induced"
        return "Investigate", "Recent entry"

    return "Transition", ""   # 70..100


def _action(rec, sub):
    """Default one-line action w/ owner tag (forked from classify.bucket_action home==2)."""
    if rec == "Pause":
        return f"[Perf] pause — {sub}" if sub else "[Perf] pause"
    if rec == "Investigate":
        return f"[Perf] investigate — {sub}" if sub else "[Perf] investigate"
    if rec == "Transition":
        return "[Perf] transition off paid"
    if rec == "Monitor":
        return "[Perf] monitor — RPC cliff, ROI still ≥100%"
    return ""


# --------------------------------------------------------------------------- #
# Movement classification (the weekly router) — NEW / CLIFF / ESCALATION / EXIT
# --------------------------------------------------------------------------- #
def _movement(roi_w0, roi_wm1, weeks_below_100, target):
    """
    Which door did this CE come through this week? Returns (flag, is_good_news).
      CLIFF       >30pp WoW drop landing < target ("something happened")
      NEW         entered via grinding (2nd consecutive wk < 100%)
      ESCALATION  already in, worsened (fell to Critical <20, or hit chronic wk-6)
      EXIT        back above floor + hysteresis (good news — rendered deliberately)
      None        no state change (standing count-line only)
    """
    drop_pp = (roi_wm1 - roi_w0) if (roi_w0 is not None and roi_wm1 is not None) else None
    below = roi_w0 is not None and roi_w0 < ROI_FLOOR
    was_below = roi_wm1 is not None and roi_wm1 < ROI_FLOOR

    # EXIT: was below floor, now cleared hysteresis
    if was_below and roi_w0 is not None and roi_w0 >= HYST_EXIT:
        return "EXIT", True
    if not below:
        return None, False   # healthy and stayed healthy

    # below floor this week:
    if drop_pp is not None and drop_pp > ROI_DROP_PP and (target is None or roi_w0 < target):
        return "CLIFF", False
    if was_below:
        # already in last week — ESCALATION only on a NEW worsening event this
        # week (newly fell to Critical, or just crossed the chronic wk-6 clock),
        # never every week a chronic CE sits below floor (that is standing).
        newly_critical = roi_w0 < CRITICAL_FLOOR and not (roi_wm1 < CRITICAL_FLOOR)
        newly_chronic = (weeks_below_100 or 0) == CHRONIC_WEEKS
        if newly_critical or newly_chronic:
            return "ESCALATION", False
        return None, False   # still in, no worse -> standing (count-line, not a row)
    # newly below this week without a cliff = grinding entry (2nd-wk door)
    if (weeks_below_100 or 0) >= 2:
        return "NEW", False
    return None, False


# --------------------------------------------------------------------------- #
# tROAS target per CE (spend-weighted, current), fallback to market target
# --------------------------------------------------------------------------- #
def _ce_troas_targets(troas: pd.DataFrame, w0_start: dt.date, w0_end: dt.date) -> dict:
    if troas is None or troas.empty:
        return {}
    win = troas[(troas["report_date"] >= w0_start) & (troas["report_date"] <= w0_end)].copy()
    if win.empty:
        return {}
    win = win[win["troas"].notna() & (win["troas"] > 0)]
    if win.empty:
        return {}
    out = {}
    for cid, g in win.groupby("combined_entity_id"):
        sw = float(g["spend"].sum())
        if sw > 0:
            out[str(cid)] = float((g["troas"] * g["spend"]).sum() / sw)
        else:
            out[str(cid)] = float(g["troas"].mean())
    return out


def _rpc_vs_4w(weekly: list) -> float | None:
    """Latest-week RPC / mean(prior 4 wks RPC) - 1. None if insufficient data."""
    rpcs = [w.get("rpc") for w in weekly]
    cur = rpcs[-1]
    prior = [r for r in rpcs[-5:-1] if r is not None]
    if cur is None or len(prior) < 2:
        return None
    base = sum(prior) / len(prior)
    return (cur / base - 1) if base else None


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
GRAY_ZONE_PP = config.GRAY_ZONE_PP   # ±5pp around each B1 ROI trigger
ZERO_SPEND_WEEKLY_FLOOR = 10.0       # W0 spend below this = "zero spend" (catches rounding dust)


def build_bucket_b1(ces, streak_by_ce, troas, w0_start, w0_end):
    """
    Build the B1 ROI/CM2 Movement rows + supplementary signals.

    Returns dict with keys:
      rows           — movement rows (NEW/CLIFF/ESCALATION/EXIT)
      standing_count — CEs below floor with no movement
      zero_spend_exits — CEs that were below floor last week but went to ~$0 spend
      burn_line      — aggregate of sub-$1k/4w bleeders {count, bleed_wk_total}
      gray_zone      — {near_floor, near_transition, near_critical} counts
    """
    targets = _ce_troas_targets(troas, w0_start, w0_end)
    rows, standing = [], 0
    zero_spend_exits = []
    burn_count, burn_bleed = 0, 0.0
    gz_floor, gz_transition, gz_critical = 0, 0, 0

    for ce in ces:
        weekly = ce.get("weekly") or []
        if len(weekly) < 2:
            continue
        w0, wm1 = weekly[-1], weekly[-2]
        roi_w0, roi_wm1 = w0.get("roi_pct"), wm1.get("roi_pct")
        spend_w0 = w0.get("spend") or 0.0
        spend_4w = sum((w.get("spend") or 0.0) for w in weekly[-4:])

        # --- P2.1: zero-spend transition flag ---
        # CE was below ROI floor last week (had meaningful spend) but this week
        # dropped to near-zero spend → paused, not recovered. The spend gate
        # would silently swallow it.
        if spend_w0 < ZERO_SPEND_WEEKLY_FLOOR and roi_wm1 is not None and roi_wm1 < ROI_FLOOR:
            spend_wm1 = wm1.get("spend") or 0.0
            if spend_wm1 >= ZERO_SPEND_WEEKLY_FLOOR:
                zero_spend_exits.append({
                    "ce_id": ce["ce_id"],
                    "ce_name": ce["ce_name"],
                    "roi_last_pct": round(roi_wm1, 1),
                    "spend_last": round(spend_wm1, 2),
                })

        # --- P2.2: long-tail burn line ---
        # CEs that are bleeding (ROI < 100) but below the $1k/4w spend gate.
        if spend_4w < SPEND_FLOOR_4W:
            if roi_w0 is not None and roi_w0 < ROI_FLOOR and spend_w0 > 0:
                bleed_wk = spend_w0 * (roi_w0 / 100.0 - 1.0)
                burn_count += 1
                burn_bleed += bleed_wk
            continue

        # --- P2.3: gray-zone counters ---
        if roi_w0 is not None:
            if abs(roi_w0 - ROI_FLOOR) <= GRAY_ZONE_PP:
                gz_floor += 1
            if abs(roi_w0 - TRANSITION_FLOOR) <= GRAY_ZONE_PP:
                gz_transition += 1
            if abs(roi_w0 - CRITICAL_FLOOR) <= GRAY_ZONE_PP:
                gz_critical += 1

        weeks_below = streak_by_ce.get(ce["ce_id"], 0)
        target = targets.get(ce["ce_id"], MARKET_ROI_TARGET_PCT)
        flag, good = _movement(roi_w0, roi_wm1, weeks_below, target)

        # standing (below floor, no movement) -> count line, not a row
        if flag is None:
            if roi_w0 is not None and roi_w0 < ROI_FLOOR:
                standing += 1
            continue

        rpc_v4 = _rpc_vs_4w(weekly)
        rec, sub = weekly_roi_recommendation(roi_w0, weeks_below, rpc_v4)
        bleed = spend_w0 * ((roi_w0 or 0.0) / 100.0 - 1.0)

        rows.append({
            "ce_id": ce["ce_id"],
            "ce_name": ce["ce_name"],
            "movement": flag,
            "is_exit": good,
            "roi_w0_pct": round(roi_w0, 1) if roi_w0 is not None else None,
            "roi_wm1_pct": round(roi_wm1, 1) if roi_wm1 is not None else None,
            "roi_drop_pp": round(roi_wm1 - roi_w0, 1) if (roi_w0 is not None and roi_wm1 is not None) else None,
            "troas_target_pct": round(target, 1) if target is not None else None,
            "weeks_below_100": weeks_below,
            "rpc_vs_4w_pct": round(100.0 * rpc_v4, 1) if rpc_v4 is not None else None,
            "recommendation": rec,
            "sub_reason": sub,
            "action": _action(rec, sub),
            "cm2_bleed_wk": round(bleed, 2),
            "spend_w0": round(spend_w0, 2),
        })

    rows.sort(key=lambda r: (r["is_exit"], r["cm2_bleed_wk"]))

    return {
        "rows": rows,
        "standing_count": standing,
        "zero_spend_exits": zero_spend_exits,
        "burn_line": {"count": burn_count, "bleed_wk_total": round(burn_bleed, 2)},
        "gray_zone": {
            "near_floor": gz_floor,
            "near_transition": gz_transition,
            "near_critical": gz_critical,
        },
    }
