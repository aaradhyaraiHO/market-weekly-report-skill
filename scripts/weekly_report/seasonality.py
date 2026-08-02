"""
Seasonality Visibility (Section 5) — weekly report.

Reads a config CSV of currently-applied seasonality adjustments, computes CM2
performance pre-4w vs in-window, and generates extend/expire recommendations.

Source is swappable: currently a local CSV (seasonality_config.csv), designed
to switch to Google Ads API or Replit store once the real source is confirmed.

Entry point: build_seasonality(market_slug, w0_start) -> list[dict]
matching the seasonality_adjustments contract in the master plan.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

import config
from bq import query_df

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_CSV = SCRIPT_DIR / "seasonality_config.csv"

PRE_WINDOW_WEEKS = 4


# --------------------------------------------------------------------------- #
# Config reader (swappable source)
# --------------------------------------------------------------------------- #
def _read_config(market_slug: str) -> list[dict]:
    if not CONFIG_CSV.exists():
        return []
    df = pd.read_csv(CONFIG_CSV, dtype={"ce_id": str})
    if df.empty:
        return []
    df = df[df["market"] == market_slug]
    for col in ("start_date", "end_date"):
        df[col] = pd.to_datetime(df[col]).dt.date
    return df.to_dict("records")


# --------------------------------------------------------------------------- #
# BQ: weekly CM2 components for a CE shortlist
# --------------------------------------------------------------------------- #
def _fetch_weekly_cm2(
    market: str, ce_ids: list[str], start: dt.date, end: dt.date
) -> pd.DataFrame:
    if not ce_ids:
        return pd.DataFrame()

    sql = f"""
    SELECT
        combined_entity_id,
        ANY_VALUE(combined_entity_name)              AS combined_entity_name,
        DATE_TRUNC(report_date, WEEK(SUNDAY))        AS week,

        SUM({config.REVENUE_COL})                    AS revenue,
        SUM(sum_order_value_completed)               AS gbv_completed,
        SUM(sum_organic_session_order_value)         AS organic_gbv,

        -- CM1(business) = revenue + co_mktg + insider - direct_costs
        SUM({config.REVENUE_COL})
            + SUM(sum_co_marketing_commission)
            + SUM(sum_insider_commission)
            - SUM(sum_direct_costs)                  AS cm1_business,

        -- Gross Marketing Cost (all 13 ad-spend cols + non-ad spend)
        SUM(
            sum_google_ads_spend + sum_google_split_ads_spend
            + sum_pmax_ads_spend + sum_travel_ads_spend
            + sum_google_remarketing_ads_spend + sum_google_brand_ads_spend
            + sum_microsoft_ads_spend + sum_microsoft_split_ads_spend
            + sum_facebook_ads_spend + sum_facebook_split_ads_spend
            + sum_facebook_remarketing_ads_spend
            + sum_apple_ads_spend + sum_criteo_remarketing_ads_spend
        )
        + SUM(sum_coupon_discount)
        + SUM(sum_wallet_credits)
        + SUM(sum_affiliate_commission)
        + SUM(sum_creator_collab_costs)
        + SUM(sum_creator_collab_coupon_costs)       AS gross_marketing_cost

    FROM {config.CE_STATS}

    WHERE business_market = @market
          AND combined_entity_id IN UNNEST(@ce_ids)
          AND report_date BETWEEN @start AND @end

    GROUP BY 1, 3
    """
    df = query_df(
        sql, "seasonality_cm2",
        {
            "market": market,
            "ce_ids": [str(c) for c in ce_ids],
            "start": config.iso(start),
            "end": config.iso(end),
        },
    )
    if not df.empty:
        df["cm2"] = df["cm1_business"] - df["gross_marketing_cost"]
        df["week"] = pd.to_datetime(df["week"]).dt.date
        df["combined_entity_id"] = df["combined_entity_id"].astype(str)
    return df


# --------------------------------------------------------------------------- #
# Status + recommendation
# --------------------------------------------------------------------------- #
def _status(adj_start: dt.date, adj_end: dt.date, w0_start: dt.date) -> str:
    w0_end = w0_start + dt.timedelta(days=6)
    if adj_end < w0_start:
        return "expired"
    if adj_start > w0_end:
        return "scheduled"
    return "active"


def _recommendation(
    cm2_pre: float | None,
    cm2_in: float | None,
    paid_contrib_pct: float | None,
) -> str:
    if paid_contrib_pct is not None and paid_contrib_pct < config.PAID_CONTRIB_LOW_PCT:
        return "review — low paid contribution"
    if cm2_pre is None or cm2_in is None:
        return "insufficient data"
    if cm2_in >= cm2_pre:
        return "extend — CM2 sustaining"
    return "expire — CM2 declining"


# --------------------------------------------------------------------------- #
# Replit deep-link stub
# --------------------------------------------------------------------------- #
def replit_link(ce_id: str, direction: str, pct: float, duration_days: int) -> str:
    # TODO(Aaradhya): replace with real URL once Replit tool params are confirmed.
    return (
        f"TODO://replit-seasonality?ce={ce_id}"
        f"&dir={direction}&pct={pct}&days={duration_days}"
    )


# --------------------------------------------------------------------------- #
# Main builder
# --------------------------------------------------------------------------- #
def build_seasonality(market_slug: str, w0_start: dt.date) -> list[dict]:
    market = config.MARKETS.get(market_slug)
    if not market:
        return []

    adjustments = _read_config(market_slug)
    if not adjustments:
        print("  [seasonality] no adjustments configured — emitting empty")
        return []

    ce_ids = list({str(a["ce_id"]) for a in adjustments})
    w0_end = w0_start + dt.timedelta(days=6)

    earliest = min(a["start_date"] for a in adjustments)
    fetch_start = earliest - dt.timedelta(weeks=PRE_WINDOW_WEEKS)

    print(f"  [seasonality] {len(adjustments)} adjustments, fetching CM2 "
          f"{fetch_start}..{w0_end} for {len(ce_ids)} CEs")
    cm2_df = _fetch_weekly_cm2(market, ce_ids, fetch_start, w0_end)

    names: dict[str, str] = {}
    if not cm2_df.empty:
        for _, r in cm2_df.iterrows():
            cid = r["combined_entity_id"]
            n = r.get("combined_entity_name")
            if n and str(n).strip():
                names[cid] = str(n)

    results = []
    for adj in adjustments:
        ce_id = str(adj["ce_id"])
        adj_start = adj["start_date"]
        adj_end = adj["end_date"]
        direction = str(adj.get("direction", "")).lower()
        pct = float(adj.get("pct", 0))

        status = _status(adj_start, adj_end, w0_start)

        pre_begin = adj_start - dt.timedelta(weeks=PRE_WINDOW_WEEKS)
        pre_end = adj_start - dt.timedelta(days=1)
        in_end = min(adj_end, w0_end)

        ce_rows = (
            cm2_df[cm2_df["combined_entity_id"] == ce_id]
            if not cm2_df.empty else pd.DataFrame()
        )

        cm2_pre_avg = None
        cm2_in_avg = None
        rev_pre_avg = None
        rev_in_avg = None
        paid_contrib_pct = None

        if not ce_rows.empty:
            pre = ce_rows[(ce_rows["week"] >= pre_begin) & (ce_rows["week"] <= pre_end)]
            inw = ce_rows[(ce_rows["week"] >= adj_start) & (ce_rows["week"] <= in_end)]

            if not pre.empty:
                cm2_pre_avg = float(pre["cm2"].mean())
                rev_pre_avg = float(pre["revenue"].mean())
            if not inw.empty:
                cm2_in_avg = float(inw["cm2"].mean())
                rev_in_avg = float(inw["revenue"].mean())

            w0_row = ce_rows[ce_rows["week"] == w0_start]
            if not w0_row.empty:
                gbv_c = float(w0_row.iloc[0]["gbv_completed"])
                org = float(w0_row.iloc[0]["organic_gbv"])
                if gbv_c:
                    paid_contrib_pct = round(max(0.0, min(100.0, 100.0 * (1 - org / gbv_c))), 2)

        revenue_delta_pct = None
        if rev_pre_avg and rev_in_avg is not None:
            revenue_delta_pct = round(100.0 * (rev_in_avg / rev_pre_avg - 1), 2)

        rec = _recommendation(cm2_pre_avg, cm2_in_avg, paid_contrib_pct)
        duration = (adj_end - adj_start).days
        ce_name = adj.get("ce_name") or names.get(ce_id, ce_id)

        results.append({
            "ce_id": ce_id,
            "ce_name": str(ce_name),
            "direction": direction,
            "pct": pct,
            "start_date": config.iso(adj_start),
            "end_date": config.iso(adj_end),
            "status": status,
            "cm2_pre_4w_avg": round(cm2_pre_avg, 2) if cm2_pre_avg is not None else None,
            "cm2_in_window_avg": round(cm2_in_avg, 2) if cm2_in_avg is not None else None,
            "revenue_delta_pct": revenue_delta_pct,
            "recommendation": rec,
        })

    active = sum(1 for r in results if r["status"] == "active")
    print(f"  [seasonality] {len(results)} rows ({active} active)")
    return results
