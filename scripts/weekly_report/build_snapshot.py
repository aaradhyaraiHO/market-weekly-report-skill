"""
Weekly Market Report V1 — snapshot producer (CLI, per-market).

Emits the `meta`, `market_summary`, `ces`, `followup`, and `bucket1_fluctuations`
sections of the contract, plus a Phase-2-forward-compat `transitions` state model.
Optionally merges seasonality / levers / no_bid fragments from sibling worktree
modules if they are importable, else emits empty arrays for those sections.

Output: .cache/weekly_report/snapshot_{market_slug}_{week}.json

Usage:
    python build_snapshot.py --market north_america --week 2026-06-29
    python build_snapshot.py --market north_america            # latest matured week
    python build_snapshot.py --all --validate
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

import alerts
import bucket_b1
import bucket_b3
import bucket_b4
import config
import fetch
import flows
import shapley

REPO_ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = REPO_ROOT / ".cache" / "weekly_report"


# --------------------------------------------------------------------------- #
# Small numeric helpers
# --------------------------------------------------------------------------- #
def _num(x):
    """JSON-safe number: None for NaN/inf, plain float/int otherwise."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 4)


def _pct(num, den, gate=None):
    """100 * num/den, or None if den falsy. gate=(lo,hi) nulls out-of-range."""
    num, den = float(num or 0), float(den or 0)
    if den == 0:
        return None
    v = 100.0 * num / den
    if gate and not (gate[0] <= v <= gate[1]):
        return None
    return round(v, 2)


def _ce_levels(row: dict) -> dict:
    """Funnel levels for the per-CE WoW Shapley (gbv_completed = gbv * cr%)."""
    gbv, cr = row.get("gbv"), row.get("cr_pct")
    gbv_c = (gbv * cr / 100.0) if (gbv is not None and cr is not None) else None
    return {"clicks": row.get("clicks"), "orders": row.get("orders"),
            "gbv": gbv, "gbv_completed": gbv_c, "revenue": row.get("revenue")}


def _to_date(s) -> dt.date:
    if isinstance(s, dt.date):
        return s
    return dt.date.fromisoformat(str(s)[:10])


# --------------------------------------------------------------------------- #
# Weekly metric row assembly (canon definitions; revenue = predicted)
# --------------------------------------------------------------------------- #
def _weekly_metrics(biz: pd.Series | None, paid: pd.Series | None, yoy_rev=None) -> dict:
    b = biz if biz is not None else {}
    p = paid if paid is not None else {}
    revenue = float(b.get("revenue") or 0) if biz is not None else None
    orders = float(b.get("orders") or 0) if biz is not None else None
    clicks = float(b.get("clicks") or 0) if biz is not None else None
    ad_conv = float(b.get("ad_conversions") or 0) if biz is not None else None
    gbv = float(b.get("gbv") or 0) if biz is not None else None
    gbv_comp = float(b.get("gbv_completed") or 0) if biz is not None else None
    organic = float(b.get("organic_gbv") or 0) if biz is not None else None

    def _fb(key, default=0.0):
        """NaN/None-safe float extraction from the business Series."""
        v = b.get(key)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return default
        return default if math.isnan(v) else v

    # CM1(business) + Gross Marketing Cost components (for canonical ROI(1)).
    co_mktg = _fb("co_marketing_commission") if biz is not None else 0.0
    insider = _fb("insider_commission") if biz is not None else 0.0
    direct_costs = _fb("direct_costs") if biz is not None else 0.0
    ad_spend_total = _fb("ad_spend_total") if biz is not None else 0.0
    coupon_discount = _fb("coupon_discount") if biz is not None else 0.0
    wallet_credits = _fb("wallet_credits") if biz is not None else 0.0
    affiliate = _fb("affiliate_commission") if biz is not None else 0.0
    creator_collab = _fb("creator_collab_costs") if biz is not None else 0.0
    creator_collab_coupon = _fb("creator_collab_coupon_costs") if biz is not None else 0.0

    def _f(src, key, default=0.0):
        """NaN/None-safe float extraction from a pandas Series or dict."""
        v = src.get(key)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return default
        return default if math.isnan(v) else v

    spend = _f(p, "spend") if paid is not None else None
    coupon_wallet = _f(p, "coupon_wallet") if paid is not None else 0.0
    cm1 = _f(p, "cm1") if paid is not None else None
    conversions = _f(p, "conversions") if paid is not None else None
    paid_impressions = _f(p, "paid_impressions") if paid is not None else None
    paid_clicks = _f(p, "paid_clicks") if paid is not None else None
    conv_value_gbv = _f(p, "conv_value_gbv") if paid is not None else None
    offline_rev = _f(p, "offline_revenue") if paid is not None else None   # paid-attributed net rev (for Paid RPC)
    # Search Impression Share (Google search only): impr / eligible searches.
    sis_impr = _f(p, "sis_impr") if paid is not None else None
    sis_elig = _f(p, "sis_elig") if paid is not None else None

    # Paid RoI (ads_campaign_stats, Google Search + Bing): CM1 / (spend + coupon_wallet).
    roi = None
    if spend is not None and spend >= config.WEEKLY_SPEND_FLOOR:
        roi = _pct(cm1, spend + coupon_wallet, gate=(config.ROI_MIN_PCT, config.ROI_MAX_PCT))

    # Canonical business ROI(1): CM1(business) / Gross Marketing Cost.
    cm1_business = None
    gross_mktg_cost = None
    roi1 = None
    if biz is not None:
        cm1_business = revenue + co_mktg + insider - direct_costs
        gross_mktg_cost = (
            ad_spend_total + coupon_discount + wallet_credits
            + affiliate + creator_collab + creator_collab_coupon
        )
        if gross_mktg_cost and gross_mktg_cost >= config.WEEKLY_SPEND_FLOOR:
            roi1 = _pct(cm1_business, gross_mktg_cost,
                        gate=(config.ROI_MIN_PCT, config.ROI_MAX_PCT))

    row = {
        "revenue": _num(revenue),
        "gbv": _num(gbv) if biz is not None else None,
        "orders": int(orders) if orders is not None else None,
        "clicks": int(clicks) if clicks is not None else None,
        # Raw additive numerators — carried so group SUBTOTALS can recompute the
        # ratio metrics (CVR/AOV/TR/Paid %/ROI) exactly as Σnum/Σden rather than
        # averaging per-CE ratios. Not shown per-row; consumed by the render's
        # subtotalHtml. See _weekly_metrics ratio defs below.
        "ad_conversions": _num(ad_conv) if biz is not None else None,
        "gbv_completed": _num(gbv_comp) if biz is not None else None,
        "organic_gbv": _num(organic) if biz is not None else None,
        "coupon_wallet": _num(coupon_wallet) if paid is not None else None,
        # canon: paid ad CVR = ad_conversions / ad_clicks
        "cvr_pct": _pct(ad_conv, clicks, gate=(0.0, config.CVR_MAX_PCT)) if biz is not None else None,
        # canon: AOV = GBV / orders
        "aov": _num(gbv / orders) if (orders and biz is not None) else None,
        # canon: take rate = revenue / GBV completed
        "tr_pct": _pct(revenue, gbv_comp) if biz is not None else None,
        # canon: completion rate = GBV completed / GBV booked
        "cr_pct": _pct(gbv_comp, gbv) if biz is not None else None,
        "cm2": _num(revenue - ad_spend_total) if biz is not None else None,
        "spend": _num(spend),
        "cm1": _num(cm1),
        "roi_pct": roi,                       # Paid RoI (campaign, coupon-inclusive)
        "cm1_business": _num(cm1_business),
        "gross_marketing_cost": _num(gross_mktg_cost),
        "roi1_pct": roi1,                     # canonical business ROI(1)
        "paid_impressions": int(paid_impressions) if _num(paid_impressions) is not None else None,
        "paid_clicks": int(paid_clicks) if _num(paid_clicks) is not None else None,
        "paid_ctr_pct": _pct(paid_clicks, paid_impressions) if paid is not None else None,
        # Search Impression Share — Google search only (impr / eligible searches).
        "paid_sis_pct": _pct(sis_impr, sis_elig, gate=(0.0, 100.0)) if paid is not None else None,
        "paid_conv_value": _num(conv_value_gbv),
        "paid_conversions": int(conversions) if _num(conversions) is not None else None,
        "paid_cvr_pct": _pct(conversions, paid_clicks, gate=(0.0, config.CVR_MAX_PCT)) if paid is not None else None,
        "cpc": _num(spend / paid_clicks) if (paid_clicks and paid is not None) else None,
        "rpc": _num(revenue / clicks) if (clicks and biz is not None) else None,
        # Paid RPC = paid-attributed net revenue ÷ paid clicks (not total revenue).
        "paid_revenue": _num(offline_rev),
        "paid_rpc": _num(offline_rev / paid_clicks) if (paid_clicks and offline_rev is not None and paid is not None) else None,
        "paid_cm2": _num(revenue - spend) if (spend is not None and revenue is not None) else None,
        "revenue_ly": _num(yoy_rev) if yoy_rev else None,
        "cm1_per_conv": _num(cm1 / conversions) if (conversions and paid is not None) else None,
        "paid_contribution_pct": (
            _num(max(0.0, min(100.0, 100.0 * (1 - organic / gbv_comp)))) if gbv_comp else None
        ),
        # SCHEMA ADDITION (documented): per-CE YoY needs the -364d anchor, which
        # is not derivable from the 12-week array. Null where no LY data.
        "yoy_pct": _num(100.0 * (revenue / yoy_rev - 1)) if (yoy_rev and revenue is not None) else None,
    }
    return row


# --------------------------------------------------------------------------- #
# Main per-market build
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# RE-SOURCE tier (A1) — attach per-CE composition breakdowns to the drawer
# --------------------------------------------------------------------------- #
_LEADTIME_ORDER = ["0-2D", "3-4D", "5-7D", "7D+"]
_TGIDS_TOP_N = 8
_COUNTRIES_TOP_N = 10   # render shows top 6; a few extra ride along for export


def _dp(cur, ly):
    """% delta (cur vs ly), None when ly missing/zero."""
    if cur is None or ly is None or ly == 0:
        return None
    return round(100.0 * (cur / ly - 1), 1)


def _dpp(cur_pct, ly_pct):
    """Percentage-point delta, None when either missing."""
    if cur_pct is None or ly_pct is None:
        return None
    return round(cur_pct - ly_pct, 1)


def _safe(v, default=0.0):
    try:
        f = float(v)
        return default if (f != f) else f  # NaN check
    except (TypeError, ValueError):
        return default


def _attach_resource_breakdowns(
    ces, tgids_df, tgid_funnel_df, tgid_lt_df, lead_df, ctry_df
) -> None:
    """
    Attach composition tables to each CE for the drawer. TGIDs are enriched
    with the full ce_health column set (15 columns + WoW/YoY deltas).
    """
    for df in (tgids_df, tgid_funnel_df, tgid_lt_df, lead_df, ctry_df):
        if not df.empty and "combined_entity_id" in df:
            df["combined_entity_id"] = df["combined_entity_id"].astype(str)
        if not df.empty and "tgid" in df:
            df["tgid"] = df["tgid"].astype(str)

    tg_by_ce = dict(tuple(tgids_df.groupby("combined_entity_id"))) if not tgids_df.empty else {}
    lt_by_ce = dict(tuple(lead_df.groupby("combined_entity_id"))) if not lead_df.empty else {}
    ct_by_ce = dict(tuple(ctry_df.groupby("combined_entity_id"))) if not ctry_df.empty else {}

    # TGID funnel + lead-time indexed by (ce_id, tgid)
    fn_idx = {}
    if not tgid_funnel_df.empty:
        for _, r in tgid_funnel_df.iterrows():
            fn_idx[(str(r["combined_entity_id"]), str(r["tgid"]))] = r
    lt_idx = {}
    if not tgid_lt_df.empty:
        for _, r in tgid_lt_df.iterrows():
            wm1 = r.get("pct_wm1")
            has_wm1 = wm1 is not None and not (isinstance(wm1, float) and math.isnan(wm1))
            lt_idx.setdefault((str(r["combined_entity_id"]), str(r["tgid"])), {})[r["band"]] = {
                "pct": _safe(r["pct"]),
                "wm1": _safe(wm1) if has_wm1 else None,
            }

    def _share(part, total):
        return _num(round(100.0 * part / total, 0)) if total else None

    for ce in ces:
        cid = ce["ce_id"]

        # TGIDs — enriched: 15 columns matching ce_health
        tgids = []
        g = tg_by_ce.get(cid)
        if g is not None:
            total_rev = float(g["rev"].sum())
            total_rev_wm1 = float(g["rev_wm1"].sum()) if "rev_wm1" in g else 0.0
            total_rev_ly = float(g["rev_ly"].sum()) if "rev_ly" in g else 0.0
            # total select users for %Traffic denominator
            total_sel = sum(_safe(fn_idx.get((cid, str(r["tgid"])), {}).get("select_users"))
                            for _, r in g.iterrows())

            for _, r in g.sort_values("rev", ascending=False).head(_TGIDS_TOP_N).iterrows():
                rev = _safe(r["rev"])
                orders = _safe(r["orders"])
                gbv = _safe(r["gbv"])
                gbv_c = _safe(r["completed_gbv"])
                rev_wm1 = _safe(r.get("rev_wm1"))
                orders_wm1 = _safe(r.get("orders_wm1"))
                gbv_wm1 = _safe(r.get("gbv_wm1"))
                gbv_c_wm1 = _safe(r.get("completed_gbv_wm1"))
                rev_ly = _safe(r.get("rev_ly"))

                if rev <= 0 and rev_ly <= 0:
                    continue

                tid = str(r["tgid"])
                fn = fn_idx.get((cid, tid))
                has_fn = fn is not None
                sel = _safe(fn.get("select_users")) if has_fn else 0
                s2c = _safe(fn.get("s2c")) * 100 if (has_fn and fn.get("s2c") is not None) else None
                c2o = _safe(fn.get("c2o")) * 100 if (has_fn and fn.get("c2o") is not None) else None
                s2c_wm1 = _safe(fn.get("s2c_wm1")) * 100 if (has_fn and fn.get("s2c_wm1") is not None) else None
                c2o_wm1 = _safe(fn.get("c2o_wm1")) * 100 if (has_fn and fn.get("c2o_wm1") is not None) else None

                # W0 + W-1 derived metrics (deltas are WoW: W0 vs W-1)
                aov = gbv / orders if orders else None
                aov_wm1 = gbv_wm1 / orders_wm1 if orders_wm1 else None
                cr = 100.0 * gbv_c / gbv if gbv else None
                cr_wm1 = 100.0 * gbv_c_wm1 / gbv_wm1 if gbv_wm1 else None
                tr = 100.0 * rev / gbv_c if gbv_c else None
                tr_wm1 = 100.0 * rev_wm1 / gbv_c_wm1 if gbv_c_wm1 else None
                # RPC = revenue per select-user via the driver product:
                # S2O × AOV × CR × TR  (S2O = S2C × C2O, user-based). Ties out to
                # the funnel + economics columns shown in the table.
                def _rpc(s2c_, c2o_, aov_, cr_, tr_):
                    if None in (s2c_, c2o_, aov_, cr_, tr_):
                        return None
                    return (s2c_ / 100.0) * (c2o_ / 100.0) * aov_ * (cr_ / 100.0) * (tr_ / 100.0)
                rpc = _rpc(s2c, c2o, aov, cr, tr)
                rpc_wm1 = _rpc(s2c_wm1, c2o_wm1, aov_wm1, cr_wm1, tr_wm1)

                lt = lt_idx.get((cid, tid), {})

                # Revenue-share shift: within-CE share for W0 / W-1 / LY → pp deltas.
                share_now = 100.0 * rev / total_rev if total_rev else None
                share_wm1 = 100.0 * rev_wm1 / total_rev_wm1 if total_rev_wm1 else None
                share_ly = 100.0 * rev_ly / total_rev_ly if total_rev_ly else None

                tgids.append({
                    "tgid": tid,
                    "experience": r["experience"] or tid,
                    "rev": _num(rev),
                    "rev_wm1": _num(rev_wm1),
                    "rev_wow": _dp(rev, rev_wm1),
                    "orders": int(orders) if orders else None,
                    "orders_wow": _dp(orders, orders_wm1),
                    "share_pct": _share(rev, total_rev),
                    "share_wow_pp": _dpp(share_now, share_wm1),
                    "share_yoy_pp": _dpp(share_now, share_ly),
                    "rpc": _num(rpc),
                    "rpc_wow": _dp(rpc, rpc_wm1),
                    "aov": _num(aov),
                    "aov_wow": _dp(aov, aov_wm1),
                    "cr_pct": _num(cr),
                    "cr_wow_pp": _dpp(cr, cr_wm1),
                    "tr_pct": _num(tr),
                    "tr_wow_pp": _dpp(tr, tr_wm1),
                    "sel_users": int(sel) if sel else None,
                    "traffic_pct": _num(100.0 * sel / total_sel) if (total_sel and sel) else None,
                    "s2c_pct": _num(s2c),
                    "s2c_wow_pp": _dpp(s2c, s2c_wm1),
                    "c2o_pct": _num(c2o),
                    "c2o_wow_pp": _dpp(c2o, c2o_wm1),
                    "lt_02d": (_num(100.0 * lt["0-2D"]["pct"]) if lt.get("0-2D") else None),
                    "lt_02d_wow": (_dpp(100.0 * lt["0-2D"]["pct"], 100.0 * lt["0-2D"]["wm1"])
                                   if (lt.get("0-2D") and lt["0-2D"]["wm1"] is not None) else None),
                    "lt_37d": (_num(100.0 * lt["3-7D"]["pct"]) if lt.get("3-7D") else None),
                    "lt_37d_wow": (_dpp(100.0 * lt["3-7D"]["pct"], 100.0 * lt["3-7D"]["wm1"])
                                   if (lt.get("3-7D") and lt["3-7D"]["wm1"] is not None) else None),
                    "lt_7p": (_num(100.0 * lt["7D+"]["pct"]) if lt.get("7D+") else None),
                    "lt_7p_wow": (_dpp(100.0 * lt["7D+"]["pct"], 100.0 * lt["7D+"]["wm1"])
                                  if (lt.get("7D+") and lt["7D+"]["wm1"] is not None) else None),
                })
        ce["tgids"] = tgids

        # Lead-time bands — fixed order, booking share within CE, gross AOV
        leadtime = []
        g = lt_by_ce.get(cid)
        if g is not None:
            g = g[g["band"].notna()]
            total_bk = float(g["bookings"].sum())
            band_map = {r["band"]: r for _, r in g.iterrows()}
            for band in _LEADTIME_ORDER:
                r = band_map.get(band)
                if r is None:
                    continue
                bk = float(r["bookings"] or 0)
                bk_wm1 = float(r.get("bookings_wm1") or 0)
                ov = float(r["order_value"] or 0)
                leadtime.append({
                    "band": band,
                    "bookings": _num(bk),
                    "bookings_wm1": _num(bk_wm1),
                    "share_pct": _share(bk, total_bk),
                    "rev": _num(r["rev"]),
                    "aov": _num(ov / bk) if bk else None,
                })
        ce["leadtime"] = leadtime

        # Countries — top by orders, order & revenue share within CE, gross AOV
        countries = []
        g = ct_by_ce.get(cid)
        if g is not None:
            total_ord = float(g["orders"].sum())
            total_rev = float(g["rev"].sum())
            for _, r in g.sort_values("orders", ascending=False).head(_COUNTRIES_TOP_N).iterrows():
                od = float(r["orders"] or 0)
                od_wm1 = float(r.get("orders_wm1") or 0)
                rev = float(r["rev"] or 0)
                rev_wm1 = float(r.get("rev_wm1") or 0)
                ov = float(r["order_value"] or 0)
                countries.append({
                    "country": r["country"],
                    "orders": _num(od),
                    "orders_wow": _dp(od, od_wm1),
                    "order_share_pct": _share(od, total_ord),
                    "rev": _num(rev),
                    "rev_wm1": _num(rev_wm1),
                    "rev_wow": _dp(rev, rev_wm1),
                    "rev_share_pct": _share(rev, total_rev),
                    "aov": _num(ov / od) if od else None,
                })
        ce["countries"] = countries


_CHANNELS_TOP_N = 8
_FUNNEL_STAGES = [
    # (mockup label, dataframe column, is_rate) — LP Users is a count (WoW/YoY as
    # % change); the three conversion stages are rates (WoW/YoY as pp deltas).
    ("LP Users", "lp_users", False),
    ("LP2S", "lp2s", True),
    ("S2C", "s2c", True),
    ("C2O", "c2o", True),
]


def _attach_channels_funnel(ces, chan_df, funnel_df) -> None:
    """
    Attach the A2 "hard re-source" drawer sections, matching the mockup contract:
      ce['channels'] -> [{channel, rev, wow_pct, yoy_pct, share_pct}]   top-N by W0 rev
      ce['funnel']   -> {"LP Users"|"LP2S"|"S2C"|"C2O": {current, wow, yoy}}
    Both carry W0 + WoW + YoY off the three one-week windows the fetches emit.
    Revenue basis is actuals (see fetch.py). Each defaults to []/{} when empty.
    """
    for df in (chan_df, funnel_df):
        if not df.empty and "combined_entity_id" in df:
            df["combined_entity_id"] = df["combined_entity_id"].astype(str)

    ch_by_ce = dict(tuple(chan_df.groupby("combined_entity_id"))) if not chan_df.empty else {}
    fn_by_ce = dict(tuple(funnel_df.groupby("combined_entity_id"))) if not funnel_df.empty else {}

    def _chg(cur, base):
        """% change cur vs base, None when base missing/zero."""
        cur, base = float(cur or 0), float(base or 0)
        return round(100.0 * (cur / base - 1), 1) if base else None

    for ce in ces:
        cid = ce["ce_id"]

        # ---- Channel mix ----
        channels = []
        g = ch_by_ce.get(cid)
        if g is not None:
            pivot = {}   # channel -> {period: rev}
            for _, r in g.iterrows():
                pivot.setdefault(r["channel"], {})[r["period"]] = float(r["rev"] or 0)
            total_w0 = sum(p.get("w0", 0.0) for p in pivot.values())
            ranked = sorted(pivot.items(), key=lambda kv: kv[1].get("w0", 0.0), reverse=True)
            for channel, per in ranked[:_CHANNELS_TOP_N]:
                w0 = per.get("w0", 0.0)
                if w0 <= 0:
                    continue
                channels.append({
                    "channel": channel,
                    "rev": _num(w0),
                    "rev_wm1": _num(per.get("wm1", 0.0)),
                    "wow_pct": _chg(w0, per.get("wm1")),
                    "yoy_pct": _chg(w0, per.get("ly")),
                    "share_pct": _num(round(100.0 * w0 / total_w0, 1)) if total_w0 else None,
                })
        ce["channels"] = channels

        # ---- Funnel (LP → order) ----
        funnel = {}
        g = fn_by_ce.get(cid)
        if g is not None:
            per = {r["period"]: r for _, r in g.iterrows()}
            w0, wm1, ly = per.get("w0"), per.get("wm1"), per.get("ly")
            if w0 is not None:
                for label, col, is_rate in _FUNNEL_STAGES:
                    cur = _num(w0[col])
                    prev = _num(wm1[col]) if (wm1 is not None and wm1[col] is not None) else None
                    if is_rate:
                        wow = _num(round(float(w0[col]) - float(wm1[col]), 1)) if wm1 is not None and wm1[col] is not None else None
                        yoy = _num(round(float(w0[col]) - float(ly[col]), 1)) if ly is not None and ly[col] is not None else None
                    else:
                        wow = _chg(w0[col], wm1[col] if wm1 is not None else None)
                        yoy = _chg(w0[col], ly[col] if ly is not None else None)
                    funnel[label] = {"current": cur, "wm1": prev, "wow": wow, "yoy": yoy}

                # Overall CVR (LP → order) = LP2S × S2C × C2O (each a %).
                def _cvr(row):
                    if row is None:
                        return None
                    try:
                        v = float(row["lp2s"]) * float(row["s2c"]) * float(row["c2o"]) / 10000.0
                        return v if v == v else None  # NaN guard
                    except (TypeError, ValueError, KeyError):
                        return None
                cvr0, cvrm1, cvrly = _cvr(w0), _cvr(wm1), _cvr(ly)
                if cvr0 is not None:
                    funnel["CVR"] = {
                        "current": _num(cvr0),
                        "wm1": _num(cvrm1),
                        "wow": _num(round(cvr0 - cvrm1, 2)) if cvrm1 is not None else None,
                        "yoy": _num(round(cvr0 - cvrly, 2)) if cvrly is not None else None,
                    }
        ce["funnel"] = funnel


# --------------------------------------------------------------------------- #
# Cross-bucket cascade (spec §5) — one home per CE (B1>B2>B3>B4), dedup,
# (also in …) chips, hard cap of 10 narrative rows by $ at stake.
# --------------------------------------------------------------------------- #
_CASCADE = ["B1", "B2", "B3", "B4"]
_NARRATIVE_CAP = 10


def _stake(label: str, row: dict) -> float:
    """Rough weekly $ at stake, comparable across buckets, for ranking/cap."""
    if label == "B1":
        return abs(row.get("cm2_bleed_wk") or 0.0)
    if label == "B2":
        return abs(row.get("spend_wk") or 0.0)            # CM1-delta proxy
    if label == "B3":
        return abs(row.get("projected_monthly_loss") or 0.0) / 4.345   # → weekly
    if label == "B4":
        return abs(row.get("est_incremental_wk") or 0.0)
    return 0.0


def _apply_cascade(bucket_rows: dict) -> dict:
    """
    Mutates each row in-place with: home (bucket label), is_home (bool),
    also_in (list of other buckets for the home row), stake_usd, in_store (bool
    — beyond the 10-row narrative cap). B1 home rows are never capped. Returns a
    summary {home_counts, rendered, in_store}.
      bucket_rows = {"B1":[...], "B2":[...], "B3":[...], "B4":[...]}
    """
    home, also = {}, {}
    for label in _CASCADE:
        for r in bucket_rows.get(label, []):
            cid = r["ce_id"]
            if cid not in home:
                home[cid] = label
            elif label not in also.setdefault(cid, []):
                also[cid].append(label)

    # tag home / also_in / stake
    home_rows = []
    for label in _CASCADE:
        for r in bucket_rows.get(label, []):
            cid = r["ce_id"]
            r["is_home"] = (home[cid] == label)
            r["also_in"] = also.get(cid, []) if r["is_home"] else []
            r["stake_usd"] = round(_stake(label, r), 0)
            r["in_store"] = False
            if r["is_home"]:
                home_rows.append((label, r))

    # B1 EXITs are WINS, not problems — render them in a separate "recovered"
    # line, never competing for the problem-narrative cap.
    wins, problems = [], []
    for (l, r) in home_rows:
        r["is_win"] = (l == "B1" and r.get("movement") == "EXIT")
        (wins if r["is_win"] else problems).append((l, r))

    # hard cap on the PROBLEM narrative: B1 problems never dropped; B2/B3/B4 fill
    # the remainder by $ at stake, up to 10 total. Wins are always shown.
    b1p = [(l, r) for (l, r) in problems if l == "B1"]
    rest = sorted([(l, r) for (l, r) in problems if l != "B1"], key=lambda x: -x[1]["stake_usd"])
    keep = set(id(r) for (_, r) in b1p) | set(id(r) for (_, r) in wins)
    for _, r in rest[:max(0, _NARRATIVE_CAP - len(b1p))]:
        keep.add(id(r))
    in_store = 0
    for _, r in home_rows:
        if id(r) not in keep:
            r["in_store"] = True
            in_store += 1
    return {
        "home_counts": {l: sum(1 for (ll, _) in home_rows if ll == l) for l in _CASCADE},
        "wins": len(wins),
        "rendered_problems": len(keep) - len(wins),
        "in_store": in_store,
    }


# --------------------------------------------------------------------------- #
# P3 — per-bucket sparkline enrichment
# --------------------------------------------------------------------------- #
def _spark(ce, field, n):
    """Extract last *n* values of *field* from ce['weekly']."""
    wk = ce.get("weekly") or []
    return [w.get(field) for w in wk[-n:]]


def _enrich_b1_sparklines(rows, ce_by_id):
    """B1: 8-week RPC sparkline (cliff vs gradual visual)."""
    for r in rows:
        ce = ce_by_id.get(r["ce_id"])
        if not ce:
            continue
        r["spark_rpc"] = _spark(ce, "rpc", 8)


def _enrich_b3_sparklines(rows, ce_by_id, ly_rev, w0_start):
    """B3: 10-week revenue TY + 14-point LY (10 aligned + 4 forward weeks)."""
    forward_weeks = [w0_start + dt.timedelta(days=7 * (i + 1)) for i in range(4)]
    for r in rows:
        ce = ce_by_id.get(r["ce_id"])
        if not ce:
            continue
        r["spark_rev"] = _spark(ce, "revenue", 10)
        wly = ce.get("weekly_ly") or []
        ly_aligned = [w.get("revenue") for w in wly[-10:]]
        ly_fwd = [_num(ly_rev.get((r["ce_id"], fw))) for fw in forward_weeks]
        r["spark_rev_ly"] = ly_aligned + ly_fwd


def _enrich_b4_sparklines(rows, ce_by_id):
    """B4: 10-week revenue sparkline (growth momentum)."""
    for r in rows:
        ce = ce_by_id.get(r["ce_id"])
        if not ce:
            continue
        r["spark_rev"] = _spark(ce, "revenue", 10)


def build_market(market_slug: str, w0_start: dt.date, *, with_availability=True) -> dict:
    market = config.MARKETS[market_slug]
    weeks = config.week_starts(w0_start, config.WEEKS_BACK)
    w0_end = w0_start + dt.timedelta(days=6)
    wm1_start = w0_start - dt.timedelta(days=7)
    start = weeks[0]
    print(f"\n=== {market} | W0 {w0_start} ({weeks[0]}..{w0_end}) ===")

    # ---- fetch ----
    biz = fetch.ce_weekly_business(market, start, w0_end)
    paid = fetch.ce_weekly_ads(market, start, w0_end)
    meta = fetch.ce_metadata(market, start, w0_end)

    # LY (weekday-aligned -364d) weekly revenue for YoY. Extend +28d forward so the
    # header flows engine has LY[t+1] and B3 sparklines have +4 forward LY weeks.
    ly_start = start - dt.timedelta(days=config.YOY_LAG_DAYS)
    ly_end = w0_end - dt.timedelta(days=config.YOY_LAG_DAYS) + dt.timedelta(days=28)
    ly = fetch.ce_weekly_business(market, ly_start, ly_end)
    ly["aligned_week"] = pd.to_datetime(ly["week"]).dt.date.map(
        lambda d: d + dt.timedelta(days=config.YOY_LAG_DAYS)
    )
    ly_rev = ly.groupby(["combined_entity_id", "aligned_week"])["revenue"].sum().to_dict()

    # Daily series for the fluctuation engine.
    daily_start = w0_start - dt.timedelta(days=40)
    d_ads = fetch.ce_daily_ads(market, daily_start, w0_end)
    d_biz = fetch.ce_daily_business(market, daily_start, w0_end)
    troas = fetch.troas_history(market, w0_start - dt.timedelta(days=config.TROAS_LOOKBACK_DAYS), w0_end)

    for df in (biz, paid, ly, d_ads, d_biz):
        if "week" in df:
            df["week"] = pd.to_datetime(df["week"]).dt.date
    if "report_date" in d_ads:
        d_ads["report_date"] = pd.to_datetime(d_ads["report_date"]).dt.date
        d_biz["report_date"] = pd.to_datetime(d_biz["report_date"]).dt.date
    if not troas.empty:
        troas["report_date"] = pd.to_datetime(troas["report_date"]).dt.date

    for df in (biz, paid, meta, d_ads, d_biz, troas):
        if "combined_entity_id" in df:
            df["combined_entity_id"] = df["combined_entity_id"].astype(str)

    names = dict(zip(biz["combined_entity_id"], biz["combined_entity_name"]))
    names.update(dict(zip(meta["combined_entity_id"], meta["combined_entity_name"])))
    # Coalesce missing/null names to the CE id so ce_name is never null downstream.
    names = {k: (v if (v is not None and str(v).strip()) else k) for k, v in names.items()}

    # ---- per-CE assembly ----
    biz_idx = {(r["combined_entity_id"], r["week"]): r for _, r in biz.iterrows()}
    paid_idx = {(r["combined_entity_id"], r["week"]): r for _, r in paid.iterrows()}
    meta_idx = {r["combined_entity_id"]: r for _, r in meta.iterrows()}

    all_ce_ids = sorted(set(biz["combined_entity_id"]) | set(paid["combined_entity_id"]))
    ces = []
    paid_contrib_w0: dict[str, float] = {}
    for ce_id in all_ce_ids:
        weekly = []
        for wk in weeks:
            b = biz_idx.get((ce_id, wk))
            p = paid_idx.get((ce_id, wk))
            yoy = ly_rev.get((ce_id, wk))
            row = _weekly_metrics(b if b is not None else None,
                                  p if p is not None else None, yoy_rev=yoy)
            row["week"] = config.iso(wk)
            weekly.append(row)
            if wk == w0_start and row["paid_contribution_pct"] is not None:
                paid_contrib_w0[ce_id] = row["paid_contribution_pct"]
        md = meta_idx.get(ce_id, {})
        ces.append({
            "ce_id": ce_id,
            "ce_name": names.get(ce_id, ce_id),
            "metadata": {
                "category": md.get("category"),
                "subcategory": md.get("subcategory"),
                "city": md.get("city"),
                "management_type": md.get("management_type"),
                "evolution": md.get("evolution"),
                "new_vs_existing": md.get("new_vs_existing"),
                "tier": md.get("tier"),
            },
            "weekly": weekly,
            # per-CE WoW Shapley (traffic x CVR x AOV x CR x TR) for the CE drawer
            "shapley_wow": shapley.wow_revenue_shapley(_ce_levels(weekly[-1]), _ce_levels(weekly[-2]))
            if len(weekly) >= 2 else None,
        })

    # ---- market summary ----
    market_weekly = []
    mkt_levels = {}   # per-week funnel levels for the WoW Shapley
    for wk in weeks:
        bw = biz[biz["week"] == wk]
        pw = paid[paid["week"] == wk]
        rev = float(bw["revenue"].sum())
        orders = float(bw["orders"].sum())
        clicks = float(bw["clicks"].sum())
        ad_conv = float(bw["ad_conversions"].sum())
        gbv = float(bw["gbv"].sum())
        gbv_comp = float(bw["gbv_completed"].sum())
        organic = float(bw["organic_gbv"].sum())
        spend = float(pw["spend"].sum())
        coupon = float(pw["coupon_wallet"].sum())
        cm1 = float(pw["cm1"].sum())

        # Business ROI(1) components (analytics-skill canon).
        cm1_business = (
            rev
            + float(bw["co_marketing_commission"].sum())
            + float(bw["insider_commission"].sum())
            - float(bw["direct_costs"].sum())
        )
        gross_mktg_cost = (
            float(bw["ad_spend_total"].sum())
            + float(bw["coupon_discount"].sum())
            + float(bw["wallet_credits"].sum())
            + float(bw["affiliate_commission"].sum())
            + float(bw["creator_collab_costs"].sum())
            + float(bw["creator_collab_coupon_costs"].sum())
        )
        roi1 = _pct(cm1_business, gross_mktg_cost,
                    gate=(config.ROI_MIN_PCT, config.ROI_MAX_PCT))

        # Paid metrics (ads_campaign_stats — Google Search + Bing).
        paid_impressions = float(pw["paid_impressions"].sum()) if "paid_impressions" in pw else 0
        paid_clicks = float(pw["paid_clicks"].sum())
        paid_conv = float(pw["conversions"].sum())
        conv_value_gbv = float(pw["conv_value_gbv"].sum())
        offline_rev = float(pw["offline_revenue"].sum()) if "offline_revenue" in pw else 0.0
        paid_roi = _pct(cm1, spend + coupon, gate=(config.ROI_MIN_PCT, config.ROI_MAX_PCT))
        paid_cvr = _pct(paid_conv, paid_clicks, gate=(0.0, config.CVR_MAX_PCT))
        # Search Impression Share (Google search only).
        sis_impr = float(pw["sis_impr"].sum()) if "sis_impr" in pw else 0
        sis_elig = float(pw["sis_elig"].sum()) if "sis_elig" in pw else 0

        mkt_levels[wk] = {
            "clicks": clicks, "orders": orders, "gbv": gbv,
            "gbv_completed": gbv_comp, "revenue": rev,
        }

        ly_wk = float(sum(v for (c, aw), v in ly_rev.items() if aw == wk))
        ad_spend_all = float(bw["ad_spend_total"].sum())
        market_weekly.append({
            "week": config.iso(wk),
            "revenue": _num(rev),
            "gbv": _num(gbv),
            "orders": int(orders),
            "clicks": int(clicks),
            "cm2": _num(rev - ad_spend_all),
            "spend": _num(spend),
            "cm1": _num(cm1),
            "roi_pct": paid_roi,                 # Paid RoI (campaign, coupon-inclusive)
            "cvr_pct": _pct(ad_conv, clicks, gate=(0.0, config.CVR_MAX_PCT)),
            "aov": _num(gbv / orders) if orders else None,
            # canon take rate = predicted revenue / completed GBV (Sheet A "TR%")
            "tr_pct": _pct(rev, gbv_comp),
            # completion rate = completed GBV / booked GBV (Sheet A "CR%")
            "cr_pct": _pct(gbv_comp, gbv),
            # canonical business ROI(1) = CM1(business) / Gross Marketing Cost
            "cm1_business": _num(cm1_business),
            "gross_marketing_cost": _num(gross_mktg_cost),
            "roi1_pct": roi1,
            "paid_impressions": int(paid_impressions),
            "paid_clicks": int(paid_clicks),
            "paid_ctr_pct": _pct(paid_clicks, paid_impressions),
            "paid_sis_pct": _pct(sis_impr, sis_elig, gate=(0.0, 100.0)),
            "paid_conv_value": _num(conv_value_gbv),
            "paid_conversions": int(paid_conv),
            "paid_cvr_pct": paid_cvr,
            "cpc": _num(spend / paid_clicks) if paid_clicks else None,
            "paid_revenue": _num(offline_rev),
            "paid_rpc": _num(offline_rev / paid_clicks) if paid_clicks else None,
            "paid_cm2": _num(rev - spend),
            "cm1_per_conv": _num(cm1 / paid_conv) if paid_conv else None,
            "paid_contribution_pct": _num(max(0.0, min(100.0, 100.0 * (1 - organic / gbv_comp)))) if gbv_comp else None,
            "yoy_pct": _num(100.0 * (rev / ly_wk - 1)) if ly_wk else None,
        })

    # Headlines + top movers by raw WoW revenue delta.
    def _ce_rev(ce_id, wk):
        r = biz_idx.get((ce_id, wk))
        return float(r["revenue"]) if r is not None else 0.0

    movers = []
    for ce_id in all_ce_ids:
        delta = _ce_rev(ce_id, w0_start) - _ce_rev(ce_id, wm1_start)
        movers.append({"ce_id": ce_id, "ce_name": names.get(ce_id, ce_id), "delta_wow": _num(delta)})
    movers.sort(key=lambda m: (m["delta_wow"] or 0), reverse=True)
    gainers = [m for m in movers if (m["delta_wow"] or 0) > 0][:5]
    drops = [m for m in movers if (m["delta_wow"] or 0) < 0][-5:][::-1]

    w0_row = next(w for w in market_weekly if w["week"] == config.iso(w0_start))
    wm1_row = next((w for w in market_weekly if w["week"] == config.iso(wm1_start)), None)

    # ---- Section-1 key-metrics table (9 metrics; W0 / W-1 / Δabs / Δ%) ----
    # Each metric maps to a market_weekly field. Δabs and Δ% are W0-vs-W-1.
    # Revenue additionally carries a YoY% (predicted-vs-LY). Paid metrics get NO
    # LY leg (LY crosses the pre-2025-09-01 offline-CM boundary where paid CM is
    # $0/unreliable). Ratio metrics (CR/TR/Paid RoI/ROI1/Paid CVR) report Δ in
    # percentage points (delta_abs = w0 - wm1); absolute-value metrics
    # (Revenue/GBV/Paid Conv Value/Paid Clicks) report a raw-unit delta.
    # (key, label, market_weekly field, ly weekly_ly field | None)
    KEY_METRIC_SPEC = [
        ("revenue", "Revenue", "revenue", "revenue"),
        ("gbv", "GBV", "gbv", "gbv"),
        ("cr_pct", "CR%", "cr_pct", "cr_pct"),
        ("tr_pct", "TR%", "tr_pct", "tr_pct"),
        ("paid_roi", "Paid RoI", "roi_pct", "roi_pct"),
        ("roi1", "ROI 1", "roi1_pct", "roi1_pct"),
        ("paid_conv_value", "Paid Conv Value", "paid_conv_value", "paid_conv_value"),
        ("paid_cvr", "Paid CVR", "paid_cvr_pct", "paid_cvr_pct"),
        ("paid_clicks", "Paid Clicks", "paid_clicks", "paid_clicks"),
    ]

    def _metric_block(field: str, *, yoy=False) -> dict:
        w0v = w0_row.get(field)
        wm1v = wm1_row.get(field) if wm1_row else None
        delta_abs = _num(w0v - wm1v) if (w0v is not None and wm1v is not None) else None
        delta_pct = (
            _num(100.0 * (w0v / wm1v - 1))
            if (w0v is not None and wm1v not in (None, 0)) else None
        )
        block = {
            "w0": w0v,
            "wm1": wm1v,
            "delta_abs": delta_abs,
            "delta_pct": delta_pct,
        }
        if yoy:
            block["yoy_pct"] = w0_row.get("yoy_pct")
        return block

    key_metrics = {}
    for key, label, field, ly_field in KEY_METRIC_SPEC:
        block = _metric_block(field, yoy=(key == "revenue"))
        block["label"] = label
        block["field"] = field         # points into market_summary.weekly[]
        block["has_ly"] = ly_field is not None
        block["ly_field"] = ly_field   # points into market_summary.weekly_ly[]
        key_metrics[key] = block

    headlines = {
        "revenue_w0": w0_row["revenue"],
        "wow_pct": _num(100.0 * (w0_row["revenue"] / wm1_row["revenue"] - 1))
        if (wm1_row and wm1_row["revenue"]) else None,
        "yoy_pct": w0_row["yoy_pct"],
        "roi_w0_pct": w0_row["roi_pct"],           # W0 Paid RoI (coupon-inclusive) — back-compat
        "roi1_w0_pct": w0_row["roi1_pct"],         # canonical business ROI(1), W0
        "key_metrics": key_metrics,                # Section-1 table (9 metrics)
        "top_gainers": gainers,
        "top_drops": drops,
    }

    # ---- WoW revenue Shapley (traffic x CVR x AOV x CR x TR) ----
    headlines["shapley_wow"] = shapley.wow_revenue_shapley(
        mkt_levels.get(w0_start, {}), mkt_levels.get(wm1_start, {})
    )

    # ---- LY 12-week series (full metrics via _weekly_metrics for TY-vs-LY sparklines) ----
    paid_ly = fetch.ce_weekly_ads(market, ly_start, ly_end)
    if not paid_ly.empty:
        paid_ly["week"] = pd.to_datetime(paid_ly["week"]).dt.date
        paid_ly["aligned_week"] = paid_ly["week"].map(
            lambda d: d + dt.timedelta(days=config.YOY_LAG_DAYS)
        )
        paid_ly["combined_entity_id"] = paid_ly["combined_entity_id"].astype(str)

    ly_biz_idx = {(r["combined_entity_id"], r["aligned_week"]): r
                  for _, r in ly.iterrows()}
    ly_paid_idx = ({(r["combined_entity_id"], r["aligned_week"]): r
                    for _, r in paid_ly.iterrows()} if not paid_ly.empty else {})

    # Market-level LY
    ly_biz_cols = [c for c in ly.columns if c not in ("combined_entity_id", "combined_entity_name", "week", "aligned_week")]
    ly_mkt_biz = ly.groupby("aligned_week")[ly_biz_cols].sum()
    ly_mkt_paid = (paid_ly.groupby("aligned_week")[[c for c in paid_ly.columns
                   if c not in ("combined_entity_id", "week", "aligned_week")]].sum()
                   if not paid_ly.empty else pd.DataFrame())

    weekly_ly = []
    for wk in weeks:
        b = ly_mkt_biz.loc[wk] if wk in ly_mkt_biz.index else None
        p = ly_mkt_paid.loc[wk] if (not ly_mkt_paid.empty and wk in ly_mkt_paid.index) else None
        row = _weekly_metrics(b, p)
        row["week"] = config.iso(wk)
        weekly_ly.append(row)

    # Per-CE LY
    for ce in ces:
        cid = ce["ce_id"]
        wly = []
        for wk in weeks:
            b = ly_biz_idx.get((cid, wk))
            p = ly_paid_idx.get((cid, wk))
            row = _weekly_metrics(
                b if b is not None else None,
                p if p is not None else None,
            )
            row["week"] = config.iso(wk)
            wly.append(row)
        ce["weekly_ly"] = wly

    # ---- RE-SOURCE tier: per-CE drawer breakdowns ----
    # A1 (easy): tgids / lead-time / countries — W0 week composition.
    # A2 (hard): channel mix + funnel — W0 / W-1 / LY windows.
    wm1_end = w0_start - dt.timedelta(days=1)
    ly_w0_start = w0_start - dt.timedelta(days=config.YOY_LAG_DAYS)
    ly_w0_end = w0_end - dt.timedelta(days=config.YOY_LAG_DAYS)
    _attach_resource_breakdowns(
        ces,
        fetch.ce_tgids(market, w0_start, w0_end, wm1_start, wm1_end, ly_w0_start, ly_w0_end),
        fetch.ce_tgid_funnel([c["ce_id"] for c in ces], w0_start, w0_end, wm1_start, wm1_end, ly_w0_start, ly_w0_end),
        fetch.ce_tgid_leadtime(market, w0_start, w0_end, wm1_start, wm1_end),
        fetch.ce_leadtime(market, w0_start, w0_end, wm1_start, wm1_end),
        fetch.ce_countries(market, w0_start, w0_end, wm1_start, wm1_end),
    )
    _attach_channels_funnel(
        ces,
        fetch.ce_channels(market, w0_start, w0_end, wm1_start, wm1_end, ly_w0_start, ly_w0_end),
        fetch.ce_funnel([c["ce_id"] for c in ces], w0_start, w0_end, wm1_start, wm1_end, ly_w0_start, ly_w0_end),
    )

    # ---- Week-type calibration: p75 of the trailing-52-week |WoW-Δ| distribution.
    # Small markets churn more, so a fixed $-floor mislabels them (spec §4). Pull
    # 52 weeks of market weekly revenue, take absolute WoW deltas, and use the
    # 75th percentile as the "large" flow threshold. Need >= 20 weeks of history
    # to trust the distribution; otherwise leave None so flows.build_header falls
    # back to the old market-size floor.
    large_threshold = None
    hist_start = w0_start - dt.timedelta(weeks=52)
    mkt_hist = fetch.market_weekly_revenue(market, hist_start, w0_end)
    if not mkt_hist.empty:
        mkt_hist = mkt_hist.sort_values("week")
        wow_deltas = mkt_hist["revenue"].astype(float).diff().abs().dropna()
        if len(wow_deltas) >= 20:
            large_threshold = float(np.percentile(wow_deltas, 75))
            print(f"  week-type calibration: p75 of {len(wow_deltas)} WoW deltas = ${large_threshold:,.0f}")

    # ---- Week header: structural flows / week-type / dual-clock / themes ----
    # LY[t+1] = LY revenue of the week after W0 (from the +7d-extended LY fetch).
    w0_fwd = w0_start + dt.timedelta(days=7)
    ly_forward_rev = {c["ce_id"]: ly_rev.get((c["ce_id"], w0_fwd)) for c in ces}
    headlines["week_header"] = flows.build_header(
        ces, ly_forward_rev, market_weekly, w0_start, large_threshold=large_threshold
    )

    # ---- fluctuation engine ----
    avail_fetcher = None
    if with_availability:
        def avail_fetcher(ce_ids):
            return fetch.availability_signal(
                ce_ids, w0_start - dt.timedelta(days=28), w0_start, w0_end
            )

    week_days = [w0_start + dt.timedelta(days=i) for i in range(7)]
    bucket1, diag = alerts.build_bucket1(
        ce_daily_ads=d_ads,
        ce_daily_business=d_biz,
        ce_weekly=biz,
        ce_weekly_paid=paid,
        names=names,
        paid_contrib=paid_contrib_w0,
        troas=troas,
        w0_start=w0_start,
        wm1_start=wm1_start,
        week_days=week_days,
        availability_fetcher=avail_fetcher,
        shapley_by_ce={c["ce_id"]: c.get("shapley_wow") for c in ces},
    )

    # ---- transitions state model (Phase-2 forward-compat) ----
    transitions = []
    for ce in ces:
        hist = []
        streak = 0
        for w in ce["weekly"]:
            roi = w["roi_pct"]
            below = roi is not None and roi < 100.0
            if below:
                streak += 1
            elif roi is not None:
                streak = 0
            hist.append({"week": w["week"], "roi_pct": roi, "below_100": below})
        if any(h["roi_pct"] is not None for h in hist):
            transitions.append({
                "ce_id": ce["ce_id"],
                "ce_name": ce["ce_name"],
                "weekly": hist,
                "current_streak_weeks_below_100": streak,
            })

    # ---- Bucket B1: ROI/CM2 Movement (weekly flow view) ----
    # Movement-only: renders CEs whose ROI state changed this week (NEW/CLIFF/
    # ESCALATION/EXIT). weeks_below_100 streak comes from the transitions model.
    streak_by_ce = {t["ce_id"]: t["current_streak_weeks_below_100"] for t in transitions}
    b1_result = bucket_b1.build_bucket_b1(ces, streak_by_ce, troas, w0_start, w0_end)
    b1_rows = b1_result["rows"]
    b1_standing = b1_result["standing_count"]

    # ---- Bucket B3: Losing Ground (forecasting — on pace to fall a band) ----
    b3_rows = bucket_b3.build_bucket_b3(ces)

    # ---- Bucket B4: Scale Windows (sticky / NEW WAVE / LOADING lanes) ----
    _struct = flows.per_ce_structural(ces, ly_forward_rev)
    struct_by_ce = {c["ce_id"]: c["struct"] for c in _struct}
    up_swing_ids = {r["ce_id"] for r in bucket1 if r.get("direction") == "up"}
    b4_rows = bucket_b4.build_bucket_b4(ces, struct_by_ce, up_swing_ids, market_weekly)

    # ---- P3: per-bucket sparkline enrichment ----
    ce_by_id = {c["ce_id"]: c for c in ces}
    _enrich_b1_sparklines(b1_rows, ce_by_id)
    _enrich_b3_sparklines(b3_rows, ce_by_id, ly_rev, w0_start)
    _enrich_b4_sparklines(b4_rows, ce_by_id)

    # ---- cross-bucket cascade: one home per CE (B1>B2>B3>B4), dedup + cap 10 ----
    cascade_summary = _apply_cascade({"B1": b1_rows, "B2": bucket1, "B3": b3_rows, "B4": b4_rows})

    # ---- follow-up (reads prior week's bucket1 output if present) ----
    followup = _build_followup(market_slug, wm1_start, bucket1, names, biz, w0_start, wm1_start)

    # ---- optional sibling-worktree fragments ----
    seasonality = _optional_module("seasonality", "build_seasonality", market_slug, w0_start)
    no_bid = _optional_module("no_bid", "build_no_bid", market_slug, w0_start) or {"totals": {"count": 0, "spend_total": 0}, "rows": []}
    levers = _optional_module("levers", "build_levers", market_slug, w0_start) or []

    snapshot = {
        "meta": {
            "market": market,
            "market_slug": market_slug,   # render keys market-switcher tabs on this
            "week_start": config.iso(w0_start),
            "week_end": config.iso(w0_end),
            "weeks": [config.iso(w) for w in weeks],
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "schema_version": config.SCHEMA_VERSION,
            "revenue_basis": "sum_revenue_predicted",  # provenance
            "metric_reference": "analytics-skill (business.md / marketing.md)",
        },
        "market_summary": {"weekly": market_weekly, "weekly_ly": weekly_ly, "headlines": headlines},
        "ces": ces,
        "followup": followup,
        "bucket1_fluctuations": bucket1,
        "bucket_b1": {
            "rows": b1_rows,
            "standing_count": b1_standing,
            "zero_spend_exits": b1_result["zero_spend_exits"],
            "burn_line": b1_result["burn_line"],
            "gray_zone": b1_result["gray_zone"],
        },
        "bucket_b3": {"rows": b3_rows},
        "bucket_b4": {"rows": b4_rows},
        "bucket_cascade": cascade_summary,   # home dedup + hard-cap-10 summary
        "no_bid_campaigns": no_bid,
        "seasonality_adjustments": seasonality or [],
        "levers": levers,
        "transitions": transitions,   # SCHEMA ADDITION: Phase-2 forward-compat
        "_diagnostics": diag,
    }
    return snapshot


# --------------------------------------------------------------------------- #
# Follow-up snapshot
# --------------------------------------------------------------------------- #
def _build_followup(market_slug, prior_week, current_bucket1, names, biz, w0_start, wm1_start):
    prior_path = OUT_DIR / f"snapshot_{market_slug}_{config.iso(prior_week)}.json"
    if not prior_path.exists():
        return []
    try:
        prior = json.loads(prior_path.read_text())
    except Exception:
        return []
    prior_rows = prior.get("bucket1_fluctuations", [])
    current_ids = {r["ce_id"] for r in current_bucket1}
    out = []
    for pr in prior_rows:
        ce_id = pr["ce_id"]
        status = "still flagged" if ce_id in current_ids else "resolved"
        out.append({
            "ce_id": ce_id,
            "ce_name": pr.get("ce_name", names.get(ce_id, ce_id)),
            "flagged_week": prior.get("meta", {}).get("week_start"),
            "signal": f'{pr.get("signal")} {pr.get("direction")} {pr.get("magnitude_pct")}%',
            "status_now": status,
        })
    return out


# --------------------------------------------------------------------------- #
# Optional sibling-worktree module hook
# --------------------------------------------------------------------------- #
def _optional_module(module_name, fn_name, market_slug, w0_start):
    try:
        mod = __import__(module_name)
    except ImportError:
        return None
    fn = getattr(mod, fn_name, None)
    if fn is None:
        return None
    try:
        return fn(market_slug, w0_start)
    except Exception as exc:  # noqa: BLE001
        print(f"  [{module_name}] fragment failed, emitting empty: {exc}")
        return None


# --------------------------------------------------------------------------- #
# Validation against NA references
# --------------------------------------------------------------------------- #
def validate_na(snapshot: dict) -> bool:
    ref = config.VALIDATION_NA
    diag = snapshot["_diagnostics"]
    ok = True
    print("\n----- VALIDATION vs NA references -----")

    got = list(diag["cm1_conv_alert_ces"])
    exp = list(ref["cm1_conv_alerts"])

    def _found(name, pool):
        n = name.lower()
        return any(n in g.lower() or g.lower() in n for g in pool)

    missing = [e for e in exp if not _found(e, got)]
    extra = [g for g in got if not _found(g, exp)]
    match = not missing and not extra and diag["cm1_conv_alert_count"] == len(exp)
    ok &= match
    print(f"CM1/conv alert CEs   : expected {len(exp)}, got {diag['cm1_conv_alert_count']} "
          f"-> {'MATCH' if match else 'MISMATCH'} (name-alias tolerant)")
    if missing or extra:
        print(f"   missing: {missing}")
        print(f"   extra  : {extra}")
    all_up = all(v == "up" for v in diag["cm1_conv_directions"].values()) and diag["cm1_conv_alert_count"] > 0
    print(f"CM1/conv all up-swing: {'YES' if all_up else 'NO'} ({diag['cm1_conv_directions']})")
    ok &= all_up

    cv_ok = diag["cv_excluded_count"] == ref["cv_excluded"]
    ok &= cv_ok
    print(f"CV-excluded          : expected {ref['cv_excluded']}, got {diag['cv_excluded_count']} "
          f"-> {'MATCH' if cv_ok else 'MISMATCH'}")

    rev_pred = snapshot["market_summary"]["headlines"]["revenue_w0"]
    print(f"Market revenue W0    : ${rev_pred:,.0f} (predicted) vs ${ref['market_revenue_actuals']:,.0f} "
          f"(actuals ref; predicted expected ~5% lower — informational, not a gate)")
    print(f"RPC alerts: {diag['rpc_alert_count']} | CVR-drop alerts: {diag['cvr_alert_count']}")
    print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return ok


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _write(snapshot: dict, market_slug: str, w0_start: dt.date) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"snapshot_{market_slug}_{config.iso(w0_start)}.json"
    path.write_text(json.dumps(snapshot, indent=2, default=str))
    print(f"  wrote {path}  ({path.stat().st_size/1024:.0f} KB, {len(snapshot['ces'])} CEs, "
          f"{len(snapshot['bucket1_fluctuations'])} bucket1 rows)")
    return path


def main():
    ap = argparse.ArgumentParser(description="Weekly report snapshot producer")
    ap.add_argument("--market", choices=list(config.MARKETS), help="market slug")
    ap.add_argument("--all", action="store_true", help="build all pilot markets")
    ap.add_argument("--week", help="W0 Monday (YYYY-MM-DD); default = latest matured week")
    ap.add_argument("--validate", action="store_true", help="validate NA against references")
    ap.add_argument("--no-availability", action="store_true", help="skip availability join")
    args = ap.parse_args()

    w0 = _to_date(args.week) if args.week else config.latest_complete_week()
    targets = list(config.MARKETS) if args.all else [args.market or "north_america"]

    for slug in targets:
        snap = build_market(slug, w0, with_availability=not args.no_availability)
        _write(snap, slug, w0)
        if args.validate and slug == "north_america":
            validate_na(snap)


if __name__ == "__main__":
    main()
