#!/usr/bin/env python3
"""build_global — true-global Headout weekly snapshot.

Queries BigQuery directly with NO market filter — all ~69 business_market values
included. Phase 1 uses CE_STATS + ADS_STATS (~21 MB each). RE-SOURCE drawers
(fct_orders/fct_bookings/Mixpanel) are deferred to Phase 3 and bounded to the
surfaced CE set.

Output: .cache/weekly_report/snapshot_headout_{week}.json

Usage:
    python3 build_global.py --week 2026-07-13 [--out <path>]
    then: python3 render.py .cache/weekly_report/snapshot_headout_<week>.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import alerts
import bucket_b1
import bucket_b3
import bucket_b4
import config
import fetch
import flows
import shapley
from build_snapshot import (
    _apply_cascade,
    _attach_channels_funnel,
    _attach_resource_breakdowns,
    _ce_levels,
    _enrich_b1_sparklines,
    _enrich_b3_sparklines,
    _enrich_b4_sparklines,
    _num,
    _pct,
    _weekly_metrics,
)

CACHE = HERE.parent.parent / ".cache" / "weekly_report"


def _json_safe(obj):
    """Recursively replace NaN/Inf floats with None so json.dumps never emits the
    bare NaN/Infinity literals that browser JSON.parse rejects (blank report).
    Also unwraps numpy scalars. Defensive net over the whole snapshot — cheaper
    than auditing every producer for one stray un-_num'd value."""
    import math
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, np.generic):
        obj = obj.item()
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    return obj


# --------------------------------------------------------------------------- #
# Market breakdown — per-market §1 rollup from CE-level data
# --------------------------------------------------------------------------- #
def _market_breakdown(ces, biz_idx, paid_idx, ly_rev, w0_start, wm1_start):
    """Per-market revenue/WoW/YoY/ROI + each market's share of the global WoW move."""

    def _f(v):
        """NaN/None-safe float. A SUM() over an all-NULL CE-week yields NaN, which
        is truthy — `float(nan) or 0` leaks it, poisoning the market accumulator
        (denom→NaN, `nan >= floor`→False, ROI silently nulls for the whole market)."""
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 0.0
        return 0.0 if np.isnan(v) else v

    by_mkt = {}
    for ce in ces:
        mkt = ce.get("metadata", {}).get("market", "Unknown")
        if mkt not in by_mkt:
            by_mkt[mkt] = {"w0": 0.0, "wm1": 0.0, "ly": 0.0,
                           "spend_w0": 0.0, "cw_w0": 0.0, "cm1_w0": 0.0}
        b_w0 = biz_idx.get((ce["ce_id"], w0_start))
        b_wm1 = biz_idx.get((ce["ce_id"], wm1_start))
        ly_val = ly_rev.get((ce["ce_id"], w0_start), 0.0)
        p_w0 = paid_idx.get((ce["ce_id"], w0_start))
        if b_w0 is not None:
            by_mkt[mkt]["w0"] += _f(b_w0.get("revenue"))
        if b_wm1 is not None:
            by_mkt[mkt]["wm1"] += _f(b_wm1.get("revenue"))
        by_mkt[mkt]["ly"] += _f(ly_val)
        if p_w0 is not None:
            by_mkt[mkt]["spend_w0"] += _f(p_w0.get("spend"))
            by_mkt[mkt]["cw_w0"] += _f(p_w0.get("coupon_wallet"))
            by_mkt[mkt]["cm1_w0"] += _f(p_w0.get("cm1"))

    rows = []
    total_delta = 0.0
    n_hidden = 0
    for mkt, v in by_mkt.items():
        # Drop dormant/phantom business_market values (e.g. "#N/A", "Online",
        # "Central LE", legacy country labels) that carry no activity in the whole
        # window — they only clutter the breakdown. total_delta is unaffected (they
        # contribute 0), so contrib_pct stays exact for the real markets.
        if not (v["w0"] or v["wm1"] or v["ly"]):
            n_hidden += 1
            continue
        delta = v["w0"] - v["wm1"]
        total_delta += delta
        denom = v["spend_w0"] + v["cw_w0"]
        roi = _pct(v["cm1_w0"], denom, gate=(config.ROI_MIN_PCT, config.ROI_MAX_PCT)) if denom >= config.WEEKLY_SPEND_FLOOR else None
        rows.append({
            "market": mkt,
            "revenue_w0": _num(v["w0"]),
            "wow_pct": _num(100.0 * (v["w0"] / v["wm1"] - 1)) if v["wm1"] else None,
            "yoy_pct": _num(100.0 * (v["w0"] / v["ly"] - 1)) if v["ly"] else None,
            "roi_pct": roi,
            "delta_abs": _num(delta),
        })
    for r in rows:
        r["contrib_pct"] = _num(100.0 * r["delta_abs"] / total_delta) if total_delta else None
    rows.sort(key=lambda r: -(r["revenue_w0"] or 0))
    return rows, n_hidden


# --------------------------------------------------------------------------- #
# Main build
# --------------------------------------------------------------------------- #
def build_global(week: str) -> dict:
    """True-global Headout snapshot: queries BQ globally (no market filter)."""
    w0_start = dt.date.fromisoformat(week)
    w0_end = w0_start + dt.timedelta(days=6)
    wm1_start = w0_start - dt.timedelta(days=7)
    weeks = config.week_starts(w0_start, config.WEEKS_BACK)
    start = weeks[0]
    print(f"\n=== Headout (global) | W0 {w0_start} ({start}..{w0_end}) ===")

    # ---- 1. Fetch: global queries (no market filter) ----
    print("  fetching ce_weekly_business (global)...")
    biz = fetch.ce_weekly_business(None, start, w0_end)
    print(f"    {len(biz)} rows")

    print("  fetching ce_weekly_ads (global)...")
    paid = fetch.ce_weekly_ads(None, start, w0_end)
    print(f"    {len(paid)} rows")

    print("  fetching ce_metadata (global)...")
    meta_df = fetch.ce_metadata(None, start, w0_end)
    n_markets = meta_df["market"].nunique() if "market" in meta_df.columns else 0
    print(f"    {len(meta_df)} CEs across {n_markets} markets")

    # LY (weekday-aligned -364d + 28d forward for structural / B3 sparklines)
    ly_start = start - dt.timedelta(days=config.YOY_LAG_DAYS)
    ly_end = w0_end - dt.timedelta(days=config.YOY_LAG_DAYS) + dt.timedelta(days=28)
    print("  fetching LY business (global)...")
    ly = fetch.ce_weekly_business(None, ly_start, ly_end)
    ly["aligned_week"] = pd.to_datetime(ly["week"]).dt.date.map(
        lambda d: d + dt.timedelta(days=config.YOY_LAG_DAYS)
    )
    ly_rev = ly.groupby(["combined_entity_id", "aligned_week"])["revenue"].sum().to_dict()
    print(f"    {len(ly)} rows")

    # Daily series for the fluctuation engine (CE_STATS + ADS_STATS only — cheap)
    daily_start = w0_start - dt.timedelta(days=40)
    print("  fetching daily series (global)...")
    d_ads = fetch.ce_daily_ads(None, daily_start, w0_end)
    d_biz = fetch.ce_daily_business(None, daily_start, w0_end)
    d_funnel_g = fetch.ce_daily_paid_google(None, daily_start, w0_end)
    for _c in ("orders", "booked", "attr_value", "attr_completed", "revenue", "clicks"):
        if _c in d_funnel_g.columns:
            d_funnel_g[_c] = pd.to_numeric(d_funnel_g[_c], errors="coerce").fillna(0.0)
    troas = fetch.troas_history(
        None, w0_start - dt.timedelta(days=config.TROAS_LOOKBACK_DAYS), w0_end
    )
    print(f"    daily_ads={len(d_ads)}, daily_biz={len(d_biz)}, "
          f"daily_funnel_g={len(d_funnel_g)}, troas={len(troas)}")

    # ---- Type coercions (same as build_snapshot) ----
    for df in (biz, paid, ly, d_ads, d_biz):
        if "week" in df.columns:
            df["week"] = pd.to_datetime(df["week"]).dt.date
    for df in (d_ads, d_biz, d_funnel_g, troas):
        if not df.empty and "report_date" in df.columns:
            df["report_date"] = pd.to_datetime(df["report_date"]).dt.date
    for df in (biz, paid, meta_df, d_ads, d_biz, d_funnel_g, troas):
        if "combined_entity_id" in df.columns:
            df["combined_entity_id"] = df["combined_entity_id"].astype(str)

    names = dict(zip(biz["combined_entity_id"], biz["combined_entity_name"]))
    names.update(dict(zip(meta_df["combined_entity_id"], meta_df["combined_entity_name"])))
    names = {k: (v if (v is not None and str(v).strip()) else k) for k, v in names.items()}

    # ---- 2. Per-CE assembly ----
    biz_idx = {(r["combined_entity_id"], r["week"]): r for _, r in biz.iterrows()}
    paid_idx = {(r["combined_entity_id"], r["week"]): r for _, r in paid.iterrows()}
    meta_idx = {r["combined_entity_id"]: r for _, r in meta_df.iterrows()}

    # combined_entity_id is a composite string ("1043 - Paris", "1008 - Barcelona") —
    # NOT purely numeric, so we can't gate on digits. Drop only the genuinely null-
    # attributed id (pandas astype(str) turns a NULL campaign_target_combined_entity_id
    # into "nan"/"None"): globally that lone bucket aggregates ~$65K/wk of UNATTRIBUTED
    # paid spend into a phantom "None" CE with no business rows. Its spend still counts
    # in the market_summary totals (computed from the paid df), just not as a fake CE.
    _JUNK_IDS = {"", "nan", "none", "null"}
    all_ce_ids = sorted(
        i for i in (set(biz["combined_entity_id"]) | set(paid["combined_entity_id"]))
        if i is not None and str(i).strip().lower() not in _JUNK_IDS
    )
    print(f"  assembling {len(all_ce_ids)} CEs...")

    ces = []
    paid_contrib_w0 = {}
    for ce_id in all_ce_ids:
        weekly = []
        for wk in weeks:
            b = biz_idx.get((ce_id, wk))
            p = paid_idx.get((ce_id, wk))
            yoy = ly_rev.get((ce_id, wk))
            row = _weekly_metrics(
                b if b is not None else None,
                p if p is not None else None,
                yoy_rev=yoy,
            )
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
                "market": md.get("market", "Unknown"),
            },
            "weekly": weekly,
            "shapley_wow": shapley.wow_revenue_shapley(
                _ce_levels(weekly[-1]), _ce_levels(weekly[-2])
            ) if len(weekly) >= 2 else None,
        })

    # ---- 3. Market summary (global aggregate) ----
    market_weekly = []
    mkt_levels = {}
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

        paid_impressions = float(pw["paid_impressions"].sum()) if "paid_impressions" in pw else 0
        paid_clicks = float(pw["paid_clicks"].sum())
        paid_conv = float(pw["conversions"].sum())
        conv_value_gbv = float(pw["conv_value_gbv"].sum())
        offline_rev = float(pw["offline_revenue"].sum()) if "offline_revenue" in pw else 0.0
        paid_roi = _pct(cm1, spend + coupon, gate=(config.ROI_MIN_PCT, config.ROI_MAX_PCT))
        paid_cvr = _pct(paid_conv, paid_clicks, gate=(0.0, config.CVR_MAX_PCT))
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
            "roi_pct": paid_roi,
            "cvr_pct": _pct(ad_conv, clicks, gate=(0.0, config.CVR_MAX_PCT)),
            "aov": _num(gbv / orders) if orders else None,
            "tr_pct": _pct(rev, gbv_comp),
            "cr_pct": _pct(gbv_comp, gbv),
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
            "avg_cm1": _num(cm1 / paid_conv) if paid_conv else None,
            "cpc": _num(spend / paid_clicks) if paid_clicks else None,
            "paid_revenue": _num(offline_rev),
            "paid_rpc": _num(offline_rev / paid_clicks) if paid_clicks else None,
            "paid_cm2": _num(offline_rev - spend),
            "cm1_per_conv": _num(cm1 / paid_conv) if paid_conv else None,
            "paid_contribution_pct": _num(max(0.0, min(100.0, 100.0 * (1 - organic / gbv_comp)))) if gbv_comp else None,
            "yoy_pct": _num(100.0 * (rev / ly_wk - 1)) if ly_wk else None,
            "sis_impr": _num(sis_impr), "sis_elig": _num(sis_elig), "organic_gbv": _num(organic),
        })

    # ---- 4. Headlines ----
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

    KEY_METRIC_SPEC = [
        ("revenue", "Revenue", "revenue", "revenue"),
        ("gbv", "GBV", "gbv", "gbv"),
        ("orders", "Orders", "orders", "orders"),
        ("aov", "AOV", "aov", "aov"),
        ("cr_pct", "CR%", "cr_pct", "cr_pct"),
        ("tr_pct", "TR%", "tr_pct", "tr_pct"),
        ("paid_clicks", "Paid Clicks", "paid_clicks", "paid_clicks"),
        ("paid_cvr", "Paid CVR", "paid_cvr_pct", "paid_cvr_pct"),
        ("paid_conv_value", "Paid Conv Value", "paid_conv_value", "paid_conv_value"),
        ("avg_cm1", "Avg CM1", "avg_cm1", "avg_cm1"),
        ("paid_roi", "Paid RoI", "roi_pct", "roi_pct"),
        ("roi1", "ROI 1", "roi1_pct", "roi1_pct"),
    ]

    key_metrics = {}
    for key, label, field, ly_field in KEY_METRIC_SPEC:
        w0v = w0_row.get(field)
        wm1v = wm1_row.get(field) if wm1_row else None
        delta_abs = _num(w0v - wm1v) if (w0v is not None and wm1v is not None) else None
        delta_pct = _num(100.0 * (w0v / wm1v - 1)) if (w0v is not None and wm1v not in (None, 0)) else None
        block = {
            "w0": w0v, "wm1": wm1v,
            "delta_abs": delta_abs, "delta_pct": delta_pct,
            "label": label, "field": field,
            "has_ly": ly_field is not None, "ly_field": ly_field,
        }
        if key == "revenue":
            block["yoy_pct"] = w0_row.get("yoy_pct")
        key_metrics[key] = block

    headlines = {
        "revenue_w0": w0_row["revenue"],
        "wow_pct": _num(100.0 * (w0_row["revenue"] / wm1_row["revenue"] - 1))
        if (wm1_row and wm1_row["revenue"]) else None,
        "yoy_pct": w0_row["yoy_pct"],
        "roi_w0_pct": w0_row["roi_pct"],
        "roi1_w0_pct": w0_row["roi1_pct"],
        "key_metrics": key_metrics,
        "top_gainers": gainers,
        "top_drops": drops,
    }

    headlines["shapley_wow"] = shapley.wow_revenue_shapley(
        mkt_levels.get(w0_start, {}), mkt_levels.get(wm1_start, {})
    )

    # ---- 5. LY weekly series (global) ----
    print("  fetching LY ads (global)...")
    paid_ly = fetch.ce_weekly_ads(None, ly_start, ly_end)
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

    ly_biz_cols = [c for c in ly.columns
                   if c not in ("combined_entity_id", "combined_entity_name", "week", "aligned_week")]
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

    # ---- 6. Week-type calibration (global trailing 52w) ----
    large_threshold = None
    hist_start = w0_start - dt.timedelta(weeks=52)
    print("  fetching market_weekly_revenue (global, 52w)...")
    mkt_hist = fetch.market_weekly_revenue(None, hist_start, w0_end)
    if not mkt_hist.empty:
        if "market" in mkt_hist.columns:
            mkt_hist = mkt_hist.groupby("week", as_index=False)["revenue"].sum()
        mkt_hist = mkt_hist.sort_values("week")
        wow_deltas = mkt_hist["revenue"].astype(float).diff().abs().dropna()
        if len(wow_deltas) >= 20:
            large_threshold = float(np.percentile(wow_deltas, 75))
            print(f"  week-type calibration: p75 of {len(wow_deltas)} WoW deltas = ${large_threshold:,.0f}")

    # ---- 7. Week header: structural flows / week-type / dual-clock ----
    w0_fwd = w0_start + dt.timedelta(days=7)
    ly_forward_rev = {c["ce_id"]: ly_rev.get((c["ce_id"], w0_fwd)) for c in ces}
    headlines["week_header"] = flows.build_header(
        ces, ly_forward_rev, market_weekly, w0_start, large_threshold=large_threshold
    )

    # ---- 8. Fluctuation engine + buckets ----
    today = dt.date.today()
    mat_cutoff = min(w0_end, today - dt.timedelta(days=config.MATURITY_DAYS))
    if mat_cutoff < w0_start:
        fallback = config.latest_matured_week(today)
        flux_w0_start, mat_cutoff = fallback, fallback + dt.timedelta(days=6)
    else:
        flux_w0_start = w0_start
    flux_week_days = [flux_w0_start + dt.timedelta(days=i)
                      for i in range((mat_cutoff - flux_w0_start).days + 1)]
    flux_n_days = len(flux_week_days)
    flux_partial = mat_cutoff < (flux_w0_start + dt.timedelta(days=6))
    flux_context_week = config.latest_matured_week(today)

    print("  running fluctuation engine (global)...")
    bucket1, diag = alerts.build_bucket1(
        ce_daily_ads=d_ads,
        ce_daily_business=d_biz,
        ce_daily_funnel_google=d_funnel_g,
        ce_weekly=biz,
        ce_weekly_paid=paid,
        names=names,
        paid_contrib=paid_contrib_w0,
        troas=troas,
        w0_start=flux_w0_start,
        wm1_start=flux_w0_start - dt.timedelta(days=7),
        week_days=flux_week_days,
        w0_end=mat_cutoff,
        availability_fetcher=None,
        shapley_by_ce={c["ce_id"]: c.get("shapley_wow") for c in ces},
    )

    # Transitions + B1/B3/B4
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

    streak_by_ce = {t["ce_id"]: t["current_streak_weeks_below_100"] for t in transitions}
    b1_result = bucket_b1.build_bucket_b1(ces, streak_by_ce, troas, w0_start, w0_end)
    b1_rows = b1_result["rows"]
    b1_standing = b1_result["standing_count"]

    b3_rows = bucket_b3.build_bucket_b3(ces)

    _struct = flows.per_ce_structural(ces, ly_forward_rev)
    struct_by_ce = {c["ce_id"]: c["struct"] for c in _struct}
    up_swing_ids = {r["ce_id"] for r in bucket1 if r.get("direction") == "up"}
    b4_rows = bucket_b4.build_bucket_b4(ces, struct_by_ce, up_swing_ids, market_weekly)

    ce_by_id = {c["ce_id"]: c for c in ces}
    _enrich_b1_sparklines(b1_rows, ce_by_id)
    _enrich_b3_sparklines(b3_rows, ce_by_id, ly_rev, w0_start)
    _enrich_b4_sparklines(b4_rows, ce_by_id)

    cascade_summary = _apply_cascade({"B1": b1_rows, "B2": bucket1, "B3": b3_rows, "B4": b4_rows})

    # ---- 9. Market breakdown ----
    breakdown, n_hidden_markets = _market_breakdown(ces, biz_idx, paid_idx, ly_rev, w0_start, wm1_start)
    print(f"  market breakdown: {len(breakdown)} active markets ({n_hidden_markets} dormant hidden)")

    # ---- 10. CE cap (keep all referenced + top-N by revenue) ----
    CAP = 300

    def _ids(rows):
        return {str(r.get("ce_id")) for r in rows if r.get("ce_id") is not None}

    ref = set()
    ref |= _ids(b1_rows) | _ids(bucket1) | _ids(b3_rows) | _ids(b4_rows)
    ref |= _ids(headlines["week_header"]["trend"]["top_gainers"])
    ref |= _ids(headlines["week_header"]["trend"]["top_droppers"])
    ranked = sorted(ces, key=lambda c: -((c.get("weekly") or [{}])[-1].get("revenue") or 0))
    keep = ref | {str(c["ce_id"]) for c in ranked[:CAP]}
    n_full = len(ces)
    ces_capped = [c for c in ces if str(c["ce_id"]) in keep]

    # ---- 11. RE-SOURCE drawers for surfaced CEs ----
    # fct_orders + fct_bookings run globally (~500 MB total, cheap).
    # Mixpanel queries are CE-filtered (surfaced IDs only, ~42 GB each — within 80 GB cap).
    wm1_end = w0_start - dt.timedelta(days=1)
    ly_w0_start = w0_start - dt.timedelta(days=config.YOY_LAG_DAYS)
    ly_w0_end = w0_end - dt.timedelta(days=config.YOY_LAG_DAYS)
    surfaced_ids = [c["ce_id"] for c in ces_capped]
    # The two Mixpanel drawer queries scan the surfaced-CE set across ALL markets —
    # a bit more than one market's worth. The 7.7 TB table grows daily, so this
    # crept just over the 80 GB per-market rail (~87 GB). Give ONLY these two global
    # calls extra headroom; per-market builds stay at config.MAX_BYTES_BILLED.
    MIXPANEL_GLOBAL_CAP = 140 * 1024 ** 3   # 140 GB

    print(f"  fetching RE-SOURCE drawers for {len(surfaced_ids)} surfaced CEs...")
    print("    tgids (fct_orders, global)...")
    tgids_df = fetch.ce_tgids(None, w0_start, w0_end, wm1_start, wm1_end, ly_w0_start, ly_w0_end)
    print("    tgid_funnel (Mixpanel, CE-filtered)...")
    tgid_funnel_df = fetch.ce_tgid_funnel(surfaced_ids, w0_start, w0_end, wm1_start, wm1_end, ly_w0_start, ly_w0_end, max_bytes=MIXPANEL_GLOBAL_CAP)
    print("    tgid_leadtime (fct_bookings, global)...")
    tgid_lt_df = fetch.ce_tgid_leadtime(None, w0_start, w0_end, wm1_start, wm1_end)
    print("    leadtime (fct_bookings, global)...")
    lead_df = fetch.ce_leadtime(None, w0_start, w0_end, wm1_start, wm1_end)
    print("    countries (fct_orders, global)...")
    ctry_df = fetch.ce_countries(None, w0_start, w0_end, wm1_start, wm1_end)
    print("    channels (fct_orders, global)...")
    chan_df = fetch.ce_channels(None, w0_start, w0_end, wm1_start, wm1_end, ly_w0_start, ly_w0_end)
    print("    funnel (Mixpanel, CE-filtered)...")
    funnel_df = fetch.ce_funnel(surfaced_ids, w0_start, w0_end, wm1_start, wm1_end, ly_w0_start, ly_w0_end, max_bytes=MIXPANEL_GLOBAL_CAP)

    _attach_resource_breakdowns(ces_capped, tgids_df, tgid_funnel_df, tgid_lt_df, lead_df, ctry_df)
    _attach_channels_funnel(ces_capped, chan_df, funnel_df)

    # Overall CVR from funnel data (same as build_snapshot)
    for ce in ces_capped:
        cvr = (ce.get("funnel") or {}).get("CVR")
        wkly = ce.get("weekly") or []
        if cvr and len(wkly) >= 2:
            wkly[-1]["overall_cvr_pct"] = cvr.get("current")
            wkly[-2]["overall_cvr_pct"] = cvr.get("wm1")
    print("    drawers attached.")

    # ---- 12. No-bid campaigns (global: ENABLED, no tROAS, spend ≥ floor) ----
    print("  fetching no-bid campaigns (global)...")
    try:
        import no_bid
        no_bid_result = no_bid.build_no_bid("headout", w0_start)
    except Exception as e:
        print(f"  [no_bid] skipped: {e}")
        no_bid_result = {"totals": {"count": 0, "spend_total": 0}, "rows": []}

    # ---- 13. Assemble snapshot ----
    meta = {
        "market": "Headout (all markets)",
        "market_slug": "headout",
        "n_markets": n_markets,
        "market_breakdown_hidden": n_hidden_markets,   # dormant $0 markets dropped from §1 table
        "week_start": config.iso(w0_start),
        "week_end": config.iso(w0_end),
        "fluctuation_window_start": config.iso(flux_w0_start),
        "fluctuation_window_end": config.iso(mat_cutoff),
        "fluctuation_compare_start": config.iso(flux_w0_start - dt.timedelta(days=7)),
        "fluctuation_compare_end": config.iso(mat_cutoff - dt.timedelta(days=7)),
        "fluctuation_context_week": config.iso(flux_context_week),
        "fluctuation_days": flux_n_days,
        "fluctuation_partial": flux_partial,
        "weeks": [config.iso(w) for w in weeks],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "schema_version": config.SCHEMA_VERSION,
        "revenue_basis": "sum_revenue_predicted",
        "metric_reference": "analytics-skill (business.md / marketing.md)",
        "ce_cap": {
            "shown": len(ces_capped), "total": n_full, "cap": CAP,
            "note": f"All-CE view: top {CAP} by revenue + all flagged / mover CEs "
                    f"({len(ces_capped)} of {n_full})",
        },
    }

    snapshot = {
        "meta": meta,
        "market_breakdown": breakdown,
        "market_summary": {"weekly": market_weekly, "weekly_ly": weekly_ly, "headlines": headlines},
        "ces": ces_capped,
        "followup": [],
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
        "bucket_cascade": cascade_summary,
        "no_bid_campaigns": no_bid_result,
        "seasonality_adjustments": [],
        "levers": [],
        "market_review_context": [],
        "transitions": transitions,
        "_diagnostics": diag,
    }

    # buckets_final (Defend/Compound/Lifecycle reorganization)
    import buckets
    snapshot["buckets_final"] = buckets.build_buckets(snapshot)

    # PP tracking (optional — may fail if dim_pp_allotments unavailable globally)
    try:
        import pp
        snapshot["prepurchase"] = pp.build_pp(snapshot)
    except Exception as e:
        print(f"  [pp] skipped: {e}")
        snapshot["prepurchase"] = []

    # Seasonality tags (optional)
    try:
        import seasonality_llm
        n = seasonality_llm.attach(snapshot)
        print(f"  seasonality tags attached: {n}")
    except Exception as e:
        print(f"  seasonality_llm.attach skipped ({e!r})")

    # Tag bucket rows with market (for §4 Market column in the global report)
    for section_key in ("bucket1_fluctuations",):
        for r in snapshot.get(section_key, []):
            ce = ce_by_id.get(r.get("ce_id"))
            if ce:
                r["market"] = ce.get("metadata", {}).get("market")
    for cat in snapshot.get("buckets_final", {}).values():
        if isinstance(cat, dict):
            for sub in cat.values():
                rows = sub if isinstance(sub, list) else (sub.get("existing", []) + sub.get("new", [])
                        + sub.get("paused", []) + sub.get("tracking_gap", [])
                        if isinstance(sub, dict) else [])
                for r in rows:
                    if isinstance(r, dict) and "ce_id" in r:
                        ce = ce_by_id.get(r["ce_id"])
                        if ce:
                            r["market"] = ce.get("metadata", {}).get("market")

    # Slack digest sidecar (if a prior agent step wrote one)
    sc = CACHE / f"slack_context_headout_{config.iso(w0_start)}.json"
    if sc.exists():
        try:
            snapshot["market_review_context"] = json.loads(sc.read_text())
            print(f"  [slack] loaded {len(snapshot['market_review_context'])} context cards")
        except Exception as e:
            print(f"  [slack] sidecar load skipped ({e!r})")

    return _json_safe(snapshot)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", required=True, help="W0 week-start = SUNDAY (YYYY-MM-DD); snapped to its Sun–Sat week")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    args.week = config.iso(config._week_start(dt.date.fromisoformat(args.week)))   # ensure Sun-Sat week-start
    snap = build_global(args.week)
    out = Path(args.out) if args.out else CACHE / f"snapshot_headout_{args.week}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snap, default=str))
    rev = snap["market_summary"]["headlines"]["revenue_w0"]
    n_mkt = len(snap.get("market_breakdown", []))
    n_ces = len(snap["ces"])
    print(f"\n  wrote {out}  ({n_ces} CEs, {n_mkt} markets, {out.stat().st_size // 1024} KB)")
    print(f"  Headout W0 revenue: ${rev:,.0f}" if rev else "  Headout W0 revenue: N/A")


if __name__ == "__main__":
    main()
