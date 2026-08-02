"""
Levers Visibility (Section 6) — weekly report.

Reads a config CSV of CEs with active levers (PP / marketing_budget /
tr_incentive), fetches W0 and W-1 weekly performance, and emits a summary
for each tagged CE.

Source is swappable: currently a local CSV (levers_config.csv), same pattern
as seasonality_config.csv. Tag sources TBD (Aaradhya).

Entry point: build_levers(market_slug, w0_start) -> list[dict]
matching the levers contract in the master plan.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

import config
from bq import query_df

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_CSV = SCRIPT_DIR / "levers_config.csv"

VALID_LEVERS = {"pp", "marketing_budget", "tr_incentive"}


def _read_config(market_slug: str) -> list[dict]:
    if not CONFIG_CSV.exists():
        return []
    df = pd.read_csv(CONFIG_CSV, dtype={"ce_id": str})
    if df.empty:
        return []
    df = df[df["market"] == market_slug]
    if df.empty:
        return []
    df["since"] = pd.to_datetime(df["since"]).dt.date
    return df.to_dict("records")


def _fetch_weekly_perf(
    market: str, ce_ids: list[str], start: dt.date, end: dt.date
) -> pd.DataFrame:
    if not ce_ids:
        return pd.DataFrame()

    biz_sql = f"""
    SELECT
        combined_entity_id,
        DATE_TRUNC(report_date, WEEK(SUNDAY))    AS week,
        SUM({config.REVENUE_COL})                 AS revenue

    FROM {config.CE_STATS}

    WHERE business_market = @market
          AND combined_entity_id IN UNNEST(@ce_ids)
          AND report_date BETWEEN @start AND @end

    GROUP BY 1, 2
    """
    biz = query_df(
        biz_sql, "levers_biz",
        {
            "market": market,
            "ce_ids": [str(c) for c in ce_ids],
            "start": config.iso(start),
            "end": config.iso(end),
        },
    )

    ads_sql = f"""
    SELECT
        campaign_target_combined_entity_id        AS combined_entity_id,
        DATE_TRUNC(report_date, WEEK(SUNDAY))     AS week,
        SUM(sum_spend)                            AS spend,
        SUM(sum_conversion_value_offline_contribution_margin)  AS cm1

    FROM {config.ADS_STATS}

    WHERE campaign_target_business_market = @market
          AND campaign_target_combined_entity_id IN UNNEST(@ce_ids)
          AND report_date BETWEEN @start AND @end

    GROUP BY 1, 2
    """
    ads = query_df(
        ads_sql, "levers_ads",
        {
            "market": market,
            "ce_ids": [str(c) for c in ce_ids],
            "start": config.iso(start),
            "end": config.iso(end),
        },
    )

    if biz.empty and ads.empty:
        return pd.DataFrame()

    for df in (biz, ads):
        if not df.empty:
            df["combined_entity_id"] = df["combined_entity_id"].astype(str)
            df["week"] = pd.to_datetime(df["week"]).dt.date

    if biz.empty:
        return ads
    if ads.empty:
        return biz
    return biz.merge(ads, on=["combined_entity_id", "week"], how="outer")


def _num(x) -> float | None:
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN check
        return None
    return round(f, 2)


def _roi_pct(cm1: float | None, spend: float | None) -> float | None:
    if cm1 is None or spend is None:
        return None
    if spend < config.WEEKLY_SPEND_FLOOR or spend == 0:
        return None
    v = 100.0 * cm1 / spend
    if not (config.ROI_MIN_PCT <= v <= config.ROI_MAX_PCT):
        return None
    return round(v, 2)


def build_levers(market_slug: str, w0_start: dt.date) -> list[dict]:
    market = config.MARKETS.get(market_slug)
    if not market:
        return []

    tagged = _read_config(market_slug)
    if not tagged:
        print("  [levers] no CEs tagged — emitting empty")
        return []

    ce_ids = list({str(t["ce_id"]) for t in tagged})
    w0_end = w0_start + dt.timedelta(days=6)
    wm1_start = w0_start - dt.timedelta(days=7)

    print(f"  [levers] {len(tagged)} tagged CEs, fetching {wm1_start}..{w0_end}")
    perf = _fetch_weekly_perf(market, ce_ids, wm1_start, w0_end)

    perf_idx: dict[tuple[str, dt.date], dict] = {}
    if not perf.empty:
        for _, r in perf.iterrows():
            perf_idx[(str(r["combined_entity_id"]), r["week"])] = r

    results = []
    for t in tagged:
        ce_id = str(t["ce_id"])
        lever = str(t.get("lever", "")).lower()
        if lever not in VALID_LEVERS:
            continue

        w0 = perf_idx.get((ce_id, w0_start))
        wm1 = perf_idx.get((ce_id, wm1_start))

        rev_w0 = _num(w0["revenue"]) if w0 is not None and "revenue" in w0 else None
        rev_wm1 = _num(wm1["revenue"]) if wm1 is not None and "revenue" in wm1 else None
        spend_w0 = _num(w0["spend"]) if w0 is not None and "spend" in w0 else None
        cm1_w0 = _num(w0["cm1"]) if w0 is not None and "cm1" in w0 else None

        wow_pct = None
        if rev_w0 is not None and rev_wm1 and rev_wm1 != 0:
            wow_pct = round(100.0 * (rev_w0 / rev_wm1 - 1), 2)

        results.append({
            "ce_id": ce_id,
            "ce_name": t.get("ce_name") or ce_id,
            "lever": lever,
            "since": config.iso(t["since"]),
            "weekly_perf_summary": {
                "revenue_w0": rev_w0,
                "revenue_wm1": rev_wm1,
                "wow_pct": wow_pct,
                "spend_w0": spend_w0,
                "cm1_w0": cm1_w0,
                "roi_pct_w0": _roi_pct(cm1_w0, spend_w0),
            },
        })

    print(f"  [levers] {len(results)} lever rows emitted")
    return results
