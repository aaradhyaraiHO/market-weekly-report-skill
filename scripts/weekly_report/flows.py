"""
Week header — trend movers, week type, dual clock, themes (spec §4).

Top movers ranked by 4-week trailing average deviation (W0 − avg(W-1..W-4)),
with a seasonal context tag derived from LY same-week WoW:
  - "seasonal"         LY moved the same direction, ≥30% of the TY magnitude
  - "against season"   LY moved the opposite direction — needs investigation
  - "mostly TY"        same direction but LY was small relative to TY — real win/loss
  - "no LY"            no comparable LY data

The structural engine (LY-ratio-based expected WoW) is retained for week-type
classification, dual-clock resolution, and theme attribution — but NOT for
mover ranking, where it produced artifacts from LY/TY scale mismatches.

Emits snapshot['market_summary']['headlines']['flows' | 'week_type' |
'dual_clock' | 'themes' | 'routing'].
"""
from __future__ import annotations

import datetime as dt

EXPECTED_CAP = 1.0          # cap expected WoW at ±100% of last-week revenue
LY_BASE_FLOOR = 200.0       # no seasonal expectation below this LY base (raw WoW)
TY_LY_SCALE_CAP = 10.0     # if TY W-1 > 10× LY avg base, LY ratio is noise -> raw WoW
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
        if ratio is not None and wm1_rev and None not in (ly_tm2, ly_tm1, ly_t):
            ly_avg = (ly_tm2 + ly_tm1 + ly_t) / 3.0
            if ly_avg > 0 and wm1_rev / ly_avg > TY_LY_SCALE_CAP:
                ratio = None
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


TREND_MIN_REV = 200.0       # skip CEs with W-1 < this


def _seasonal_tag(delta_4w, ly_wow):
    """Classify the 4-week trend delta against LY same-week WoW."""
    if ly_wow is None:
        return "no LY"
    if abs(delta_4w) < 200:
        return ""
    same_dir = (delta_4w > 0) == (ly_wow > 0)
    if same_dir and abs(ly_wow) > abs(delta_4w) * 0.3:
        return "seasonal"
    elif not same_dir:
        return "against season"
    return "mostly TY"


def per_ce_trend(ces):
    """Per-CE trend movers: W0 − trailing 4-week avg, plus LY seasonal context.
    Returns [{ce_id, ce_name, delta_4w, raw_wow, ly_wow, tag, w0_rev}]."""
    out = []
    for ce in ces:
        wk = ce.get("weekly") or []
        wly = ce.get("weekly_ly") or []
        if len(wk) < 5:
            continue
        revs = [w.get("revenue") for w in wk[-5:]]
        if any(v is None for v in revs):
            continue
        wm4, wm3, wm2, wm1, w0 = revs
        if wm1 < TREND_MIN_REV:
            continue

        raw_wow = w0 - wm1
        avg4 = (wm1 + wm2 + wm3 + wm4) / 4.0
        delta_4w = w0 - avg4

        ly_wow = None
        ly_w0_rev = None
        if len(wly) >= 2:
            ly_w0_rev = wly[-1].get("revenue")
            ly_wm1 = wly[-2].get("revenue")
            if ly_w0_rev is not None and ly_wm1 is not None and ly_wm1 > TREND_MIN_REV:
                ly_wow = ly_w0_rev - ly_wm1

        yoy_growth = None
        if ly_w0_rev and ly_w0_rev > TREND_MIN_REV:
            yoy_growth = (w0 / ly_w0_rev) - 1.0

        out.append({
            "ce_id": ce["ce_id"],
            "ce_name": ce["ce_name"],
            "delta_4w": round(delta_4w, 0),
            "raw_wow": round(raw_wow, 0),
            "ly_wow": round(ly_wow, 0) if ly_wow is not None else None,
            "yoy_growth": round(yoy_growth, 2) if yoy_growth is not None else None,
            "tag": _seasonal_tag(delta_4w, ly_wow),
            "w0_rev": w0,
            "metadata": ce.get("metadata") or {},
        })
    return out


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

    # Trend movers — union of top-10-by-raw-WoW and top-10-by-4w-trend, deduped.
    # Captures both sudden drops (raw) and sustained declines (trend).
    trend = per_ce_trend(ces)
    by_raw_drop = sorted([c for c in trend if c["raw_wow"] < 0],
                         key=lambda c: c["raw_wow"])[:10]
    by_4w_drop = sorted([c for c in trend if c["delta_4w"] < 0],
                        key=lambda c: c["delta_4w"])[:10]
    seen = set()
    trend_drops = []
    for c in sorted(by_raw_drop + by_4w_drop,
                    key=lambda c: min(c["raw_wow"], c["delta_4w"])):
        if c["ce_id"] not in seen:
            seen.add(c["ce_id"])
            trend_drops.append(c)
    trend_drops = trend_drops[:10]

    by_raw_gain = sorted([c for c in trend if c["raw_wow"] > 0],
                         key=lambda c: -c["raw_wow"])[:10]
    by_4w_gain = sorted([c for c in trend if c["delta_4w"] > 0],
                        key=lambda c: -c["delta_4w"])[:10]
    seen = set()
    trend_gains = []
    for c in sorted(by_raw_gain + by_4w_gain,
                    key=lambda c: -max(c["raw_wow"], c["delta_4w"])):
        if c["ce_id"] not in seen:
            seen.add(c["ce_id"])
            trend_gains.append(c)
    trend_gains = trend_gains[:10]

    return {
        "raw": {"revenue_w0": round(raw_rev, 0),
                "wow_pct": round(raw_wow, 1) if raw_wow is not None else None,
                "yoy_pct": round(raw_yoy, 1) if raw_yoy is not None else None},
        "structural": {
            "gains_usd": round(G, 0), "losses_usd": round(L, 0), "net_usd": round(G - L, 0),
            "n80_gain": n80_gain, "n80_loss": n80_loss,
        },
        "trend": {
            "top_gainers": trend_gains,
            "top_droppers": trend_drops,
        },
        "week_type": wtype,
        "calibration": calibration,
        "dual_clock_label": dual,
        "clocks_disagree": disagree,
        "themes": themes[:12],
        "routing": {"mode": routing, "n80_loss": n80_loss},
    }
