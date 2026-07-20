-- ============================================================================
-- Weekly Revenue & CVR Drop Alert — CE-level Pre/Post metrics (v2)
--
-- Adds, vs v1:
--   - Paid / Organic traffic split
--   - Channel mix for paid (Google Ads, Microsoft Ads, Other Paid)
--   - Funnel step counts (select_page_viewed, checkout_started)
-- ============================================================================

WITH date_windows AS (

    SELECT
        -- Current comparison: previous complete Mon–Sun week vs the one before it
        DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)) - INTERVAL 2 WEEK                     AS pre_start,
        DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)) - INTERVAL 1 WEEK - INTERVAL 1 DAY    AS pre_end,
        DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)) - INTERVAL 1 WEEK                     AS post_start,
        DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)) - INTERVAL 1 DAY                      AS post_end,

        -- L4W: 4 complete Mon–Sun weeks immediately before Pre week (clean baseline)
        DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)) - INTERVAL 6 WEEK                     AS l4w_start,
        DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)) - INTERVAL 2 WEEK - INTERVAL 1 DAY    AS l4w_end,

        -- LY same week: 52-week shift (364 days) preserves Mon–Sun alignment
        DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)) - INTERVAL 54 WEEK                    AS ly_pre_start,
        DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)) - INTERVAL 53 WEEK - INTERVAL 1 DAY   AS ly_pre_end,
        DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)) - INTERVAL 53 WEEK                    AS ly_post_start,
        DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY)) - INTERVAL 52 WEEK - INTERVAL 1 DAY   AS ly_post_end

),

ce_revenue_raw AS (

    SELECT
        TRIM(combined_entity_id) AS combined_entity_id,
        CASE
            WHEN DATE(report_timestamp) BETWEEN (SELECT pre_start  FROM date_windows) AND (SELECT pre_end  FROM date_windows) THEN 'Pre'
            WHEN DATE(report_timestamp) BETWEEN (SELECT post_start FROM date_windows) AND (SELECT post_end FROM date_windows) THEN 'Post'
        END AS time_period,
        SUM(sum_revenue) AS revenue,
        SUM(count_orders) AS count_orders,
        SUM(sum_order_value) AS gross_bookings,
        SUM(sum_order_value_completed) AS gross_bookings_completed

    FROM `headout-analytics.analytics_reporting.combined_entity_stats`

    WHERE (
            DATE(report_timestamp) BETWEEN (SELECT pre_start  FROM date_windows) AND (SELECT pre_end  FROM date_windows)
            OR DATE(report_timestamp) BETWEEN (SELECT post_start FROM date_windows) AND (SELECT post_end FROM date_windows)
        )
        AND combined_entity_id IS NOT NULL
        AND combined_entity_id NOT LIKE 'Others - %'

    GROUP BY 1, 2

),

ce_revenue_pivoted AS (

    SELECT
        combined_entity_id,
        SUM(IF(time_period = 'Pre',  revenue, 0))                  AS pre_revenue,
        SUM(IF(time_period = 'Post', revenue, 0))                  AS post_revenue,
        SUM(IF(time_period = 'Pre',  count_orders, 0))             AS pre_count_orders,
        SUM(IF(time_period = 'Post', count_orders, 0))             AS post_count_orders,
        SUM(IF(time_period = 'Pre',  gross_bookings, 0))           AS pre_gross_bookings,
        SUM(IF(time_period = 'Post', gross_bookings, 0))           AS post_gross_bookings,
        SUM(IF(time_period = 'Pre',  gross_bookings_completed, 0)) AS pre_gross_bookings_completed,
        SUM(IF(time_period = 'Post', gross_bookings_completed, 0)) AS post_gross_bookings_completed

    FROM ce_revenue_raw

    WHERE time_period IS NOT NULL

    GROUP BY 1

),

eligible_ces AS (

    -- Hard global floor: filter out truly trivial CEs.
    -- Per-market floors (e.g., $1,500 for Italy, $250 for UAE) are applied in Python,
    -- so they can be tuned without changing SQL. See MARKET_FLOORS in revenue_drop_alert.py.
    SELECT *
    FROM ce_revenue_pivoted
    WHERE pre_revenue >= 100

),

funnel_raw AS (

    SELECT
        combined_entity_id,
        CASE
            WHEN event_date BETWEEN (SELECT pre_start  FROM date_windows) AND (SELECT pre_end  FROM date_windows) THEN 'Pre'
            WHEN event_date BETWEEN (SELECT post_start FROM date_windows) AND (SELECT post_end FROM date_windows) THEN 'Post'
        END AS time_period,

        -- Channel buckets
        CASE
            WHEN advertising_channel_type = 'Others' OR advertising_channel_type IS NULL THEN 'organic'
            WHEN channel_name = 'Google Ads'    THEN 'paid_google'
            WHEN channel_name = 'Microsoft Ads' THEN 'paid_microsoft'
            ELSE                                     'paid_other'
        END AS channel_bucket,

        user_id,
        has_select_page_viewed,
        select_page_viewed_timestamp,
        has_checkout_started,
        checkout_started_timestamp,
        has_order_completed,
        order_completed_timestamp,
        session_start_timestamp

    FROM `headout-analytics.analytics_reporting.mixpanel_user_page_funnel_progression`

    -- Filters mirror Omni's CE dashboard (the source of truth for GMs):
    --   - Exclude PERFORMANCE_MAX  (dashboard-level filter in Omni)
    --   - 30-day funnel completion window  (applied per-step in our SELECT — close
    --     enough to Omni's funnel_completion_days <= 30 filter)
    --   - NO page_type filter — Omni does not restrict by page type, so we don't either
    WHERE (advertising_channel_type <> 'PERFORMANCE_MAX' OR advertising_channel_type IS NULL)
        AND (
            event_date BETWEEN (SELECT pre_start  FROM date_windows) AND (SELECT pre_end  FROM date_windows)
            OR event_date BETWEEN (SELECT post_start FROM date_windows) AND (SELECT post_end FROM date_windows)
        )
        AND combined_entity_id IN (SELECT combined_entity_id FROM eligible_ces)

),

funnel_aggregated AS (

    SELECT
        combined_entity_id,
        time_period,

        -- Total traffic
        COUNT(DISTINCT user_id) AS overall_traffic,

        -- Paid / Organic split
        COUNT(DISTINCT IF(channel_bucket <> 'organic', user_id, NULL)) AS traffic_paid,
        COUNT(DISTINCT IF(channel_bucket = 'organic', user_id, NULL))  AS traffic_organic,

        -- Channel mix (paid only)
        COUNT(DISTINCT IF(channel_bucket = 'paid_google',    user_id, NULL)) AS traffic_google,
        COUNT(DISTINCT IF(channel_bucket = 'paid_microsoft', user_id, NULL)) AS traffic_microsoft,
        COUNT(DISTINCT IF(channel_bucket = 'paid_other',     user_id, NULL)) AS traffic_paid_other,

        -- Funnel steps (with 30-day completion window)
        COUNT(DISTINCT IF(
            has_select_page_viewed
                AND DATE_DIFF(select_page_viewed_timestamp, session_start_timestamp, DAY) <= 30,
            user_id, NULL
        )) AS users_select_page_viewed,

        COUNT(DISTINCT IF(
            has_checkout_started
                AND DATE_DIFF(checkout_started_timestamp, session_start_timestamp, DAY) <= 30,
            user_id, NULL
        )) AS users_checkout_started,

        COUNT(DISTINCT IF(
            has_order_completed
                AND DATE_DIFF(order_completed_timestamp, session_start_timestamp, DAY) <= 30,
            user_id, NULL
        )) AS users_order_completed

    FROM funnel_raw
    WHERE time_period IS NOT NULL
    GROUP BY 1, 2

),

funnel_pivoted AS (

    SELECT
        combined_entity_id,

        SUM(IF(time_period = 'Pre',  overall_traffic, 0))   AS pre_traffic,
        SUM(IF(time_period = 'Post', overall_traffic, 0))   AS post_traffic,

        SUM(IF(time_period = 'Pre',  traffic_paid, 0))      AS pre_traffic_paid,
        SUM(IF(time_period = 'Post', traffic_paid, 0))      AS post_traffic_paid,
        SUM(IF(time_period = 'Pre',  traffic_organic, 0))   AS pre_traffic_organic,
        SUM(IF(time_period = 'Post', traffic_organic, 0))   AS post_traffic_organic,

        SUM(IF(time_period = 'Pre',  traffic_google, 0))    AS pre_traffic_google,
        SUM(IF(time_period = 'Post', traffic_google, 0))    AS post_traffic_google,
        SUM(IF(time_period = 'Pre',  traffic_microsoft, 0)) AS pre_traffic_microsoft,
        SUM(IF(time_period = 'Post', traffic_microsoft, 0)) AS post_traffic_microsoft,
        SUM(IF(time_period = 'Pre',  traffic_paid_other, 0)) AS pre_traffic_paid_other,
        SUM(IF(time_period = 'Post', traffic_paid_other, 0)) AS post_traffic_paid_other,

        SUM(IF(time_period = 'Pre',  users_select_page_viewed, 0)) AS pre_users_select_page_viewed,
        SUM(IF(time_period = 'Post', users_select_page_viewed, 0)) AS post_users_select_page_viewed,
        SUM(IF(time_period = 'Pre',  users_checkout_started, 0))   AS pre_users_checkout_started,
        SUM(IF(time_period = 'Post', users_checkout_started, 0))   AS post_users_checkout_started,
        SUM(IF(time_period = 'Pre',  users_order_completed, 0))    AS pre_users_order_completed,
        SUM(IF(time_period = 'Post', users_order_completed, 0))    AS post_users_order_completed

    FROM funnel_aggregated
    GROUP BY 1

),

ce_metadata AS (

    SELECT
        combined_entity_id,
        combined_entity_name,
        market,
        country

    FROM `headout-analytics.analytics_reporting.dim_combined_entities`

),

-- ============================================================================
-- LONG-TERM CONTEXT — L4W average and LY same-week values
-- Used in the thread reply to give GMs seasonal/baseline context
-- ============================================================================

-- L4W: revenue + order/booking components across the 4 weeks before Pre week.
-- Components feed the full YoY driver matrix (AOV, Completion, Take Rate, etc.)
-- in the Long-term Context table.
l4w_revenue AS (

    SELECT
        TRIM(combined_entity_id) AS combined_entity_id,
        SUM(sum_revenue) AS l4w_total_revenue,
        SUM(count_orders) AS l4w_count_orders,
        SUM(sum_order_value) AS l4w_gross_bookings,
        SUM(sum_order_value_completed) AS l4w_gross_bookings_completed

    FROM `headout-analytics.analytics_reporting.combined_entity_stats`

    WHERE DATE(report_timestamp) BETWEEN (SELECT l4w_start FROM date_windows)
                                     AND (SELECT l4w_end   FROM date_windows)
        AND combined_entity_id IS NOT NULL
        AND combined_entity_id NOT LIKE 'Others - %'

    GROUP BY 1

),

-- L4W: traffic + converters for pooled CVR over the 4 weeks
l4w_funnel AS (

    SELECT
        TRIM(combined_entity_id) AS combined_entity_id,
        COUNT(DISTINCT user_id) AS l4w_traffic,
        COUNT(DISTINCT IF(
            has_order_completed
                AND DATE_DIFF(order_completed_timestamp, session_start_timestamp, DAY) <= 30,
            user_id, NULL
        )) AS l4w_converters

    FROM `headout-analytics.analytics_reporting.mixpanel_user_page_funnel_progression`

    WHERE (advertising_channel_type <> 'PERFORMANCE_MAX' OR advertising_channel_type IS NULL)
        AND event_date BETWEEN (SELECT l4w_start FROM date_windows)
                           AND (SELECT l4w_end   FROM date_windows)
        AND combined_entity_id IN (SELECT combined_entity_id FROM eligible_ces)

    GROUP BY 1

),

-- LY same-week revenue + order/booking components: separate Pre and Post
-- 1-year-shifted weeks. Components feed the full YoY driver matrix.
ly_revenue_raw AS (

    SELECT
        TRIM(combined_entity_id) AS combined_entity_id,
        CASE
            WHEN DATE(report_timestamp) BETWEEN (SELECT ly_pre_start  FROM date_windows) AND (SELECT ly_pre_end  FROM date_windows) THEN 'ly_pre'
            WHEN DATE(report_timestamp) BETWEEN (SELECT ly_post_start FROM date_windows) AND (SELECT ly_post_end FROM date_windows) THEN 'ly_post'
        END AS ly_period,
        SUM(sum_revenue) AS revenue,
        SUM(count_orders) AS count_orders,
        SUM(sum_order_value) AS gross_bookings,
        SUM(sum_order_value_completed) AS gross_bookings_completed

    FROM `headout-analytics.analytics_reporting.combined_entity_stats`

    WHERE (
            DATE(report_timestamp) BETWEEN (SELECT ly_pre_start  FROM date_windows) AND (SELECT ly_pre_end  FROM date_windows)
            OR DATE(report_timestamp) BETWEEN (SELECT ly_post_start FROM date_windows) AND (SELECT ly_post_end FROM date_windows)
        )
        AND combined_entity_id IS NOT NULL
        AND combined_entity_id NOT LIKE 'Others - %'

    GROUP BY 1, 2

),

ly_revenue_pivoted AS (

    SELECT
        combined_entity_id,
        SUM(IF(ly_period = 'ly_pre',  revenue, 0))                  AS ly_pre_revenue,
        SUM(IF(ly_period = 'ly_post', revenue, 0))                  AS ly_post_revenue,
        SUM(IF(ly_period = 'ly_pre',  count_orders, 0))             AS ly_pre_count_orders,
        SUM(IF(ly_period = 'ly_post', count_orders, 0))             AS ly_post_count_orders,
        SUM(IF(ly_period = 'ly_pre',  gross_bookings, 0))           AS ly_pre_gross_bookings,
        SUM(IF(ly_period = 'ly_post', gross_bookings, 0))           AS ly_post_gross_bookings,
        SUM(IF(ly_period = 'ly_pre',  gross_bookings_completed, 0)) AS ly_pre_gross_bookings_completed,
        SUM(IF(ly_period = 'ly_post', gross_bookings_completed, 0)) AS ly_post_gross_bookings_completed

    FROM ly_revenue_raw

    WHERE ly_period IS NOT NULL

    GROUP BY 1

),

-- LY same-week funnel: traffic + converters per LY week, pivoted for CVR
ly_funnel_raw AS (

    SELECT
        TRIM(combined_entity_id) AS combined_entity_id,
        CASE
            WHEN event_date BETWEEN (SELECT ly_pre_start  FROM date_windows) AND (SELECT ly_pre_end  FROM date_windows) THEN 'ly_pre'
            WHEN event_date BETWEEN (SELECT ly_post_start FROM date_windows) AND (SELECT ly_post_end FROM date_windows) THEN 'ly_post'
        END AS ly_period,
        user_id,
        has_order_completed,
        order_completed_timestamp,
        session_start_timestamp

    FROM `headout-analytics.analytics_reporting.mixpanel_user_page_funnel_progression`

    WHERE (advertising_channel_type <> 'PERFORMANCE_MAX' OR advertising_channel_type IS NULL)
        AND (
            event_date BETWEEN (SELECT ly_pre_start  FROM date_windows) AND (SELECT ly_pre_end  FROM date_windows)
            OR event_date BETWEEN (SELECT ly_post_start FROM date_windows) AND (SELECT ly_post_end FROM date_windows)
        )
        AND combined_entity_id IN (SELECT combined_entity_id FROM eligible_ces)

),

ly_funnel_aggregated AS (

    SELECT
        combined_entity_id,
        ly_period,
        COUNT(DISTINCT user_id) AS traffic,
        COUNT(DISTINCT IF(
            has_order_completed
                AND DATE_DIFF(order_completed_timestamp, session_start_timestamp, DAY) <= 30,
            user_id, NULL
        )) AS converters

    FROM ly_funnel_raw

    WHERE ly_period IS NOT NULL

    GROUP BY 1, 2

),

ly_funnel_pivoted AS (

    SELECT
        combined_entity_id,
        SUM(IF(ly_period = 'ly_pre',  traffic, 0))    AS ly_pre_traffic,
        SUM(IF(ly_period = 'ly_post', traffic, 0))    AS ly_post_traffic,
        SUM(IF(ly_period = 'ly_pre',  converters, 0)) AS ly_pre_converters,
        SUM(IF(ly_period = 'ly_post', converters, 0)) AS ly_post_converters

    FROM ly_funnel_aggregated

    GROUP BY 1

),

final AS (

    SELECT
        eligible_ces.combined_entity_id,
        ce_metadata.combined_entity_name,
        ce_metadata.market,
        ce_metadata.country,

        eligible_ces.pre_revenue,
        eligible_ces.post_revenue,
        eligible_ces.pre_count_orders,
        eligible_ces.post_count_orders,
        eligible_ces.pre_gross_bookings,
        eligible_ces.post_gross_bookings,
        eligible_ces.pre_gross_bookings_completed,
        eligible_ces.post_gross_bookings_completed,

        COALESCE(funnel_pivoted.pre_traffic, 0)            AS pre_traffic,
        COALESCE(funnel_pivoted.post_traffic, 0)           AS post_traffic,
        COALESCE(funnel_pivoted.pre_traffic_paid, 0)       AS pre_traffic_paid,
        COALESCE(funnel_pivoted.post_traffic_paid, 0)      AS post_traffic_paid,
        COALESCE(funnel_pivoted.pre_traffic_organic, 0)    AS pre_traffic_organic,
        COALESCE(funnel_pivoted.post_traffic_organic, 0)   AS post_traffic_organic,
        COALESCE(funnel_pivoted.pre_traffic_google, 0)     AS pre_traffic_google,
        COALESCE(funnel_pivoted.post_traffic_google, 0)    AS post_traffic_google,
        COALESCE(funnel_pivoted.pre_traffic_microsoft, 0)  AS pre_traffic_microsoft,
        COALESCE(funnel_pivoted.post_traffic_microsoft, 0) AS post_traffic_microsoft,
        COALESCE(funnel_pivoted.pre_traffic_paid_other, 0) AS pre_traffic_paid_other,
        COALESCE(funnel_pivoted.post_traffic_paid_other, 0) AS post_traffic_paid_other,

        COALESCE(funnel_pivoted.pre_users_select_page_viewed, 0)  AS pre_users_select_page_viewed,
        COALESCE(funnel_pivoted.post_users_select_page_viewed, 0) AS post_users_select_page_viewed,
        COALESCE(funnel_pivoted.pre_users_checkout_started, 0)    AS pre_users_checkout_started,
        COALESCE(funnel_pivoted.post_users_checkout_started, 0)   AS post_users_checkout_started,
        COALESCE(funnel_pivoted.pre_users_order_completed, 0)     AS pre_users_order_completed,
        COALESCE(funnel_pivoted.post_users_order_completed, 0)    AS post_users_order_completed,

        -- L4W context (NULL when CE has no data in the window; Python handles N/A)
        -- Kept for backward-compat + the LTC verdict:
        l4w_revenue.l4w_total_revenue / 4                                   AS l4w_avg_weekly_revenue,
        SAFE_DIVIDE(l4w_funnel.l4w_converters, l4w_funnel.l4w_traffic)      AS l4w_cvr,
        -- L4W raw components — Python computes the full driver matrix from these:
        l4w_revenue.l4w_total_revenue              AS l4w_total_revenue,
        l4w_revenue.l4w_count_orders               AS l4w_count_orders,
        l4w_revenue.l4w_gross_bookings             AS l4w_gross_bookings,
        l4w_revenue.l4w_gross_bookings_completed   AS l4w_gross_bookings_completed,
        l4w_funnel.l4w_traffic                     AS l4w_traffic,
        l4w_funnel.l4w_converters                  AS l4w_converters,

        -- LY same-week context (NULL if CE didn't exist a year ago)
        -- Kept for backward-compat + the LTC verdict:
        ly_revenue_pivoted.ly_pre_revenue                                                              AS ly_pre_revenue,
        ly_revenue_pivoted.ly_post_revenue                                                             AS ly_post_revenue,
        SAFE_DIVIDE(ly_funnel_pivoted.ly_pre_converters,  ly_funnel_pivoted.ly_pre_traffic)            AS ly_pre_cvr,
        SAFE_DIVIDE(ly_funnel_pivoted.ly_post_converters, ly_funnel_pivoted.ly_post_traffic)           AS ly_post_cvr,
        -- LY raw components — Python computes the full driver matrix from these:
        ly_revenue_pivoted.ly_pre_count_orders               AS ly_pre_count_orders,
        ly_revenue_pivoted.ly_post_count_orders              AS ly_post_count_orders,
        ly_revenue_pivoted.ly_pre_gross_bookings             AS ly_pre_gross_bookings,
        ly_revenue_pivoted.ly_post_gross_bookings            AS ly_post_gross_bookings,
        ly_revenue_pivoted.ly_pre_gross_bookings_completed   AS ly_pre_gross_bookings_completed,
        ly_revenue_pivoted.ly_post_gross_bookings_completed  AS ly_post_gross_bookings_completed,
        ly_funnel_pivoted.ly_pre_traffic                     AS ly_pre_traffic,
        ly_funnel_pivoted.ly_post_traffic                    AS ly_post_traffic,
        ly_funnel_pivoted.ly_pre_converters                  AS ly_pre_converters,
        ly_funnel_pivoted.ly_post_converters                 AS ly_post_converters,

        (SELECT pre_start  FROM date_windows) AS pre_period_start,
        (SELECT pre_end    FROM date_windows) AS pre_period_end,
        (SELECT post_start FROM date_windows) AS post_period_start,
        (SELECT post_end   FROM date_windows) AS post_period_end

    FROM eligible_ces
    LEFT JOIN funnel_pivoted     USING (combined_entity_id)
    LEFT JOIN ce_metadata        USING (combined_entity_id)
    LEFT JOIN l4w_revenue        USING (combined_entity_id)
    LEFT JOIN l4w_funnel         USING (combined_entity_id)
    LEFT JOIN ly_revenue_pivoted USING (combined_entity_id)
    LEFT JOIN ly_funnel_pivoted  USING (combined_entity_id)

)

SELECT * FROM final
ORDER BY pre_revenue DESC
