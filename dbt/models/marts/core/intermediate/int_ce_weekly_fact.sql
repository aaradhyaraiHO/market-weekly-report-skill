{{
    config(
        materialized='table',
        tags=["refresh_schedule=weekly", "pii=false"],
        labels={'contains_pii': 'false', 'refresh_schedule': 'weekly'},
        persist_docs={'relation': true, 'columns': true},
        schema='intermediate'
    )
}}

/* Weekly backbone for the CE weekly system: one row per combined entity per
   ISO (Monday-start) week, carrying revenue, the funnel inputs (GBV / orders),
   the paid funnel (clicks / spend / conversions), and competition.

   Week grain is WEEK(MONDAY) to match competitor_weekly_stats and
   int_ce_weekly_funnel. Revenue is recomputed by summing daily sum_revenue over
   the Monday-Sunday week (the pre-rolled sum_weekly_revenue_value column on
   combined_entity_stats is Sunday-based, so it is NOT used here; it can serve as
   a Sunday-week cross-check only). The current in-progress week is excluded.

   Ratios (RPC, CPC, ROI, CVR, AOV, take rate, completion) are computed from the
   weekly sums, never averaged from daily ratios. */

WITH ce_daily AS (

    SELECT
        combined_entity_id,
        combined_entity_name,
        business_market,
        country,
        city,
        business_region,
        first_order_date,
        days_since_created,
        DATE_TRUNC(report_date, WEEK(MONDAY)) AS week_start_date,
        sum_revenue,
        sum_order_value_completed,
        count_orders,
        count_completed_orders,
        count_ad_clicks,
        count_ad_impressions,
        count_ad_conversions,
        sum_google_ads_spend,
        sum_microsoft_ads_spend,
        sum_facebook_ads_spend,
        sum_pmax_ads_spend,
        sum_google_ads_conversion_value

    FROM {{ ref('combined_entity_stats') }}

    WHERE report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 78 WEEK)
        AND report_date < DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY))

),

ce_weekly AS (

    SELECT
        combined_entity_id,
        week_start_date,
        ANY_VALUE(combined_entity_name) AS combined_entity_name,
        ANY_VALUE(business_market) AS business_market,
        ANY_VALUE(country) AS country,
        ANY_VALUE(city) AS city,
        ANY_VALUE(business_region) AS business_region,
        MIN(first_order_date) AS first_order_date,
        MAX(days_since_created) AS days_since_created,
        SUM(sum_revenue) AS sum_revenue,
        SUM(sum_order_value_completed) AS sum_gross_bookings,
        SUM(count_orders) AS count_orders,
        SUM(count_completed_orders) AS count_completed_orders,
        SUM(count_ad_clicks) AS count_paid_clicks,
        SUM(count_ad_impressions) AS count_ad_impressions,
        SUM(count_ad_conversions) AS count_ad_conversions,
        SUM(sum_google_ads_spend) AS sum_google_ads_spend,
        SUM(sum_google_ads_spend + sum_microsoft_ads_spend + sum_facebook_ads_spend + sum_pmax_ads_spend) AS sum_total_ads_spend,
        SUM(sum_google_ads_conversion_value) AS sum_google_ads_conversion_value

    FROM ce_daily

    GROUP BY 1, 2

),

competition_weekly AS (

    SELECT
        combined_entity_id,
        week AS week_start_date,
        COUNT(DISTINCT competitor_name) AS count_competitors,
        SUM(weekly_gbv) AS sum_competitor_gbv,
        SUM(weekly_bookings) AS count_competitor_bookings,
        SUM(weekly_reviews) AS count_competitor_reviews,
        ANY_VALUE(headout_weekly_gbv) AS sum_ho_competition_gbv,
        ANY_VALUE(headout_weekly_orders) AS count_ho_competition_orders,
        ANY_VALUE(headout_weekly_experiences) AS count_ho_competition_experiences,
        ANY_VALUE(trailing_4_week_gbv) AS sum_competitor_trailing_4w_gbv

    FROM {{ ref('competitor_weekly_stats') }}

    WHERE week >= DATE_SUB(CURRENT_DATE(), INTERVAL 78 WEEK)
        AND week < DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY))

    GROUP BY 1, 2

),

joined AS (

    SELECT
        ce_weekly.combined_entity_id,
        ce_weekly.week_start_date,
        ce_weekly.combined_entity_name,
        ce_weekly.business_market,
        ce_weekly.country,
        ce_weekly.city,
        ce_weekly.business_region,
        ce_weekly.first_order_date,
        ce_weekly.days_since_created,
        DATE_DIFF(ce_weekly.week_start_date, ce_weekly.first_order_date, WEEK) AS weeks_since_launch,

        -- Revenue + funnel inputs (weekly sums)
        ce_weekly.sum_revenue,
        ce_weekly.sum_gross_bookings,
        ce_weekly.count_orders,
        ce_weekly.count_completed_orders,

        -- Paid funnel (weekly sums)
        ce_weekly.count_paid_clicks,
        ce_weekly.count_ad_impressions,
        ce_weekly.count_ad_conversions,
        ce_weekly.sum_google_ads_spend,
        ce_weekly.sum_total_ads_spend,
        ce_weekly.sum_google_ads_conversion_value,

        -- Derived weekly ratios (computed from sums, not averaged)
        SAFE_DIVIDE(ce_weekly.sum_revenue, ce_weekly.count_paid_clicks) AS revenue_per_click,
        SAFE_DIVIDE(ce_weekly.sum_google_ads_spend, ce_weekly.count_paid_clicks) AS cost_per_click,
        SAFE_DIVIDE(ce_weekly.sum_revenue, ce_weekly.sum_google_ads_spend) * 100 AS paid_roi_pct,
        SAFE_DIVIDE(ce_weekly.count_orders, ce_weekly.count_paid_clicks) AS paid_cvr,
        SAFE_DIVIDE(ce_weekly.sum_gross_bookings, ce_weekly.count_orders) AS aov,
        SAFE_DIVIDE(ce_weekly.sum_revenue, ce_weekly.sum_gross_bookings) AS take_rate,
        SAFE_DIVIDE(ce_weekly.count_completed_orders, ce_weekly.count_orders) AS completion_rate,

        -- Competition (LEFT joined; only mapped CEs have rows)
        competition_weekly.count_competitors,
        competition_weekly.sum_competitor_gbv,
        competition_weekly.count_competitor_bookings,
        competition_weekly.count_competitor_reviews,
        competition_weekly.sum_ho_competition_gbv,
        competition_weekly.count_ho_competition_orders,
        competition_weekly.count_ho_competition_experiences,
        competition_weekly.sum_competitor_trailing_4w_gbv,
        SAFE_DIVIDE(ce_weekly.sum_gross_bookings, competition_weekly.sum_competitor_gbv) * 100 AS ho_to_competitor_gbv_pct

    FROM ce_weekly
    LEFT JOIN competition_weekly
        ON ce_weekly.combined_entity_id = competition_weekly.combined_entity_id
        AND ce_weekly.week_start_date = competition_weekly.week_start_date

)

SELECT * FROM joined
