"""
No-Bid Campaign Detection (Section 4) — weekly report.

Identifies ENABLED campaigns with no tROAS target (NULL or 0) that have
meaningful spend (>= WEEKLY_SPEND_FLOOR). Flags campaigns new to the no-bid
set this week vs last week.

Entry point: build_no_bid(market_slug, w0_start) -> dict
matching the no_bid_campaigns contract in the master plan.
"""
from __future__ import annotations

import datetime as dt

import config
from bq import query_df


def _fetch_no_bid_campaigns(
    market: str, start: dt.date, end: dt.date
) -> list[dict]:
    sql = f"""
    SELECT
        campaign_id,
        ANY_VALUE(campaign_name)                                     AS campaign_name,
        ANY_VALUE(campaign_target_combined_entity_id)                AS combined_entity_id,
        ANY_VALUE(campaign_target_combined_entity_name)              AS combined_entity_name,
        ANY_VALUE(current_campaign_bidding_strategy)                 AS bidding_strategy,
        SUM(sum_spend)                                               AS spend,
        SUM(count_clicks)                                            AS clicks,
        SUM(sum_conversion_value_offline_contribution_margin)        AS cm1

    FROM {config.ADS_STATS}

    WHERE campaign_target_business_market = @market
          AND report_date BETWEEN @start AND @end
          AND ad_platform = 'Google Ads'
          AND current_campaign_status = 'ENABLED'
          AND (current_campaign_target_roas IS NULL OR current_campaign_target_roas = 0)

    GROUP BY 1

    HAVING SUM(sum_spend) >= @spend_floor
    """
    df = query_df(
        sql, "no_bid_campaigns",
        {
            "market": market,
            "start": config.iso(start),
            "end": config.iso(end),
            "spend_floor": config.WEEKLY_SPEND_FLOOR,
        },
    )
    if df.empty:
        return []
    df["combined_entity_id"] = df["combined_entity_id"].astype(str)
    return df.to_dict("records")


def _roi_pct(cm1: float, spend: float) -> float | None:
    if spend < config.WEEKLY_SPEND_FLOOR or spend == 0:
        return None
    v = 100.0 * cm1 / spend
    if not (config.ROI_MIN_PCT <= v <= config.ROI_MAX_PCT):
        return None
    return round(v, 2)


def build_no_bid(market_slug: str, w0_start: dt.date) -> dict:
    market = config.MARKETS.get(market_slug)
    if not market:
        return {"totals": {"count": 0, "spend_total": 0}, "rows": []}

    w0_end = w0_start + dt.timedelta(days=6)
    wm1_start = w0_start - dt.timedelta(days=7)
    wm1_end = w0_start - dt.timedelta(days=1)

    print(f"  [no_bid] fetching W0 {w0_start}..{w0_end}")
    w0_rows = _fetch_no_bid_campaigns(market, w0_start, w0_end)

    print(f"  [no_bid] fetching W-1 {wm1_start}..{wm1_end}")
    wm1_rows = _fetch_no_bid_campaigns(market, wm1_start, wm1_end)
    wm1_ids = {r["campaign_id"] for r in wm1_rows}

    spend_total = 0.0
    rows = []
    for r in w0_rows:
        spend = float(r["spend"] or 0)
        cm1 = float(r["cm1"] or 0)
        spend_total += spend
        rows.append({
            "campaign_name": r["campaign_name"],
            "ce_id": str(r["combined_entity_id"]),
            "ce_name": r["combined_entity_name"] or str(r["combined_entity_id"]),
            "bidding_strategy": r["bidding_strategy"],
            "spend_wk": round(spend, 2),
            "roi_pct": _roi_pct(cm1, spend),
            "clicks_wk": int(r["clicks"] or 0),
            "new_this_week": r["campaign_id"] not in wm1_ids,
        })

    rows.sort(key=lambda x: x["spend_wk"], reverse=True)

    result = {
        "totals": {"count": len(rows), "spend_total": round(spend_total, 2)},
        "rows": rows,
    }
    print(f"  [no_bid] {len(rows)} campaigns, ${spend_total:,.0f} total spend")
    return result
