"""
BigQuery fetch layer for the weekly report mart.

Every metric follows the analytics-skill canon. Revenue = sum_revenue_predicted
(see config.REVENUE_COL). All returned frames key on combined_entity_id (STRING)
and, where weekly, a `week` DATE column truncated to the report week start
(Sun→Sat weeks since 2026-08-03; see config.WEEK_START_DAY).
"""
from __future__ import annotations

import datetime as dt

import pandas as pd

import config
from bq import query_df

REV = config.REVENUE_COL


# --------------------------------------------------------------------------- #
# CE-level weekly business funnel  (combined_entity_stats)
# --------------------------------------------------------------------------- #
def ce_weekly_business(market: str | None, start: dt.date, end: dt.date) -> pd.DataFrame:
    """
    Weekly CE funnel: revenue (predicted), orders, clicks, ad conversions, GBV,
    completed GBV, organic GBV. No is_forecasted filter (canon; windows are past).

    Also SUMs every cost/commission component needed for the canonical business
    ROI(1) (analytics-skill business.md "Marketing Spend" / "ROI & Contribution
    Margin"):
        CM1_business = revenue_predicted + co_marketing_commission
                       + insider_commission - direct_costs
        Gross_Marketing_Cost = Ad_Spend_Total + coupon_discount + wallet_credits
                       + affiliate_commission + creator_collab_costs
                       + creator_collab_coupon_costs
        ROI(1) = 100 * CM1_business / Gross_Marketing_Cost
    Kept market-level aggregatable (grouped by CE + week) so build_snapshot can
    roll the components up before dividing.
    """
    sql = f"""
    SELECT
        combined_entity_id,
        ANY_VALUE(combined_entity_name)          AS combined_entity_name,
        DATE_TRUNC(report_date, WEEK(SUNDAY))    AS week,
        SUM({REV})                               AS revenue,
        SUM(count_orders)                        AS orders,
        SUM(count_ad_clicks)                     AS clicks,
        SUM(count_ad_conversions)                AS ad_conversions,
        SUM(sum_order_value)                     AS gbv,
        SUM(sum_order_value_completed)           AS gbv_completed,
        SUM(sum_organic_session_order_value)     AS organic_gbv,

        -- CM1(business) components
        SUM(sum_co_marketing_commission)         AS co_marketing_commission,
        SUM(sum_insider_commission)              AS insider_commission,
        SUM(sum_direct_costs)                     AS direct_costs,

        -- Ad Spend (Total) — all 13 platform spend columns (business.md canon)
        SUM(
            sum_google_ads_spend
            + sum_google_split_ads_spend
            + sum_pmax_ads_spend
            + sum_travel_ads_spend
            + sum_google_remarketing_ads_spend
            + sum_google_brand_ads_spend
            + sum_microsoft_ads_spend
            + sum_microsoft_split_ads_spend
            + sum_facebook_ads_spend
            + sum_facebook_split_ads_spend
            + sum_facebook_remarketing_ads_spend
            + sum_apple_ads_spend
            + sum_criteo_remarketing_ads_spend
        )                                        AS ad_spend_total,

        -- Gross Marketing Cost non-ad-spend components
        SUM(sum_coupon_discount)                 AS coupon_discount,
        SUM(sum_wallet_credits)                  AS wallet_credits,
        SUM(sum_affiliate_commission)            AS affiliate_commission,
        SUM(sum_creator_collab_costs)            AS creator_collab_costs,
        SUM(sum_creator_collab_coupon_costs)     AS creator_collab_coupon_costs

    FROM {config.CE_STATS}

    WHERE report_date BETWEEN @start AND @end
          {'AND business_market = @market' if market else ''}

    GROUP BY 1, 3
    """
    params = {"start": config.iso(start), "end": config.iso(end)}
    if market:
        params["market"] = market
    return query_df(sql, "ce_weekly_business", params)


# --------------------------------------------------------------------------- #
# Market-level trailing weekly revenue  (combined_entity_stats)
# --------------------------------------------------------------------------- #
def market_weekly_revenue(market: str | None, start: dt.date, end: dt.date) -> pd.DataFrame:
    """
    Market-level weekly revenue (predicted) over [start, end], one row per report
    week-start. Used to calibrate the week-type "large" threshold from the
    market's own trailing-52-week WoW-delta distribution (small markets churn
    more, so a fixed $-floor mislabels them). Returns columns: week (DATE),
    revenue (FLOAT).
    """
    mkt_col = ",\n        business_market AS market" if not market else ""
    mkt_grp = ", business_market" if not market else ""
    sql = f"""
    SELECT
        DATE_TRUNC(report_date, WEEK(SUNDAY))    AS week{mkt_col},
        SUM({REV})                               AS revenue

    FROM {config.CE_STATS}

    WHERE report_date BETWEEN @start AND @end
          {'AND business_market = @market' if market else ''}

    GROUP BY 1{mkt_grp}

    ORDER BY 1
    """
    params = {"start": config.iso(start), "end": config.iso(end)}
    if market:
        params["market"] = market
    return query_df(sql, "market_weekly_revenue", params)


# --------------------------------------------------------------------------- #
# CE-level weekly paid performance  (ads_campaign_stats — Google + Bing)
# --------------------------------------------------------------------------- #
def ce_weekly_ads(market: str | None, start: dt.date, end: dt.date) -> pd.DataFrame:
    """
    Weekly CE paid rollup: spend, coupon+wallet, CM1 (with pre/post Sep-2025
    migration fallback), conversions, paid clicks, conv value.
    Source: ads_campaign_stats (Google Ads + Microsoft/Bing, all campaign types).
    """
    sql = f"""
    SELECT
        campaign_target_combined_entity_id                        AS combined_entity_id,
        DATE_TRUNC(report_date, WEEK(SUNDAY))                     AS week,
        SUM(sum_spend)                                            AS spend,
        SUM(sum_coupon_and_wallet_credits)                       AS coupon_wallet,
        -- CM1: offline contribution margin post-Sep-2025, calculated fallback pre-Sep
        SUM(CASE
            WHEN report_date >= '2025-09-01'
                 AND sum_conversion_value_offline_contribution_margin > 0
                THEN sum_conversion_value_offline_contribution_margin
            ELSE sum_conversion_value_calculated_contribution_margin
        END)                                                      AS cm1,
        SUM(CASE
            WHEN report_date >= '2025-09-01'
                 AND count_conversions_offline_contribution_margin > 0
                THEN count_conversions_offline_contribution_margin
            ELSE count_conversions_online
        END)                                                      AS conversions,
        SUM(sum_conversion_value_offline_revenue)                AS offline_revenue,
        SUM(count_impressions)                                   AS paid_impressions,
        SUM(count_clicks)                                        AS paid_clicks,
        SUM(sum_conversion_value_offline_gross_bookings)         AS conv_value_gbv,
        -- Google-Search-only paid (2026-07-17): pause/scale decisions are Google-only, not Bing.
        -- Feeds the Losing Money + Fluctuations 'weekly_google' money columns; the rest of the
        -- report keeps the Google+Bing rollup above. (SEARCH filter already applied in WHERE.)
        SUM(IF(ad_platform = 'Google Ads', sum_spend, 0))       AS spend_g,
        SUM(IF(ad_platform = 'Google Ads', CASE
            WHEN report_date >= '2025-09-01'
                 AND sum_conversion_value_offline_contribution_margin > 0
                THEN sum_conversion_value_offline_contribution_margin
            ELSE sum_conversion_value_calculated_contribution_margin
        END, 0))                                                AS cm1_g,
        SUM(IF(ad_platform = 'Google Ads', count_clicks, 0))    AS paid_clicks_g,
        SUM(IF(ad_platform = 'Google Ads', CASE
            WHEN report_date >= '2025-09-01'
                 AND count_conversions_offline_contribution_margin > 0
                THEN count_conversions_offline_contribution_margin
            ELSE count_conversions_online
        END, 0))                                                AS conversions_g,
        -- Google-Search take rate components: net revenue ÷ gross booking value (offline attr).
        SUM(IF(ad_platform = 'Google Ads', sum_conversion_value_offline_revenue, 0))        AS offline_revenue_g,
        SUM(IF(ad_platform = 'Google Ads', sum_conversion_value_offline_gross_bookings, 0)) AS gbv_g,
        -- Search Impression Share — GOOGLE SEARCH ONLY. Bing's
        -- count_eligible_searches is unreliable (yields SIS > 100%), so SIS is
        -- Google-only (perf-audit canon: SUM(impr)/SUM(eligible), never
        -- AVG(search_impression_share)).
        SUM(IF(ad_platform = 'Google Ads', count_impressions, 0))       AS sis_impr,
        SUM(IF(ad_platform = 'Google Ads', count_eligible_searches, 0)) AS sis_elig

    FROM {config.ADS_STATS}

    WHERE report_date BETWEEN @start AND @end
          {'AND campaign_target_business_market = @market' if market else ''}
          AND ad_platform IN ('Google Ads', 'Microsoft Ads')
          AND campaign_advertising_channel_type = 'SEARCH'

    GROUP BY 1, 2
    """
    params = {"start": config.iso(start), "end": config.iso(end)}
    if market:
        params["market"] = market
    return query_df(sql, "ce_weekly_ads", params)


# --------------------------------------------------------------------------- #
# CE metadata  (dim_combined_entities + city from stats)
# --------------------------------------------------------------------------- #
def ce_metadata(market: str | None, start: dt.date, end: dt.date) -> pd.DataFrame:
    """
    Pivot dimensions for the all-CE view. city is not on the dim, so it is
    sourced from combined_entity_stats (most-frequent value in window).
    """
    dim_where = "WHERE market = @market" if market else ""
    sql = f"""
    WITH dim AS (

        SELECT
            combined_entity_id,
            combined_entity_name,
            market,
            -- Group-by dims. ~45% of *active* CEs are an unenriched dormant tail
            -- (zero-revenue "Airport Services", "Wifi & SIM", brand-new CEs) with
            -- NULL dims — only ~0.13% of revenue. Coalesce NULLs to explicit,
            -- honest buckets so group-by / chips / subtotals never show blanks
            -- (same pattern as the tier 'Unclassified' collapse below).
            COALESCE(combined_entity_category, 'Uncategorized')    AS category,
            COALESCE(combined_entity_subcategory, 'Uncategorized') AS subcategory,
            COALESCE(evolution_bucket, 'Unknown')                  AS evolution,
            COALESCE(management_type, 'Unknown')                   AS management_type,
            -- 3-way: NULL is_existing was previously coerced to 'New' (inflated
            -- the New count) — now surfaced as 'Unknown'.
            CASE
                WHEN is_existing IS TRUE  THEN 'Existing'
                WHEN is_existing IS FALSE THEN 'New'
                ELSE 'Unknown'
            END                                     AS new_vs_existing,
            -- 2025 annual CE tier; collapse NULL + placeholder "Does not Exist *"
            -- values to a single Unclassified bucket.
            CASE
                WHEN bucket_2025 IS NULL THEN 'Unclassified'
                WHEN bucket_2025 LIKE '4. Does not Exist%' THEN 'Unclassified'
                ELSE bucket_2025
            END                                     AS tier,
            country,
            region

        FROM {config.DIM_CE}

        {dim_where}

    ),

    city_counts AS (

        SELECT
            combined_entity_id,
            city,
            COUNT(*) AS n

        FROM {config.CE_STATS}

        WHERE report_date BETWEEN @start AND @end
              {'AND business_market = @market' if market else ''}
              AND city IS NOT NULL

        GROUP BY 1, 2

    ),

    city AS (

        SELECT
            combined_entity_id,
            city

        FROM city_counts

        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY combined_entity_id
            ORDER BY n DESC
        ) = 1

    )

    SELECT
        dim.*,
        COALESCE(city.city, 'Unknown')  AS city

    FROM dim
    LEFT JOIN city USING (combined_entity_id)
    """
    params = {"start": config.iso(start), "end": config.iso(end)}
    if market:
        params["market"] = market
    return query_df(sql, "ce_metadata", params)


# --------------------------------------------------------------------------- #
# RE-SOURCE tier (A1) — per-CE composition breakdowns for the CE drawer
# --------------------------------------------------------------------------- #
# tgids / lead-time / countries are the "easy" full-drawer sections. They are
# COMPOSITION tables (rev/orders share within the CE for the W0 week), sourced
# from fct_orders / fct_bookings at experience / booking / country grain — a
# grain combined_entity_stats does not carry. Consequences:
#   • Revenue here is ACTUALS (`amount_revenue_usd` / `price_net_usd`), NOT the
#     predicted basis used elsewhere. Predicted revenue is not resolvable at this
#     grain; shares are basis-robust, so composition reads the same either way.
#     (Matches the CE-Health drawer's own "breakdowns use actual revenue" note.)
#   • Window is the W0 reporting week only, so long-tail CEs degrade to few/empty
#     rows — the drawer renders "—/n/a" for those, by design.
# Each is ONE market-level batch query grouped by CE; build_snapshot splits per CE.
def ce_tgids(
    market: str | None,
    w0_start: dt.date, w0_end: dt.date,
    wm1_start: dt.date, wm1_end: dt.date,
    ly_start: dt.date, ly_end: dt.date,
) -> pd.DataFrame:
    """Enriched TGID table: rev, orders, GBV, completed GBV for W0 + W-1 + LY."""
    mkt = "AND business_market = @market" if market else ""
    sql = """
    SELECT
        combined_entity_id,
        CAST(experience_id AS STRING)                              AS tgid,
        ANY_VALUE(experience_name)                                 AS experience,

        SUM(CASE WHEN DATE(created_at) BETWEEN @w0_s AND @w0_e
            THEN amount_revenue_usd ELSE 0 END)                    AS rev,
        COUNT(DISTINCT CASE WHEN DATE(created_at) BETWEEN @w0_s AND @w0_e
            THEN order_id END)                                     AS orders,
        SUM(CASE WHEN DATE(created_at) BETWEEN @w0_s AND @w0_e
            THEN order_value_usd ELSE 0 END)                       AS gbv,
        SUM(CASE WHEN DATE(created_at) BETWEEN @w0_s AND @w0_e
            AND order_status = 'Completed'
            THEN order_value_usd ELSE 0 END)                       AS completed_gbv,

        SUM(CASE WHEN DATE(created_at) BETWEEN @wm1_s AND @wm1_e
            THEN amount_revenue_usd ELSE 0 END)                    AS rev_wm1,
        COUNT(DISTINCT CASE WHEN DATE(created_at) BETWEEN @wm1_s AND @wm1_e
            THEN order_id END)                                     AS orders_wm1,
        SUM(CASE WHEN DATE(created_at) BETWEEN @wm1_s AND @wm1_e
            THEN order_value_usd ELSE 0 END)                       AS gbv_wm1,
        SUM(CASE WHEN DATE(created_at) BETWEEN @wm1_s AND @wm1_e
            AND order_status = 'Completed'
            THEN order_value_usd ELSE 0 END)                       AS completed_gbv_wm1,

        SUM(CASE WHEN DATE(created_at) BETWEEN @ly_s AND @ly_e
            THEN amount_revenue_usd ELSE 0 END)                    AS rev_ly,
        COUNT(DISTINCT CASE WHEN DATE(created_at) BETWEEN @ly_s AND @ly_e
            THEN order_id END)                                     AS orders_ly,
        SUM(CASE WHEN DATE(created_at) BETWEEN @ly_s AND @ly_e
            THEN order_value_usd ELSE 0 END)                       AS gbv_ly,
        SUM(CASE WHEN DATE(created_at) BETWEEN @ly_s AND @ly_e
            AND order_status = 'Completed'
            THEN order_value_usd ELSE 0 END)                       AS completed_gbv_ly

    FROM {tbl}

    WHERE (DATE(created_at) BETWEEN @w0_s AND @w0_e
           OR DATE(created_at) BETWEEN @wm1_s AND @wm1_e
           OR DATE(created_at) BETWEEN @ly_s AND @ly_e)
          {mkt}
          AND order_status NOT IN ('Dummy', 'Cancelled - Fraudulent')
          AND user_type = 'Customer'
          AND experience_id IS NOT NULL

    GROUP BY 1, 2
    HAVING SUM(CASE WHEN DATE(created_at) BETWEEN @w0_s AND @w0_e
               THEN amount_revenue_usd ELSE 0 END) > 0
        OR SUM(CASE WHEN DATE(created_at) BETWEEN @ly_s AND @ly_e
               THEN amount_revenue_usd ELSE 0 END) > 0
    """.format(tbl=config.FCT_ORDERS, mkt=mkt)
    params = {
        "w0_s": config.iso(w0_start), "w0_e": config.iso(w0_end),
        "wm1_s": config.iso(wm1_start), "wm1_e": config.iso(wm1_end),
        "ly_s": config.iso(ly_start), "ly_e": config.iso(ly_end),
    }
    if market:
        params["market"] = market
    return query_df(sql, "ce_tgids", params)


def ce_variants(
    market: str | None,
    w0_start: dt.date, w0_end: dt.date,
    wm1_start: dt.date, wm1_end: dt.date,
    ly_start: dt.date, ly_end: dt.date,
) -> pd.DataFrame:
    """Booking-grain variant children with order economics allocated exactly once.

    `fct_orders` has the canonical TGID revenue but no variant key.  The join to
    `fct_bookings` allocates each order's economics across its bookings by
    payable-value share (equal share when the denominator is zero).  Order
    credit is split across distinct variants on an order so child totals remain
    additive.  Null variant IDs are retained as an explicit unattributed bucket.
    """
    mkt = "AND o.business_market = @market" if market else ""
    sql = """
    WITH booking_rows AS (
        SELECT
            o.combined_entity_id,
            CAST(o.experience_id AS STRING)                         AS tgid,
            COALESCE(CAST(b.variant_id AS STRING), '__UNATTRIBUTED__') AS variant_id,
            COALESCE(b.variant_name, 'Unattributed variant')        AS variant_name,
            b.booking_id,
            o.order_id,
            b.lead_time_days,
            CASE
                WHEN DATE(o.created_at) BETWEEN @w0_s AND @w0_e   THEN 'w0'
                WHEN DATE(o.created_at) BETWEEN @wm1_s AND @wm1_e THEN 'wm1'
                WHEN DATE(o.created_at) BETWEEN @ly_s AND @ly_e   THEN 'ly'
            END                                                     AS period,
            SAFE_DIVIDE(
                COALESCE(b.price_payable_usd, 0),
                NULLIF(SUM(COALESCE(b.price_payable_usd, 0)) OVER (PARTITION BY o.order_id), 0)
            )                                                       AS payable_weight,
            COUNT(*) OVER (PARTITION BY o.order_id)                 AS booking_count,
            o.amount_revenue_usd,
            o.order_value_usd,
            o.order_status
        FROM {bookings} b
        JOIN {orders} o USING (order_id)
        WHERE (DATE(o.created_at) BETWEEN @w0_s AND @w0_e
               OR DATE(o.created_at) BETWEEN @wm1_s AND @wm1_e
               OR DATE(o.created_at) BETWEEN @ly_s AND @ly_e)
              {mkt}
              AND o.order_status NOT IN ('Dummy', 'Cancelled - Fraudulent')
              AND o.user_type = 'Customer'
              AND o.experience_id IS NOT NULL
              AND CAST(b.experience_id AS STRING) = CAST(o.experience_id AS STRING)
    ), allocated AS (
        SELECT *, COALESCE(payable_weight, SAFE_DIVIDE(1, booking_count)) AS weight
        FROM booking_rows WHERE period IS NOT NULL
    ), variant_orders AS (
        SELECT DISTINCT combined_entity_id, tgid, variant_id, period, order_id
        FROM allocated
    ), order_credit AS (
        SELECT *, SAFE_DIVIDE(1, COUNT(*) OVER (
            PARTITION BY combined_entity_id, tgid, period, order_id
        )) AS credit
        FROM variant_orders
    ), order_totals AS (
        SELECT combined_entity_id, tgid, variant_id,
            SUM(IF(period = 'w0', credit, 0))  AS orders,
            SUM(IF(period = 'wm1', credit, 0)) AS orders_wm1,
            SUM(IF(period = 'ly', credit, 0))  AS orders_ly
        FROM order_credit GROUP BY 1, 2, 3
    )
    SELECT
        a.combined_entity_id,
        a.tgid,
        a.variant_id,
        ANY_VALUE(a.variant_name) AS variant_name,
        SUM(IF(a.period = 'w0', a.amount_revenue_usd * a.weight, 0))  AS rev,
        SUM(IF(a.period = 'wm1', a.amount_revenue_usd * a.weight, 0)) AS rev_wm1,
        SUM(IF(a.period = 'ly', a.amount_revenue_usd * a.weight, 0))  AS rev_ly,
        o.orders, o.orders_wm1, o.orders_ly,
        SUM(IF(a.period = 'w0', a.order_value_usd * a.weight, 0))     AS gbv,
        SUM(IF(a.period = 'wm1', a.order_value_usd * a.weight, 0))    AS gbv_wm1,
        SUM(IF(a.period = 'ly', a.order_value_usd * a.weight, 0))     AS gbv_ly,
        SUM(IF(a.period = 'w0' AND a.order_status = 'Completed',
            a.order_value_usd * a.weight, 0))                         AS completed_gbv,
        SUM(IF(a.period = 'wm1' AND a.order_status = 'Completed',
            a.order_value_usd * a.weight, 0))                         AS completed_gbv_wm1,
        SUM(IF(a.period = 'ly' AND a.order_status = 'Completed',
            a.order_value_usd * a.weight, 0))                         AS completed_gbv_ly,
        SAFE_DIVIDE(COUNT(DISTINCT IF(a.period = 'w0' AND a.lead_time_days = 0,
            a.booking_id, NULL)), COUNT(DISTINCT IF(a.period = 'w0', a.booking_id, NULL))) AS lt_0d,
        SAFE_DIVIDE(COUNT(DISTINCT IF(a.period = 'w0' AND a.lead_time_days BETWEEN 1 AND 2,
            a.booking_id, NULL)), COUNT(DISTINCT IF(a.period = 'w0', a.booking_id, NULL))) AS lt_12d,
        SAFE_DIVIDE(COUNT(DISTINCT IF(a.period = 'w0' AND a.lead_time_days BETWEEN 3 AND 7,
            a.booking_id, NULL)), COUNT(DISTINCT IF(a.period = 'w0', a.booking_id, NULL))) AS lt_37d,
        SAFE_DIVIDE(COUNT(DISTINCT IF(a.period = 'w0' AND a.lead_time_days > 7,
            a.booking_id, NULL)), COUNT(DISTINCT IF(a.period = 'w0', a.booking_id, NULL))) AS lt_7p
    FROM allocated a
    JOIN order_totals o USING (combined_entity_id, tgid, variant_id)
    GROUP BY 1, 2, 3, o.orders, o.orders_wm1, o.orders_ly
    """.format(bookings=config.FCT_BOOKINGS, orders=config.FCT_ORDERS, mkt=mkt)
    params = {
        "w0_s": config.iso(w0_start), "w0_e": config.iso(w0_end),
        "wm1_s": config.iso(wm1_start), "wm1_e": config.iso(wm1_end),
        "ly_s": config.iso(ly_start), "ly_e": config.iso(ly_end),
    }
    if market:
        params["market"] = market
    return query_df(sql, "ce_variants", params)


def ce_tgid_funnel(
    ce_ids: list[str],
    w0_start: dt.date, w0_end: dt.date,
    wm1_start: dt.date, wm1_end: dt.date,
    ly_start: dt.date, ly_end: dt.date,
    max_bytes: int | None = None,
) -> pd.DataFrame:
    """TGID-grain funnel: select users, S2C, C2O for W0 + W-1 + LY."""
    if not ce_ids:
        return pd.DataFrame()
    sql = """
    SELECT
        combined_entity_id,
        CAST(experience_id AS STRING)                              AS tgid,

        COUNT(DISTINCT CASE WHEN event_date BETWEEN @w0_s AND @w0_e
            AND has_select_page_viewed THEN user_id END)           AS select_users,
        SAFE_DIVIDE(
            COUNT(DISTINCT CASE WHEN event_date BETWEEN @w0_s AND @w0_e
                AND has_checkout_started THEN user_id END),
            NULLIF(COUNT(DISTINCT CASE WHEN event_date BETWEEN @w0_s AND @w0_e
                AND has_select_page_viewed THEN user_id END), 0)
        )                                                          AS s2c,
        SAFE_DIVIDE(
            COUNT(DISTINCT CASE WHEN event_date BETWEEN @w0_s AND @w0_e
                AND has_order_completed THEN user_id END),
            NULLIF(COUNT(DISTINCT CASE WHEN event_date BETWEEN @w0_s AND @w0_e
                AND has_checkout_started THEN user_id END), 0)
        )                                                          AS c2o,

        SAFE_DIVIDE(
            COUNT(DISTINCT CASE WHEN event_date BETWEEN @wm1_s AND @wm1_e
                AND has_checkout_started THEN user_id END),
            NULLIF(COUNT(DISTINCT CASE WHEN event_date BETWEEN @wm1_s AND @wm1_e
                AND has_select_page_viewed THEN user_id END), 0)
        )                                                          AS s2c_wm1,
        SAFE_DIVIDE(
            COUNT(DISTINCT CASE WHEN event_date BETWEEN @wm1_s AND @wm1_e
                AND has_order_completed THEN user_id END),
            NULLIF(COUNT(DISTINCT CASE WHEN event_date BETWEEN @wm1_s AND @wm1_e
                AND has_checkout_started THEN user_id END), 0)
        )                                                          AS c2o_wm1,

        COUNT(DISTINCT CASE WHEN event_date BETWEEN @ly_s AND @ly_e
            AND has_select_page_viewed THEN user_id END)           AS select_users_ly,
        SAFE_DIVIDE(
            COUNT(DISTINCT CASE WHEN event_date BETWEEN @ly_s AND @ly_e
                AND has_checkout_started THEN user_id END),
            NULLIF(COUNT(DISTINCT CASE WHEN event_date BETWEEN @ly_s AND @ly_e
                AND has_select_page_viewed THEN user_id END), 0)
        )                                                          AS s2c_ly,
        SAFE_DIVIDE(
            COUNT(DISTINCT CASE WHEN event_date BETWEEN @ly_s AND @ly_e
                AND has_order_completed THEN user_id END),
            NULLIF(COUNT(DISTINCT CASE WHEN event_date BETWEEN @ly_s AND @ly_e
                AND has_checkout_started THEN user_id END), 0)
        )                                                          AS c2o_ly

    FROM {tbl}

    WHERE combined_entity_id IN UNNEST(@ce_ids)
          AND (advertising_channel_type IS NULL OR advertising_channel_type != 'PERFORMANCE_MAX')
          AND (event_date BETWEEN @w0_s AND @w0_e
               OR event_date BETWEEN @wm1_s AND @wm1_e
               OR event_date BETWEEN @ly_s AND @ly_e)

    GROUP BY 1, 2
    HAVING COUNT(DISTINCT CASE WHEN event_date BETWEEN @w0_s AND @w0_e
               AND has_select_page_viewed THEN user_id END) > 0
    """.format(tbl=config.MIXPANEL_FUNNEL)
    return query_df(
        sql, "ce_tgid_funnel",
        {
            "ce_ids": [str(c) for c in ce_ids],
            "w0_s": config.iso(w0_start), "w0_e": config.iso(w0_end),
            "wm1_s": config.iso(wm1_start), "wm1_e": config.iso(wm1_end),
            "ly_s": config.iso(ly_start), "ly_e": config.iso(ly_end),
        },
        max_bytes=max_bytes,
    )


def ce_tgid_leadtime(
    market: str | None,
    w0_start: dt.date, w0_end: dt.date,
    wm1_start: dt.date, wm1_end: dt.date,
) -> pd.DataFrame:
    """TGID-grain lead-time band shares for W0 + W-1 (pct within each window)."""
    mkt = "AND business_market = @market" if market else ""
    sql = """
    WITH bookings AS (
        SELECT
            combined_entity_id,
            CAST(experience_id AS STRING)       AS tgid,
            CASE
                WHEN lead_time_days BETWEEN 0 AND 2 THEN '0-2D'
                WHEN lead_time_days BETWEEN 3 AND 7 THEN '3-7D'
                WHEN lead_time_days > 7              THEN '7D+'
            END                                     AS band,
            CASE
                WHEN DATE(date_created_at_et) BETWEEN @w0_s AND @w0_e   THEN 'w0'
                WHEN DATE(date_created_at_et) BETWEEN @wm1_s AND @wm1_e THEN 'wm1'
            END                                     AS period,
            booking_id
        FROM {tbl}
        WHERE DATE(date_created_at_et) BETWEEN @wm1_s AND @w0_e
              {mkt}
              AND lead_time_days IS NOT NULL
              AND lead_time_days >= 0
    ),
    filtered AS (SELECT * FROM bookings WHERE period IS NOT NULL),
    tgid_totals AS (
        SELECT combined_entity_id, tgid, period, COUNT(DISTINCT booking_id) AS total
        FROM filtered GROUP BY 1, 2, 3
    ),
    banded AS (
        SELECT combined_entity_id, tgid, band, period, COUNT(DISTINCT booking_id) AS cnt
        FROM filtered WHERE band IS NOT NULL GROUP BY 1, 2, 3, 4
    )
    SELECT b.combined_entity_id, b.tgid, b.band,
        MAX(IF(b.period = 'w0',  SAFE_DIVIDE(b.cnt, t.total), NULL)) AS pct,
        MAX(IF(b.period = 'wm1', SAFE_DIVIDE(b.cnt, t.total), NULL)) AS pct_wm1
    FROM banded b JOIN tgid_totals t USING (combined_entity_id, tgid, period)
    GROUP BY 1, 2, 3
    """.format(tbl=config.FCT_BOOKINGS, mkt=mkt)
    params = {
        "w0_s": config.iso(w0_start), "w0_e": config.iso(w0_end),
        "wm1_s": config.iso(wm1_start), "wm1_e": config.iso(wm1_end),
    }
    if market:
        params["market"] = market
    return query_df(sql, "ce_tgid_leadtime", params)


def ce_leadtime(
    market: str | None,
    w0_start: dt.date, w0_end: dt.date,
    wm1_start: dt.date, wm1_end: dt.date,
    ly_start: dt.date, ly_end: dt.date,
) -> pd.DataFrame:
    """Bookings/economics by five lead-time bands for W0 / W-1 / LY."""
    mkt = "AND business_market = @market" if market else ""
    sql = """
    SELECT
        combined_entity_id,
        CASE
            WHEN lead_time_days = 0             THEN '0D'
            WHEN lead_time_days BETWEEN 1 AND 2 THEN '1-2D'
            WHEN lead_time_days BETWEEN 3 AND 4 THEN '3-4D'
            WHEN lead_time_days BETWEEN 5 AND 7 THEN '5-7D'
            WHEN lead_time_days > 7           THEN '7D+'
        END                                 AS band,
        COUNT(DISTINCT IF(DATE(date_created_at_et) BETWEEN @w0_s AND @w0_e,
            booking_id, NULL))              AS bookings,
        COUNT(DISTINCT IF(DATE(date_created_at_et) BETWEEN @wm1_s AND @wm1_e,
            booking_id, NULL))              AS bookings_wm1,
        COUNT(DISTINCT IF(DATE(date_created_at_et) BETWEEN @ly_s AND @ly_e,
            booking_id, NULL))              AS bookings_ly,
        SUM(IF(DATE(date_created_at_et) BETWEEN @w0_s AND @w0_e,
            price_net_usd, 0))              AS rev,
        SUM(IF(DATE(date_created_at_et) BETWEEN @wm1_s AND @wm1_e,
            price_net_usd, 0))              AS rev_wm1,
        SUM(IF(DATE(date_created_at_et) BETWEEN @ly_s AND @ly_e,
            price_net_usd, 0))              AS rev_ly,
        SUM(IF(DATE(date_created_at_et) BETWEEN @w0_s AND @w0_e,
            price_payable_usd, 0))          AS order_value,
        SUM(IF(DATE(date_created_at_et) BETWEEN @wm1_s AND @wm1_e,
            price_payable_usd, 0))          AS order_value_wm1,
        SUM(IF(DATE(date_created_at_et) BETWEEN @ly_s AND @ly_e,
            price_payable_usd, 0))          AS order_value_ly

    FROM {tbl}

    WHERE (DATE(date_created_at_et) BETWEEN @wm1_s AND @w0_e
           OR DATE(date_created_at_et) BETWEEN @ly_s AND @ly_e)
          {mkt}
          AND lead_time_days IS NOT NULL
          AND lead_time_days >= 0

    GROUP BY 1, 2
    """.format(tbl=config.FCT_BOOKINGS, mkt=mkt)
    params = {
        "w0_s": config.iso(w0_start), "w0_e": config.iso(w0_end),
        "wm1_s": config.iso(wm1_start), "wm1_e": config.iso(wm1_end),
        "ly_s": config.iso(ly_start), "ly_e": config.iso(ly_end),
    }
    if market:
        params["market"] = market
    return query_df(sql, "ce_leadtime", params)


def ce_countries(
    market: str | None,
    w0_start: dt.date, w0_end: dt.date,
    wm1_start: dt.date, wm1_end: dt.date,
    ly_start: dt.date, ly_end: dt.date,
) -> pd.DataFrame:
    """Orders/revenue/AOV by customer country for W0 / W-1 / LY."""
    mkt = "AND business_market = @market" if market else ""
    sql = """
    SELECT
        combined_entity_id,
        card_issuing_country                AS country,
        COUNT(DISTINCT IF(DATE(created_at) BETWEEN @w0_s AND @w0_e,
            order_id, NULL))                AS orders,
        COUNT(DISTINCT IF(DATE(created_at) BETWEEN @wm1_s AND @wm1_e,
            order_id, NULL))                AS orders_wm1,
        COUNT(DISTINCT IF(DATE(created_at) BETWEEN @ly_s AND @ly_e,
            order_id, NULL))                AS orders_ly,
        SUM(IF(DATE(created_at) BETWEEN @w0_s AND @w0_e,
            amount_revenue_usd, 0))         AS rev,
        SUM(IF(DATE(created_at) BETWEEN @wm1_s AND @wm1_e,
            amount_revenue_usd, 0))         AS rev_wm1,
        SUM(IF(DATE(created_at) BETWEEN @ly_s AND @ly_e,
            amount_revenue_usd, 0))         AS rev_ly,
        SUM(IF(DATE(created_at) BETWEEN @w0_s AND @w0_e,
            order_value_usd, 0))            AS order_value,
        SUM(IF(DATE(created_at) BETWEEN @wm1_s AND @wm1_e,
            order_value_usd, 0))            AS order_value_wm1,
        SUM(IF(DATE(created_at) BETWEEN @ly_s AND @ly_e,
            order_value_usd, 0))            AS order_value_ly

    FROM {tbl}

    WHERE (DATE(created_at) BETWEEN @wm1_s AND @w0_e
           OR DATE(created_at) BETWEEN @ly_s AND @ly_e)
          {mkt}
          AND order_status NOT IN ('Dummy', 'Cancelled - Fraudulent')
          AND user_type = 'Customer'
          AND card_issuing_country IS NOT NULL

    GROUP BY 1, 2
    """.format(tbl=config.FCT_ORDERS, mkt=mkt)
    params = {
        "w0_s": config.iso(w0_start), "w0_e": config.iso(w0_end),
        "wm1_s": config.iso(wm1_start), "wm1_e": config.iso(wm1_end),
        "ly_s": config.iso(ly_start), "ly_e": config.iso(ly_end),
    }
    if market:
        params["market"] = market
    return query_df(sql, "ce_countries", params)


# --------------------------------------------------------------------------- #
# RE-SOURCE tier (A2, "hard") — channel mix + funnel, ported to weekly grain
# --------------------------------------------------------------------------- #
# The two heavier drawer sections. Both compute three one-week windows in a
# single query — W0 (current), W-1 (WoW), LY (−364d weekday-aligned, YoY) — so
# the drawer can show current + WoW + YoY without extra round-trips.
#   • Channel mix: revenue by channel from fct_orders, using the CE-Health v6.1
#     channel-classification CASE verbatim (Google Search / Cross-sell / PMax /
#     Bing / TTD / CPR / Organic / Direct / etc.). Actuals revenue basis.
#   • Funnel (LP→order): CE-level LP Users / LP2S / S2C / C2O from the mixpanel
#     page-funnel table (COUNT(DISTINCT user_id), PMax excluded — matches
#     CE-Health). That table has no business_market, so it is batched by the
#     market's CE-id list.
def ce_channels(
    market: str | None,
    w0_start: dt.date, w0_end: dt.date,
    wm1_start: dt.date, wm1_end: dt.date,
    ly_start: dt.date, ly_end: dt.date,
) -> pd.DataFrame:
    """Revenue by channel per CE for W0 / W-1 / LY (actuals basis, fct_orders)."""
    mkt = "AND business_market = @market" if market else ""
    sql = """
    WITH classified AS (

        SELECT
            combined_entity_id,
            CASE
                WHEN channel_name = 'Google Ads'
                    AND REGEXP_CONTAINS(campaign_name, CONCAT('cid', CAST(combined_entity_id AS STRING)))
                    THEN 'Google Search'
                WHEN channel_name = 'Google Ads' AND campaign_name LIKE '1 - %'
                    THEN 'Bing'
                WHEN channel_name = 'Bing Ads'
                    AND REGEXP_CONTAINS(campaign_name, CONCAT('cid', CAST(combined_entity_id AS STRING)))
                    THEN 'Bing'
                WHEN channel_name = 'Google Ads'
                    AND REGEXP_CONTAINS(LOWER(COALESCE(campaign_name, '')), r'pmax|performance.max')
                    THEN 'Google PMax'
                WHEN channel_name = 'Google Ads'                 THEN 'Google Cross-sell'
                WHEN channel_name = 'Bing Ads'                   THEN 'Bing Cross-sell'
                WHEN channel_name = 'Things to Do (Ads)'         THEN 'TTD (Paid)'
                WHEN channel_name = 'Things to Do (Organic)'     THEN 'TTD (Organic)'
                WHEN channel_name = 'Confirmation Page Recommendations' THEN 'CPR'
                WHEN channel_name = 'Organic Search'             THEN 'Organic'
                WHEN channel_grouping = 'Direct (App)'           THEN 'Direct (App)'
                WHEN channel_grouping = 'Direct'                 THEN 'Direct'
                WHEN channel_grouping = 'Affiliates'             THEN 'Affiliates'
                WHEN channel_grouping = 'Email'                  THEN 'Email'
                WHEN channel_grouping = 'Referral'               THEN 'Referral'
                ELSE 'Other'
            END                                                  AS channel,
            CASE
                WHEN DATE(created_at) BETWEEN @w0_s AND @w0_e   THEN 'w0'
                WHEN DATE(created_at) BETWEEN @wm1_s AND @wm1_e THEN 'wm1'
                WHEN DATE(created_at) BETWEEN @ly_s AND @ly_e   THEN 'ly'
            END                                                  AS period,
            amount_revenue_usd                                   AS revenue

        FROM {tbl}

        WHERE (DATE(created_at) BETWEEN @w0_s AND @w0_e
                   OR DATE(created_at) BETWEEN @wm1_s AND @wm1_e
                   OR DATE(created_at) BETWEEN @ly_s AND @ly_e)
              {mkt}
              AND order_status NOT IN ('Dummy', 'Cancelled - Fraudulent')
              AND user_type = 'Customer'

    )

    SELECT
        combined_entity_id,
        channel,
        period,
        SUM(revenue)    AS rev

    FROM classified

    WHERE period IS NOT NULL

    GROUP BY 1, 2, 3
    """.format(tbl=config.FCT_ORDERS, mkt=mkt)
    params = {
        "w0_s": config.iso(w0_start), "w0_e": config.iso(w0_end),
        "wm1_s": config.iso(wm1_start), "wm1_e": config.iso(wm1_end),
        "ly_s": config.iso(ly_start), "ly_e": config.iso(ly_end),
    }
    if market:
        params["market"] = market
    return query_df(sql, "ce_channels", params)


def ce_funnel(
    ce_ids: list[str],
    w0_start: dt.date, w0_end: dt.date,
    wm1_start: dt.date, wm1_end: dt.date,
    ly_start: dt.date, ly_end: dt.date,
    max_bytes: int | None = None,
) -> pd.DataFrame:
    """CE-level LP→order funnel for W0 / W-1 / LY (mixpanel page-funnel table)."""
    if not ce_ids:
        return pd.DataFrame()
    sql = """
    WITH base AS (

        SELECT
            combined_entity_id,
            CASE
                WHEN event_date BETWEEN @w0_s AND @w0_e   THEN 'w0'
                WHEN event_date BETWEEN @wm1_s AND @wm1_e THEN 'wm1'
                WHEN event_date BETWEEN @ly_s AND @ly_e   THEN 'ly'
            END                             AS period,
            user_id,
            has_select_page_viewed,
            has_checkout_started,
            has_order_completed

        FROM {tbl}

        WHERE combined_entity_id IN UNNEST(@ce_ids)
              AND (advertising_channel_type IS NULL OR advertising_channel_type != 'PERFORMANCE_MAX')
              AND (event_date BETWEEN @w0_s AND @w0_e
                   OR event_date BETWEEN @wm1_s AND @wm1_e
                   OR event_date BETWEEN @ly_s AND @ly_e)

    )

    SELECT
        combined_entity_id,
        period,
        COUNT(DISTINCT user_id)                                                   AS lp_users,
        100 * SAFE_DIVIDE(
            COUNT(DISTINCT IF(has_select_page_viewed, user_id, NULL)),
            COUNT(DISTINCT user_id))                                              AS lp2s,
        100 * SAFE_DIVIDE(
            COUNT(DISTINCT IF(has_checkout_started, user_id, NULL)),
            COUNT(DISTINCT IF(has_select_page_viewed, user_id, NULL)))            AS s2c,
        100 * SAFE_DIVIDE(
            COUNT(DISTINCT IF(has_order_completed, user_id, NULL)),
            COUNT(DISTINCT IF(has_checkout_started, user_id, NULL)))              AS c2o

    FROM base

    WHERE period IS NOT NULL

    GROUP BY 1, 2
    """.format(tbl=config.MIXPANEL_FUNNEL)
    return query_df(
        sql, "ce_funnel",
        {
            "ce_ids": [str(c) for c in ce_ids],
            "w0_s": config.iso(w0_start), "w0_e": config.iso(w0_end),
            "wm1_s": config.iso(wm1_start), "wm1_e": config.iso(wm1_end),
            "ly_s": config.iso(ly_start), "ly_e": config.iso(ly_end),
        },
        max_bytes=max_bytes,
    )


# --------------------------------------------------------------------------- #
# Weekly overall CVR series (Mixpanel page-funnel) — for the drawer Overall tab.
# Overall CVR = order-completed users ÷ LP users, all traffic, PMax excluded
# (matches the CE-Health funnel definition). Weekly grain for the 12-wk trend.
# --------------------------------------------------------------------------- #
def ce_weekly_funnel(ce_ids: list[str], start: dt.date, end: dt.date) -> pd.DataFrame:
    """Weekly LP users + order-completed users per CE (Mixpanel, PMax excluded)."""
    if not ce_ids:
        return pd.DataFrame()
    sql = """
    SELECT
        combined_entity_id,
        DATE_TRUNC(event_date, WEEK(SUNDAY))                        AS week,
        COUNT(DISTINCT user_id)                                     AS lp_users,
        COUNT(DISTINCT IF(has_order_completed, user_id, NULL))      AS order_users
    FROM {tbl}
    WHERE combined_entity_id IN UNNEST(@ce_ids)
          AND (advertising_channel_type IS NULL OR advertising_channel_type != 'PERFORMANCE_MAX')
          AND event_date BETWEEN @start AND @end
    GROUP BY 1, 2
    """.format(tbl=config.MIXPANEL_FUNNEL)
    return query_df(
        sql, "ce_weekly_funnel",
        {"ce_ids": [str(c) for c in ce_ids], "start": config.iso(start), "end": config.iso(end)},
    )


# --------------------------------------------------------------------------- #
# Daily paid series for the fluctuation engine  (CM1/conv POF)
# --------------------------------------------------------------------------- #
def ce_daily_ads(market: str | None, daily_start: dt.date, w0_end: dt.date) -> pd.DataFrame:
    """Daily CE paid series: CM1, CM1 conversions, clicks, spend (Google Search only)."""
    sql = f"""
    SELECT
        campaign_target_combined_entity_id                        AS combined_entity_id,
        ANY_VALUE(campaign_target_combined_entity_name)          AS combined_entity_name,
        report_date,
        SUM(CASE
            WHEN report_date >= '2025-09-01'
                 AND sum_conversion_value_offline_contribution_margin > 0
                THEN sum_conversion_value_offline_contribution_margin
            ELSE sum_conversion_value_calculated_contribution_margin
        END)                                                      AS cm1,
        SUM(CASE
            WHEN report_date >= '2025-09-01'
                 AND count_conversions_offline_contribution_margin > 0
                THEN count_conversions_offline_contribution_margin
            ELSE count_conversions_online
        END)                                                      AS conversions,
        SUM(count_clicks)                                        AS clicks,
        SUM(sum_spend)                                           AS spend

    FROM {config.ADS_STATS}

    WHERE report_date BETWEEN @start AND @end
          {'AND campaign_target_business_market = @market' if market else ''}
          AND ad_platform = 'Google Ads'
          AND campaign_advertising_channel_type = 'SEARCH'
          AND (account_name != 'Things To Do' OR account_name IS NULL)

    GROUP BY 1, 3
    """
    params = {"start": config.iso(daily_start), "end": config.iso(w0_end)}
    if market:
        params["market"] = market
    return query_df(sql, "ce_daily_ads", params)


# --------------------------------------------------------------------------- #
# Daily business series for the fluctuation engine  (RPC POF)
# --------------------------------------------------------------------------- #
def ce_daily_business(market: str | None, daily_start: dt.date, w0_end: dt.date) -> pd.DataFrame:
    """Daily CE business series: revenue (predicted), clicks, orders, GBV, completed GBV.
    GBV + completed enable the 3-day-vs-28-day driver breakdown (AOV/CR/TR) in the
    fluctuations bucket — RPC = CVR·AOV·CR·TR (2026-07-17)."""
    sql = f"""
    SELECT
        combined_entity_id,
        report_date,
        SUM({REV})                            AS revenue,
        SUM(count_ad_clicks)                  AS clicks,
        SUM(count_orders)                     AS orders,
        SUM(sum_order_value)                  AS gbv,
        SUM(sum_order_value_completed)        AS gbv_completed

    FROM {config.CE_STATS}

    WHERE report_date BETWEEN @start AND @end
          {'AND business_market = @market' if market else ''}

    GROUP BY 1, 2
    """
    params = {"start": config.iso(daily_start), "end": config.iso(w0_end)}
    if market:
        params["market"] = market
    return query_df(sql, "ce_daily_business", params)


def ce_daily_paid_google(market: str | None, daily_start: dt.date, w0_end: dt.date) -> pd.DataFrame:
    """Daily GOOGLE-SEARCH paid FUNNEL — single-source from ads_campaign_stats (2026-07-20 switch).
    Carries every field the RPC decomposition needs so the funnel no longer joins fct_orders:
        orders   = count_attributed_orders
        booked   = sum_conversion_value_offline_gross_bookings
        attr_value / attr_completed = sum_attributed_value / sum_attributed_value_completed
        revenue  = sum_conversion_value_offline_revenue
        clicks   = count_clicks
    Canonical Omni decomposition (reconciles to paid RPC = revenue/clicks):
        CVR = orders/clicks · AOV = booked/orders · CR = attr_completed/attr_value · TR = rev/(booked*CR)
    CR uses the attributed_value PAIR (same attribution base) → sane ≤100%, unlike completed/booked.
    Excludes the 'Things To Do' account (matches the canonical Omni query)."""
    sql = f"""
    SELECT
        campaign_target_combined_entity_id                        AS combined_entity_id,
        report_date,
        SUM(count_attributed_orders)                              AS orders,
        SUM(sum_conversion_value_offline_gross_bookings)          AS booked,
        SUM(sum_attributed_value)                                 AS attr_value,
        SUM(sum_attributed_value_completed)                       AS attr_completed,
        SUM(sum_conversion_value_offline_revenue)                 AS revenue,
        SUM(count_clicks)                                         AS clicks

    FROM {config.ADS_STATS}

    WHERE report_date BETWEEN @start AND @end
          {'AND campaign_target_business_market = @market' if market else ''}
          AND ad_platform = 'Google Ads'
          AND campaign_advertising_channel_type = 'SEARCH'
          AND (account_name != 'Things To Do' OR account_name IS NULL)

    GROUP BY 1, 2
    """
    params = {"start": config.iso(daily_start), "end": config.iso(w0_end)}
    if market:
        params["market"] = market
    return query_df(sql, "ce_daily_paid_google", params)


def ce_daily_orders_google(market: str | None, daily_start: dt.date, w0_end: dt.date) -> pd.DataFrame:
    """Daily GOOGLE-SEARCH paid ORDER funnel from fct_orders (2026-07-20): order-grounded
    booked / completed / net-revenue so the paid decomposition can separate Completion from
    Take-rate (the ad-attribution table can't — completed/booked >100%). ad_network filter =
    Google Search; valid_to IS NULL dedups to the current SCD2 version (1 row/order). Paired
    with ce_daily_paid_google clicks → CVR=orders/clicks · AOV=booked/orders · CR=completed/booked
    · TR=revenue/completed, reconciling to paid RPC = revenue/clicks."""
    sql = f"""
    SELECT
        combined_entity_id,
        DATE(created_at)                            AS report_date,
        COUNT(DISTINCT order_id)                    AS orders,
        SUM(order_value_usd)                        AS booked,
        SUM(order_value_completed_usd)              AS completed,
        SUM(amount_revenue_usd)                     AS revenue

    FROM {config.FCT_ORDERS}

    WHERE DATE(created_at) BETWEEN @start AND @end
          {'AND business_market = @market' if market else ''}
          AND ad_network = 'Google: Search'
          AND valid_to_timestamp IS NULL

    GROUP BY 1, 2
    """
    params = {"start": config.iso(daily_start), "end": config.iso(w0_end)}
    if market:
        params["market"] = market
    return query_df(sql, "ce_daily_orders_google", params)


# --------------------------------------------------------------------------- #
# tROAS history for the bid-change innocence check
# --------------------------------------------------------------------------- #
def troas_history(market: str | None, start: dt.date, w0_end: dt.date) -> pd.DataFrame:
    """
    Per-campaign as-of tROAS + spend over the window (Google Search + Bing).
    Uses campaign_target_roas (as-of report_date) so day-over-day changes are
    detectable; the current_* variant is constant across dates. tROAS is stored
    in percentage points (150 == 150%).
    """
    sql = f"""
    SELECT
        campaign_id,
        campaign_target_combined_entity_id      AS combined_entity_id,
        report_date,
        campaign_target_roas                    AS troas,
        current_campaign_target_roas            AS troas_current,
        current_campaign_bidding_strategy       AS strategy,
        sum_spend                               AS spend

    FROM {config.ADS_STATS}

    WHERE report_date BETWEEN @start AND @end
          {'AND campaign_target_business_market = @market' if market else ''}
          AND ad_platform IN ('Google Ads', 'Microsoft Ads')
          AND campaign_advertising_channel_type = 'SEARCH'

    ORDER BY campaign_id, report_date
    """
    params = {"start": config.iso(start), "end": config.iso(w0_end)}
    if market:
        params["market"] = market
    return query_df(sql, "troas_history", params)


# --------------------------------------------------------------------------- #
# Availability signal (best-effort; limited to a CE shortlist)
# --------------------------------------------------------------------------- #
def availability_signal(
    ce_ids: list[str], baseline_start: dt.date, w0_start: dt.date, w0_end: dt.date
) -> pd.DataFrame:
    """
    Sold-out rate in W0 vs the preceding baseline for a shortlist of CEs.
    tour_id -> CE mapping via fct_bookings. Returns empty on any failure — this
    is an evidence enrichment, not a core metric (matched the reference's n/a).
    """
    if not ce_ids:
        return pd.DataFrame()
    sql = f"""
    WITH tour_ce AS (

        SELECT DISTINCT
            CAST(tour_id AS STRING)     AS tour_id,
            combined_entity_id

        FROM {config.FCT_BOOKINGS}

        WHERE combined_entity_id IN UNNEST(@ce_ids)
              AND tour_id IS NOT NULL

    ),

    avail AS (

        SELECT
            CAST(tour_id AS STRING)     AS tour_id,
            extracted_date,
            SAFE_DIVIDE(
                COUNTIF(total_remaining = 0 AND count_limited_time_slots > 0),
                COUNT(*)
            )                           AS sold_out_rate

        FROM {config.INV_AVAIL}

        WHERE extracted_date BETWEEN @baseline_start AND @w0_end
              AND experience_date BETWEEN extracted_date
                  AND DATE_ADD(extracted_date, INTERVAL 14 DAY)

        GROUP BY 1, 2

    )

    SELECT
        tour_ce.combined_entity_id,
        AVG(IF(avail.extracted_date >= @w0_start, avail.sold_out_rate, NULL)) AS soldout_w0,
        AVG(IF(avail.extracted_date <  @w0_start, avail.sold_out_rate, NULL)) AS soldout_baseline

    FROM avail
    JOIN tour_ce USING (tour_id)

    GROUP BY 1
    """
    try:
        return query_df(
            sql, "availability_signal",
            {
                "ce_ids": [str(c) for c in ce_ids],
                "baseline_start": config.iso(baseline_start),
                "w0_start": config.iso(w0_start),
                "w0_end": config.iso(w0_end),
            },
        )
    except Exception as exc:  # noqa: BLE001 — enrichment must never break the build
        print(f"  [availability] signal unavailable, degrading to null: {exc}")
        return pd.DataFrame()
