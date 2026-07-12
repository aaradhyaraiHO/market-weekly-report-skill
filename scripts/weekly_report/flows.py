"""
Week header — structural flows, week type, dual clock, themes (spec §4).

The "what kind of week was it" engine. Raw WoW/YoY can mask the real story
(NA week 2026-06-29: raw net +$11K but structurally a "mostly loss" week vs the
July-4 LY ramp). So every CE's move is split into:

    structural delta = actual WoW $ − seasonally-EXPECTED WoW $

where the expected ramp is the ratio of 3-week *centered* LY averages
(LY[t-1,t,t+1] ÷ LY[t-2,t-1,t]), capped at ±100% of last-week revenue, with a
guard: no expectation when the LY base < $200 (fall back to raw WoW). Locked
after the v2 backtest 2026-07-07.

Emits snapshot['market_summary']['headlines']['flows' | 'week_type' |
'dual_clock' | 'themes' | 'routing'].
"""
from __future__ import annotations

import datetime as dt

EXPECTED_CAP = 1.0          # cap expected WoW at ±100% of last-week revenue
LY_BASE_FLOOR = 200.0       # no seasonal expectation below this LY base (raw WoW)
THEME_INDEX_MIN = 1.5       # contribution index >= this to flag a theme
THEME_MIN_CES = 3           # ... and at least this many CEs
THEME_MIN_FLOW = 2000.0     # ... and >= this many $ of flow (materiality floor, spec §4.2)
CONCENTRATION_PCT = 60.0    # top-CE share of theme delta > this -> demote to CE callout
N80_LOSS_SMALL = 4          # <= this many CEs = 80% of loss -> deep-dive cards
N80_LOSS_LARGE = 20         # >= this -> suppress cards, one market-level RCA
THEME_DIMS = ["subcategory", "category", "city", "management_type", "evolution", "tier"]


def _expected_ratio(ly_tm2, ly_tm1, ly_t, ly_tp1):
    """Centered LY WoW ratio avg(t-1,t,t+1) / avg(t-2,t-1,t). None when the LY
    base is too thin to trust (< $200) — caller falls back to raw WoW."""
    vals = [ly_tm2, ly_tm1, ly_t, ly_tp1]
    if any(v is None for v in vals):
        return None
    num = (ly_tm1 + ly_t + ly_tp1) / 3.0
    den = (ly_tm2 + ly_tm1 + ly_t) / 3.0
    if den < LY_BASE_FLOOR:
        return None
    return num / den


def _structural(w0_rev, wm1_rev, ratio):
    """(structural_delta_$, is_baseline_sensitive). structural = actual WoW −
    expected WoW; expected = wm1 × (ratio−1) capped at ±100% of wm1."""
    if w0_rev is None or wm1_rev is None:
        return None, False
    actual_wow = w0_rev - wm1_rev
    if ratio is None:
        return actual_wow, True   # no seasonal expectation -> raw WoW, flag it
    expected = wm1_rev * (ratio - 1.0)
    cap = EXPECTED_CAP * wm1_rev
    expected = max(-cap, min(cap, expected))
    return actual_wow - expected, False


def _n80(sorted_vals):
    """Count of top contributors making up 80% of the total magnitude."""
    total = sum(sorted_vals) or 1.0
    run, n = 0.0, 0
    for v in sorted_vals:
        run += v
        n += 1
        if run >= 0.8 * total:
            break
    return n


def per_ce_structural(ces, ly_forward_rev):
    """Per-CE W0 structural delta ($). Shared by the header and B4 (the gains-set
    membership + Louvre guard). `ly_forward_rev` = {ce_id: LY revenue of W0+1wk}.
    Returns [{ce_id, ce_name, w0_rev, struct, baseline_sensitive, metadata}]."""
    per_ce = []
    for ce in ces:
        wk = ce.get("weekly") or []
        wly = ce.get("weekly_ly") or []
        if len(wk) < 2 or len(wly) < 3:
            continue
        w0_rev = wk[-1].get("revenue")
        wm1_rev = wk[-2].get("revenue")
        ly_t, ly_tm1, ly_tm2 = wly[-1].get("revenue"), wly[-2].get("revenue"), wly[-3].get("revenue")
        ly_tp1 = ly_forward_rev.get(ce["ce_id"])
        ratio = _expected_ratio(ly_tm2, ly_tm1, ly_t, ly_tp1)
        struct, bl_sensitive = _structural(w0_rev, wm1_rev, ratio)
        if struct is None:
            continue
        per_ce.append({
            "ce_id": ce["ce_id"], "ce_name": ce["ce_name"],
            "w0_rev": w0_rev or 0.0, "struct": struct,
            "baseline_sensitive": bl_sensitive,
            "metadata": ce.get("metadata") or {},
        })
    return per_ce


def build_header(ces, ly_forward_rev, market_weekly, w0_start: dt.date,
                 large_threshold: float | None = None):
    """Compute the week header. `ly_forward_rev` = {ce_id: LY revenue of W0+1wk}.

    `large_threshold` — the $ magnitude above which a gains/loss flow counts as
    "large" for the week-type label. Calibrated per market from the trailing
    52-week WoW-delta distribution (build_snapshot passes p75). When None, falls
    back to the old market-size floor (max($500, 0.5% of W0 revenue))."""
    per_ce = per_ce_structural(ces, ly_forward_rev)

    gainers = sorted([c for c in per_ce if c["struct"] > 0], key=lambda c: -c["struct"])
    droppers = sorted([c for c in per_ce if c["struct"] < 0], key=lambda c: c["struct"])
    G = sum(c["struct"] for c in gainers)
    L = -sum(c["struct"] for c in droppers)   # positive magnitude
    n80_gain = _n80([c["struct"] for c in gainers])
    n80_loss = _n80([-c["struct"] for c in droppers])

    # raw clocks from the market weekly series
    w0_row = next((w for w in market_weekly if w["week"] == w0_start.isoformat()), market_weekly[-1])
    idx = market_weekly.index(w0_row)
    wm1_row = market_weekly[idx - 1] if idx > 0 else None
    raw_rev = w0_row.get("revenue") or 0.0
    raw_wow = (100.0 * (raw_rev / wm1_row["revenue"] - 1)) if (wm1_row and wm1_row.get("revenue")) else None
    raw_yoy = w0_row.get("yoy_pct")

    # week type (5) — the "large" threshold. Prefer the per-market 52w-percentile
    # calibration (spec §4) passed in by build_snapshot; fall back to the old
    # market-size floor (max($500, 0.5% of W0 revenue)) when unavailable.
    old_floor = max(500.0, 0.005 * raw_rev)
    floor = large_threshold if large_threshold is not None else old_floor
    calibration = {
        "method": "p75_52w" if large_threshold is not None else "floor",
        "threshold_usd": round(floor, 0),
    }
    both_large = G > floor and L > floor
    if both_large:
        net = G - L
        wtype = (f"Both large — gains beat by ${net:,.0f}" if net >= 0
                 else f"Both large — losses beat by ${-net:,.0f}")
    elif G > L and G > floor:
        wtype = "Mostly gains"
    elif L > G and L > floor:
        wtype = "Mostly loss"
    else:
        wtype = "Mostly stable"

    # dual-clock resolution — structural verdict reconciled against the raw clock.
    loss_dom = L > G
    if loss_dom and raw_wow is not None and raw_wow >= 0:
        dual = "UNDER-RAMPING vs LY seasonality"   # +raw but structurally behind
    elif loss_dom and raw_wow is not None and raw_wow < 0:
        dual = "MOSTLY LOSS"
    elif (not loss_dom) and raw_wow is not None and raw_wow < 0:
        dual = "BEATING SEASONALITY"                # −raw but structurally ahead
    else:
        dual = wtype
    disagree = (raw_wow is not None and ((raw_wow >= 0) != (G - L >= 0)))

    # theme attribution — contribution index = share-of-loss ÷ share-of-revenue,
    # mechanical across every metadata dim. Flag index >= 1.5x, >= 3 CEs.
    tot_rev = sum(c["w0_rev"] for c in per_ce) or 1.0
    themes = []
    for dim in THEME_DIMS:
        groups: dict[str, list] = {}
        for c in per_ce:
            v = c["metadata"].get(dim)
            if v:
                groups.setdefault(v, []).append(c)
        for val, members in groups.items():
            for direction, pool_mag in (("loss", L), ("gain", G)):
                signed = [m["struct"] for m in members if (m["struct"] < 0) == (direction == "loss")]
                if len(signed) < THEME_MIN_CES:
                    continue
                mag = abs(sum(signed))
                if mag <= 0 or pool_mag <= 0:
                    continue
                # $ materiality floor (spec §4.2): a theme must be a real chunk of
                # the flow, not a high-index sliver — kills the trivial-$ blowup
                # (e.g. a $14 city group scoring 150x). Scales to the pool.
                if mag < max(THEME_MIN_FLOW, 0.03 * pool_mag):
                    continue
                grp_rev = sum(m["w0_rev"] for m in members) or 1.0
                share_of_flow = mag / pool_mag
                share_of_rev = grp_rev / tot_rev
                index = share_of_flow / share_of_rev if share_of_rev else None
                if index is None or index < THEME_INDEX_MIN:
                    continue
                top_share = max(abs(s) for s in signed) / mag * 100.0
                themes.append({
                    "dim": dim, "value": val, "direction": direction,
                    "n_ces": len(signed),
                    "flow_usd": round(mag, 0),
                    "share_of_flow_pct": round(100.0 * share_of_flow, 0),
                    "share_of_rev_pct": round(100.0 * share_of_rev, 1),
                    "index": round(index, 1),
                    "concentrated": top_share > CONCENTRATION_PCT,   # driven by one CE
                })
    themes.sort(key=lambda t: -t["index"])

    routing = ("market_rca" if n80_loss >= N80_LOSS_LARGE
               else "cards" if n80_loss <= N80_LOSS_SMALL else "mixed")

    return {
        "raw": {"revenue_w0": round(raw_rev, 0),
                "wow_pct": round(raw_wow, 1) if raw_wow is not None else None,
                "yoy_pct": round(raw_yoy, 1) if raw_yoy is not None else None},
        "structural": {
            "gains_usd": round(G, 0), "losses_usd": round(L, 0), "net_usd": round(G - L, 0),
            "n80_gain": n80_gain, "n80_loss": n80_loss,
            "top_gainers": [{"ce_id": c["ce_id"], "ce_name": c["ce_name"],
                             "struct_usd": round(c["struct"], 0),
                             "baseline_sensitive": c["baseline_sensitive"]} for c in gainers[:10]],
            "top_droppers": [{"ce_id": c["ce_id"], "ce_name": c["ce_name"],
                              "struct_usd": round(c["struct"], 0),
                              "baseline_sensitive": c["baseline_sensitive"]} for c in droppers[:10]],
        },
        "week_type": wtype,
        "calibration": calibration,   # {method: p75_52w|floor, threshold_usd}
        "dual_clock_label": dual,
        "clocks_disagree": disagree,
        "themes": themes[:12],
        "routing": {"mode": routing, "n80_loss": n80_loss},
    }
