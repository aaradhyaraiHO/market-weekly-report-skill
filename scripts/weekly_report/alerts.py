"""
Fluctuation engine (Bucket 1).

ONE rule (2026-08-03, simplified further 2026-08-08):
  * CM1/conv and RPC: pooled ratio over the FULL report week (Sun-Sat) vs the
    prior 3 weeks (21 days), flagged at >=35% change, with volume floors on both
    legs. That is the whole qualifier — no daily engine, no 3-day alert, and no
    WoW side-paths (CVR-WoW and collective-driver-WoW were removed 2026-08-08;
    see build_bucket1).
Plus a bid-change innocence check (historized campaign tROAS diffs) and an
optional availability evidence join.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

import config

# --------------------------------------------------------------------------- #
# Weekly L3W-vs-W0 ratio alert (replaces daily POF engine, 2026-08-03)
# --------------------------------------------------------------------------- #
def _weekly_ratio_alert(
    daily: pd.DataFrame,
    ce_id: str,
    value_col: str,
    denom_col: str,
    volume_col: str,
    w0_start: dt.date,
    w0_end: dt.date,
) -> dict | None:
    """
    Pooled ratio (Σvalue / Σdenom) over the report week [w0_start, w0_end] vs
    the prior 3 weeks [w0_start−21, w0_start−1]. Flags at >=35% change.

    Volume gates (both sides — a ratio is only as trustworthy as its thinner leg):
      W0       >= MIN_ORDERS_WK, pro-rated to the window length (matches the WoW paths'
                 _mat_floors convention, so a partial window isn't stealth-tightened)
      baseline >= the same floor scaled to 21 days (i.e. 3x a full week)
    """
    d = daily[daily["combined_entity_id"] == ce_id].copy()
    if d.empty:
        return None
    for col in (value_col, denom_col, volume_col):
        if col in d:
            d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0.0)

    l3w_days = config.FLUCTUATION_L3W_DAYS
    l3w_start = w0_start - dt.timedelta(days=l3w_days)
    l3w_end = w0_start - dt.timedelta(days=1)

    def _agg(lo, hi):
        mask = [(lo <= x <= hi) for x in d["report_date"]]
        s = d[mask]
        return float(s[value_col].sum()), float(s[denom_col].sum()), float(s[volume_col].sum())

    val_w0, den_w0, vol_w0 = _agg(w0_start, w0_end)
    val_l3w, den_l3w, vol_l3w = _agg(l3w_start, l3w_end)

    n_days = (w0_end - w0_start).days + 1
    w0_floor = config.MIN_ORDERS_WK * max(1, n_days) / 7.0
    base_floor = config.MIN_ORDERS_WK * l3w_days / 7.0
    if vol_w0 < w0_floor or vol_l3w < base_floor:
        return None
    # Baseline must be a real 3-week LEVEL, not activity concentrated in one week. The pooled
    # floor above sums all 21 days, so a single big week (other two paused) clears it — then
    # "vs the prior 3 weeks" is really "vs one week, 3 weeks ago" and the swing is meaningless
    # (e.g. Paris Catacombs +69% off a 0/0/3686-clicks baseline). Require >=2 of the 3
    # constituent weeks to have a live DENOMINATOR (clicks / conversions) — a week with 0 of it
    # contributes nothing to the pooled ratio, so it is not a real baseline week. (Orders alone
    # are not enough: attribution can post a stray order to a date with no clicks/spend.)
    funded_weeks = sum(
        1 for k in (1, 2, 3)
        if _agg(w0_start - dt.timedelta(days=7 * k),
                w0_start - dt.timedelta(days=7 * k) + dt.timedelta(days=6))[1] > 0)
    if funded_weeks < 2:
        return None
    if den_w0 == 0 or den_l3w == 0:
        return None

    ratio_w0 = val_w0 / den_w0
    ratio_l3w = val_l3w / den_l3w
    if ratio_l3w == 0:
        return None

    dev = ratio_w0 / ratio_l3w - 1
    if abs(dev) < config.FLUCTUATION_THRESHOLD:
        return None

    return {
        "value_now": round(ratio_w0, 4),
        "baseline": round(ratio_l3w, 4),
        "dev": round(dev, 4),
        "direction": "up" if dev > 0 else "down",
        "magnitude_pct": round(dev * 100, 1),
    }


# --------------------------------------------------------------------------- #
# Bid-change innocence check
# --------------------------------------------------------------------------- #
def bid_changes(troas: pd.DataFrame, w0_start: dt.date) -> dict[str, dict]:
    """
    Detect campaign-level as-of tROAS changes per CE in the lookback window.
    Returns {ce_id: {"changed": True, "detail": "...", "campaigns": n}}.
    """
    out: dict[str, dict] = {}
    if troas is None or troas.empty:
        return out
    t = troas.copy()
    t["troas"] = pd.to_numeric(t["troas"], errors="coerce")
    lo = w0_start - dt.timedelta(days=config.TROAS_LOOKBACK_DAYS)
    for ce_id, g in t.groupby("combined_entity_id"):
        details = []
        n_campaigns = 0
        for _, cg in g.groupby("campaign_id"):
            cg = cg.dropna(subset=["troas"]).sort_values("report_date")
            cg = cg[(cg["report_date"] >= lo)]
            if cg["troas"].nunique() <= 1:
                continue
            vals = cg["troas"].tolist()
            first, last = vals[0], vals[-1]
            if first == last:
                continue
            # Date of the first change.
            chg_date = None
            prev = vals[0]
            for _, row in cg.iterrows():
                if row["troas"] != prev:
                    chg_date = row["report_date"]
                    break
                prev = row["troas"]
            n_campaigns += 1
            details.append(f"{first:.0f}->{last:.0f}"
                           + (f" {chg_date}" if chg_date is not None else ""))
        if n_campaigns:
            out[str(ce_id)] = {
                "changed": True,
                "campaigns": n_campaigns,
                "detail": "tROAS " + "; ".join(sorted(set(details))[:4]),
            }
    return out


# --------------------------------------------------------------------------- #
# B2 column helpers (spec §5 B2 — swing driver + daily spark)
# --------------------------------------------------------------------------- #
_SHAP_LABELS = {"traffic": "Traffic", "cvr": "CVR", "aov": "AOV", "cr": "Completion", "tr": "Take rate"}


def _swing_driver(shap: dict | None) -> dict | None:
    """Top-1 driver of the swing from the per-CE WoW Shapley (mechanical, no LLM
    — the Blue Grotto template). Returns {factor, label, value, share_pct}."""
    if not shap:
        return None
    factors = {k: shap[k] for k in ("traffic", "cvr", "aov", "cr", "tr") if shap.get(k) is not None}
    if not factors:
        return None
    total_abs = sum(abs(v) for v in factors.values()) or 1.0
    top = max(factors, key=lambda k: abs(factors[k]))
    return {
        "factor": top,
        "label": _SHAP_LABELS.get(top, top),
        "value": round(float(factors[top]), 2),
        "share_pct": round(100.0 * abs(factors[top]) / total_abs, 0),
    }


def _indexed(df: pd.DataFrame | None, ce_id: str, cols: tuple) -> pd.DataFrame | None:
    """One CE's daily frame, indexed by report_date with `cols` coerced numeric."""
    if df is None:
        return None
    o = df[df["combined_entity_id"].astype(str) == str(ce_id)].copy()
    if o.empty:
        return None
    o = o.set_index("report_date").sort_index()
    for c in cols:
        if c in o:
            o[c] = pd.to_numeric(o[c], errors="coerce").fillna(0.0)
    return o


_FUNNEL_COLS = ("orders", "booked", "attr_value", "attr_completed", "revenue", "clicks")
_ADS_COLS = ("cm1", "conversions", "clicks", "spend")


def _sum_span(o: pd.DataFrame | None, col: str, lo: dt.date, hi: dt.date) -> float:
    if o is None or col not in o:
        return 0.0
    return float(o[col][[(lo <= x <= hi) for x in o.index]].sum())


def _pooled_drivers(o: pd.DataFrame | None, lo: dt.date, hi: dt.date) -> dict:
    """Paid GOOGLE-SEARCH RPC decomposition over [lo, hi], POOLED (Σ/Σ) so it reconciles
    to paid RPC exactly:  RPC = CVR × AOV × CR × TR
      CVR = orders/clicks · AOV = booked/orders · CR = attr_completed/attr_value
      TR  = rev/(booked·CR)          (the CR base cancels, so the product = rev/clicks)
    CR uses the attributed_value PAIR (same base) so it stays ≤100%."""
    clk = _sum_span(o, "clicks", lo, hi)
    orders = _sum_span(o, "orders", lo, hi)
    booked = _sum_span(o, "booked", lo, hi)
    av = _sum_span(o, "attr_value", lo, hi)
    avc = _sum_span(o, "attr_completed", lo, hi)
    rev = _sum_span(o, "revenue", lo, hi)
    cr = (avc / av) if av else None
    return {"cvr": (orders / clk) if clk else None,
            "aov": (booked / orders) if orders else None,
            "cr":  cr,
            "tr":  (rev / (booked * cr)) if (booked and cr) else None,
            "rpc": (rev / clk) if clk else None}


def _driver_windows(funnel_df: pd.DataFrame, ce_id: str,
                    w0_start: dt.date, w0_end: dt.date) -> dict | None:
    """Driver moves on BOTH comparison bases, so each row can be displayed and gated on the
    window it actually qualified against (CM1/conv + RPC fire on L3W; CVR and the collective
    -driver path fire WoW). Mixing them — gating a WoW row on L3W deltas — let two different
    windows decide one row.

      {'l3w': {driver: {v, pct}},   W0 vs the prior 21 days
       'wow': {driver: {v, pct}}}   W0 vs the same-length preceding week
    """
    o = _indexed(funnel_df, ce_id, _FUNNEL_COLS)
    if o is None:
        return None
    now = _pooled_drivers(o, w0_start, w0_end)
    n_days = (w0_end - w0_start).days + 1

    def _pack(prev):
        out = {}
        for k in ("cvr", "aov", "cr", "tr"):
            n, p = now.get(k), prev.get(k)
            out[k] = {"v": None if n is None else round(n, 4),
                      "pct": (round((n / p - 1) * 100) if (n is not None and p) else None)}
        return out

    l3w = _pack(_pooled_drivers(o, w0_start - dt.timedelta(days=config.FLUCTUATION_L3W_DAYS),
                                w0_start - dt.timedelta(days=1)))
    wow = _pack(_pooled_drivers(o, w0_start - dt.timedelta(days=7),
                                w0_start - dt.timedelta(days=7) + dt.timedelta(days=n_days - 1)))
    return {"l3w": l3w, "wow": wow}


def _week_blocks(ads_df, funnel_df, ce_id: str, w0_start: dt.date, w0_end: dt.date,
                 n: int = 4) -> list[dict]:
    """W0..W-3 display blocks for the report table.

    Every block spans [w0_start − 7k, w0_end − 7k] — SAME LENGTH and WEEKDAY-ALIGNED, and
    anchored to the window the swing was measured on. That matters: W0 is often a partial
    (matured) window, so comparing it against full calendar weeks would read a missing day
    as a decline, and reading the blocks off the report-week series would anchor them one
    week away from the qualifier.

    Ads side (Google Search): spend · ROI · clicks · CM1/conv · CPC.
    Funnel side: the RPC decomposition CVR × AOV × Completion × Take-rate.
    """
    a = _indexed(ads_df, ce_id, _ADS_COLS)
    f = _indexed(funnel_df, ce_id, _FUNNEL_COLS)
    n_days = (w0_end - w0_start).days + 1
    out = []
    for k in range(n):
        lo = w0_start - dt.timedelta(days=7 * k)
        hi = w0_end - dt.timedelta(days=7 * k)
        blk = {"label": f"w{k}", "week": lo.isoformat(), "span_days": n_days}
        sp = _sum_span(a, "spend", lo, hi)
        cm1 = _sum_span(a, "cm1", lo, hi)
        conv = _sum_span(a, "conversions", lo, hi)
        clk = _sum_span(a, "clicks", lo, hi)
        blk["spend"] = round(sp) if sp else (0 if a is not None else None)
        # ROI follows the same validity gates as _weekly_metrics: only computed above the
        # weekly spend floor, and nulled outside 0–1000%. Without these a $3-spend week
        # renders an absurd ROI *and* mis-drives the bucket's ROI gate, which reads this value.
        roi = (100.0 * cm1 / sp) if (sp and sp >= config.WEEKLY_SPEND_FLOOR) else None
        if roi is not None and not (config.ROI_MIN_PCT <= roi <= config.ROI_MAX_PCT):
            roi = None
        blk["roi"] = round(roi) if roi is not None else None
        blk["clicks"] = int(clk) if clk else None
        blk["cm1conv"] = round(cm1 / conv, 2) if conv else None
        blk["cpc"] = round(sp / clk, 2) if clk else None
        d = _pooled_drivers(f, lo, hi)
        blk["cvr"] = round(d["cvr"] * 100, 2) if d["cvr"] is not None else None
        blk["aov"] = round(d["aov"], 2) if d["aov"] is not None else None
        blk["cr"] = round(d["cr"] * 100, 1) if d["cr"] is not None else None
        blk["tr"] = round(d["tr"] * 100, 1) if d["tr"] is not None else None
        out.append(blk)
    return out


def _daily_spark(df: pd.DataFrame, ce_id: str, num: str, den: str, days: int = 35) -> list:
    """Last `days` of a daily ratio (e.g. CM1/conv) for the B2 sparkline. None on
    zero-denominator days (null = gap, never zero — monthly-v3 convention)."""
    sub = df[df["combined_entity_id"].astype(str) == ce_id].sort_values("report_date").tail(days)

    def _f(v):
        """NaN/None-safe float: a SUM() over an all-NULL day yields NaN, which is
        truthy — `float(nan) or 0` leaks the NaN into the JSON and breaks JSON.parse."""
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if np.isnan(v) else v

    out = []
    for _, r in sub.iterrows():
        d = _f(r.get(den))
        out.append(round(_f(r.get(num)) / d, 4) if d else None)
    return out


# Orchestrator: build bucket1_fluctuations rows
# --------------------------------------------------------------------------- #
def build_bucket1(
    *,
    ce_daily_ads: pd.DataFrame,
    ce_daily_business: pd.DataFrame,
    ce_daily_funnel_google: pd.DataFrame | None = None,
    ce_weekly: pd.DataFrame,
    ce_weekly_paid: pd.DataFrame,
    names: dict[str, str],
    paid_contrib: dict[str, float],
    troas: pd.DataFrame,
    w0_start: dt.date,
    wm1_start: dt.date,
    w0_end: dt.date | None = None,
    availability_fetcher=None,
    shapley_by_ce: dict | None = None,
) -> tuple[list[dict], dict]:
    """
    Returns (bucket1_rows, diagnostics).

    CM1/conv and RPC use the simplified L3W-vs-W0 comparison (pooled ratio over
    the report week vs the prior 21 days, flagged at >=35%). CVR drops and
    wow_driver_alerts remain WoW-based.
    """
    if w0_end is None:
        w0_end = w0_start + dt.timedelta(days=6)
    ce_ids = sorted(set(ce_daily_ads["combined_entity_id"].dropna().astype(str)))

    cm1_alerts: dict[str, dict] = {}
    rpc_alerts: dict[str, dict] = {}

    # "Sustained" is a LABEL, not a filter (2026-08-10). Filtering on it was a mistake: it
    # requires the CE to have ALREADY moved 35% last week, which is the definition of NOT
    # early — it deleted brand-new declines (e.g. Oceanario Lisboa −38% at 49% ROI), the exact
    # thing this table exists to catch before Losing Money does. So we always keep the row and
    # tag whether the same-direction move ALSO cleared the threshold a week earlier:
    #   sustained=True  → 2nd week running, a confirmed trend (strongest rows)
    #   sustained=False → new this week (could be a one-week wobble; read the W0..W-3 columns)
    _pw0, _pwe = w0_start - dt.timedelta(days=7), w0_end - dt.timedelta(days=7)

    def _sustained(df, ce_id, num, den, vol, direction):
        prev = _weekly_ratio_alert(df, ce_id, num, den, vol, _pw0, _pwe)
        return prev is not None and prev["direction"] == direction

    for ce_id in ce_ids:
        res = _weekly_ratio_alert(ce_daily_ads, ce_id, "cm1", "conversions", "conversions", w0_start, w0_end)
        if res is not None:
            res["sustained"] = _sustained(ce_daily_ads, ce_id, "cm1", "conversions", "conversions", res["direction"])
            cm1_alerts[ce_id] = res

    rpc_src = ce_daily_funnel_google if ce_daily_funnel_google is not None else ce_daily_business
    rpc_ids = sorted(set(rpc_src["combined_entity_id"].dropna().astype(str)))
    for ce_id in rpc_ids:
        res = _weekly_ratio_alert(rpc_src, ce_id, "revenue", "clicks", "orders", w0_start, w0_end)
        if res is not None:
            res["sustained"] = _sustained(rpc_src, ce_id, "revenue", "clicks", "orders", res["direction"])
            rpc_alerts[ce_id] = res

    # NOTE (2026-08-08): the CVR-WoW and collective-driver-WoW paths were REMOVED. Measured on
    # 3 markets they contributed 28% of displayed rows on a WoW basis the bucket doesn't
    # advertise, and none of them cleared 35% on ANY L3W measure — one (SEA LIFE London) was
    # CVR −3% / RPC +6% vs the 3-week baseline, i.e. flat-to-up, flagged only against a single
    # noisy prior week. CVR is also already a factor of RPC (RPC = CVR·AOV·CR·TR) and stays
    # visible as a column, so a real CVR-driven revenue drop still surfaces via the RPC path.
    bid = bid_changes(troas, w0_start)

    # Weekly W0 spend/revenue lookups.
    paid_w0 = ce_weekly_paid[ce_weekly_paid["week"] == w0_start].set_index("combined_entity_id")
    biz_w0 = ce_weekly[ce_weekly["week"] == w0_start].set_index("combined_entity_id")

    # Availability enrichment for the union of flagged CEs.
    flagged = set(cm1_alerts) | set(rpc_alerts)
    avail_map: dict[str, dict] = {}
    if availability_fetcher and flagged:
        av = availability_fetcher(sorted(flagged))
        if av is not None and not av.empty:
            for _, r in av.iterrows():
                avail_map[str(r["combined_entity_id"])] = {
                    "soldout_w0": None if pd.isna(r["soldout_w0"]) else round(float(r["soldout_w0"]), 3),
                    "soldout_baseline": None if pd.isna(r["soldout_baseline"]) else round(float(r["soldout_baseline"]), 3),
                }

    def _spend(ce_id):
        return round(float(paid_w0.loc[ce_id]["spend"]), 0) if ce_id in paid_w0.index else None

    def _rev(ce_id):
        return round(float(biz_w0.loc[ce_id]["revenue"]), 0) if ce_id in biz_w0.index else None

    def _reco(direction: str, ce_id: str) -> str:
        pc = paid_contrib.get(ce_id)
        if pc is not None and pc < config.PAID_CONTRIB_LOW_PCT:
            return f"review — low paid ({pc:.0f}% paid-contribution)"
        base = ("+" if direction == "up" else "-") + f"{config.SEASONALITY_ADJ_PCT*100:.0f}% / 7d seasonality adjustment"
        if ce_id in bid:
            return f"{base} — but input-induced ({bid[ce_id]['detail']}); verify before adjusting"
        return base

    shapley_by_ce = shapley_by_ce or {}

    def _cause_tag(ce_id, direction):
        """Innocence-check routing (spec §5 B2): each hit re-routes away from the
        UNEXPLAINED tag — the only rows where 'investigate' means nobody knows.
        Order: bid change -> supply break -> (TR/price steps deferred) -> unexplained."""
        if ce_id in bid:
            return "input-induced"
        av = avail_map.get(ce_id)
        if av and av.get("soldout_w0") is not None:
            base = av.get("soldout_baseline")
            # W0 sold-out materially above its baseline => supply-linked, route to Ops
            if av["soldout_w0"] >= 0.20 and (base is None or av["soldout_w0"] > (base or 0) + 0.10):
                return "supply-linked"
        return "unexplained" if direction == "down" else "up-swing"

    rows: list[dict] = []

    def _emit(ce_id, signal, res, window, evidence_extra=None):
        ev = {
            "value_now": res.get("value_now"),
            "baseline": res.get("baseline"),
            "wow_pct": res.get("wow_pct"),
        }
        if evidence_extra:
            ev.update(evidence_extra)
        if ce_id in bid:
            ev["bid_change"] = bid[ce_id]["detail"]
        if ce_id in avail_map:
            ev["availability"] = avail_map[ce_id]
        # daily CM1/conv spark + 28d baseline band (only the daily bucket gets a daily spark)
        if signal == "cm1_per_conv":
            ev["spark_daily"] = _daily_spark(ce_daily_ads, ce_id, "cm1", "conversions")
            ev["spark_baseline"] = res.get("baseline")
        rows.append({
            "ce_id": ce_id,
            "ce_name": names.get(ce_id, ce_id),
            "signal": signal,
            "direction": res["direction"],
            "magnitude_pct": res["magnitude_pct"],
            "window": window,
            "sustained": res.get("sustained", False),   # True = same-direction move held last week too
            "cause_tag": _cause_tag(ce_id, res["direction"]),
            "swing_driver": _swing_driver(shapley_by_ce.get(ce_id)),
            # paid Google-Search RPC-driver breakdown (CVR·AOV·CR·TR), WoW + 3D, from the funnel
            "drivers": (_driver_windows(ce_daily_funnel_google, ce_id, w0_start, w0_end)
                        if ce_daily_funnel_google is not None else None),
            # W0..W-3 display blocks on weekday-aligned, equal-length spans
            "weeks": _week_blocks(ce_daily_ads, ce_daily_funnel_google, ce_id, w0_start, w0_end),
            "evidence": ev,
            "paid_contribution_pct": paid_contrib.get(ce_id),
            "spend_wk": _spend(ce_id),
            "revenue_wk": _rev(ce_id),
            "recommendation": _reco(res["direction"], ce_id),
        })

    for ce_id, res in cm1_alerts.items():
        _emit(ce_id, "cm1_per_conv", res, "l3w")
    for ce_id, res in rpc_alerts.items():
        if ce_id in cm1_alerts:
            continue
        _emit(ce_id, "rpc", res, "l3w")
    # Sort: down-swings first (risk), then by |magnitude| desc.
    rows.sort(key=lambda r: (r["direction"] != "down", -abs(r["magnitude_pct"] or 0)))

    diagnostics = {
        "cm1_conv_alert_ces": sorted(names.get(c, c) for c in cm1_alerts),
        "cm1_conv_alert_count": len(cm1_alerts),
        "cm1_conv_directions": {names.get(c, c): cm1_alerts[c]["direction"] for c in cm1_alerts},
        "rpc_alert_count": len(rpc_alerts),
    }
    return rows, diagnostics
