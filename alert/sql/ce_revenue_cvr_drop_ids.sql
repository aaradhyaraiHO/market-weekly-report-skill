-- Query Run by Claude using Analytics-Skill
-- ============================================================================
-- Weekly (WoW) Revenue & CVR RCA — CE-level Pre/Post metrics, CE-id filtered
--
-- Variant of ce_revenue_cvr_drop.sql, but:
--   - Filtered to an explicit CE-id list ({{CE_IDS}}) so it runs cheaply for
--     just the CEs the weekly alert needs (mirrors ce_revenue_cvr_mom.sql).
--   - Date windows are anchored to an explicit W0 Monday ({{WEEK_START}}) so
--     the query reproduces the exact week the weekly report covers, rather than
--     "last complete week relative to CURRENT_DATE". Post = the Mon–Sun week
--     starting {{WEEK_START}}; Pre = the week before. This keeps the numbers in
--     lock-step with the report even when the alert is (re)run days later.
--   - No per-market revenue floor — the caller (weekly_rca_helper.py) passes
--     only the CEs it wants to render.
--
-- Output column names/shape are IDENTICAL to ce_revenue_cvr_drop.sql, so
-- analyze_ce_row / the LTC renderer read it unchanged. All traffic is USER-BASED
-- (COUNT DISTINCT user_id); CVR = users_order_completed / traffic.
-- ============================================================================

WITH date_windows AS (

    SELECT
        -- Post = the Mon–Sun week starting {{WEEK_START}}; Pre = the week before.
        DATE('{{WEEK_START}}')                    AS post_start,
        DATE('{{WEEK_START}}') + INTERVAL 6 DAY   AS post_end,
        DATE('{{WEEK_START}}') - INTERVAL 7 DAY   AS pre_start,
        DATE('{{WEEK_START}}') - INTERVAL 1 DAY   AS pre_end,

        -- L4W: the 4 complete Mon–Sun weeks immediately before Pre week.
        DATE('{{WEEK_START}}') - INTERVAL 35 DAY  AS l4w_start,   -- post_start − 5 weeks
        DATE('{{WEEK_START}}') - INTERVAL 8 DAY   AS l4w_end,     -- pre_start − 1 day

        -- LY same week: 52-week (364-day) shift preserves Mon–Sun alignment.
        DATE('{{WEEK_START}}') - INTERVAL 371 DAY AS ly_pre_start,   -- post_start − 53 weeks
        DATE('{{WEEK_START}}') - INTERVAL 365 DAY AS ly_pre_end,     -- post_start − 52 weeks − 1 day
        DATE('{{WEEK_START}}') - INTERVAL 364 DAY AS ly_post_start,  -- post_start − 52 weeks
        DATE('{{WEEK_START}}') - INTERVAL 358 DAY AS ly_post_end     -- post_start − 51 weeks − 1 day

),

ce_revenue_raw AS (

    SELECT
        TRIM(combined_entity_id) AS combined_entity_id,
        CASE
            WHEN DATE(report_timestamp) BETWEEN (SELECT pre_start  FROM date_windows) AND (SELECT pre_end  FROM date_windows) THEN 'Pre'
            WHEN DATE(report_timestamp) BETWEEN (SELECT post_start FROM date_windows) AND (SELECT post_end FROM date_windows) THEN 'Post'
        END AS time_period,
        SUM(sum_revenue_predicted) AS revenue,   -- predicted = report's default revenue basis
        SUM(count_orders) AS count_orders,
        SUM(sum_order_value) AS gross_bookings,
        SUM(sum_order_value_completed) AS gross_bookings_completed

    FROM `headout-analytics.analytics_reporting.combined_entity_stats`

    -- Keep the partition column bare and the bounds compile-time constant so
    -- BigQuery prunes the monthly report_timestamp partitions.  The former
    -- DATE(report_timestamp) + scalar-subquery predicates scanned the table
    -- repeatedly and pushed the weekly RCA above the byte cap.
    WHERE report_timestamp >= TIMESTAMP(DATE('{{WEEK_START}}') - INTERVAL 7 DAY)
        AND report_timestamp <  TIMESTAMP(DATE('{{WEEK_START}}') + INTERVAL 7 DAY)
        AND combined_entity_id IN ({{CE_IDS}})

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

    -- Explicit CE list only (no market floor for the CE-id-filtered WoW RCA).
    SELECT * FROM ce_revenue_pivoted

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
    --   - 30-day funnel completion window  (applied per-step in our SELECT)
    --   - NO page_type filter — Omni does not restrict by page type, so we don't either
    WHERE (advertising_channel_type <> 'PERFORMANCE_MAX' OR advertising_channel_type IS NULL)
        AND event_date BETWEEN DATE('{{WEEK_START}}') - INTERVAL 7 DAY
                           AND DATE('{{WEEK_START}}') + INTERVAL 6 DAY
        AND combined_entity_id IN ({{CE_IDS}})

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
-- ============================================================================

l4w_revenue AS (
    SELECT
        CAST(NULL AS STRING) AS combined_entity_id,
        CAST(NULL AS FLOAT64) AS l4w_total_revenue,
        CAST(NULL AS FLOAT64) AS l4w_count_orders,
        CAST(NULL AS FLOAT64) AS l4w_gross_bookings,
        CAST(NULL AS FLOAT64) AS l4w_gross_bookings_completed
    FROM UNNEST(CAST([] AS ARRAY<STRING>)) AS combined_entity_id

),

l4w_funnel AS (
    SELECT
        CAST(NULL AS STRING) AS combined_entity_id,
        CAST(NULL AS INT64) AS l4w_traffic,
        CAST(NULL AS INT64) AS l4w_converters
    FROM UNNEST(CAST([] AS ARRAY<STRING>)) AS combined_entity_id

),

-- Prior-year context is loaded in two separately partition-pruned seven-day
-- jobs by weekly_rca_helper.py. Keeping it out of this base query prevents the
-- two historical funnel partitions from combining into one >80 GiB job.
ly_revenue_pivoted AS (
    SELECT
        CAST(NULL AS STRING) AS combined_entity_id,
        CAST(NULL AS FLOAT64) AS ly_pre_revenue,
        CAST(NULL AS FLOAT64) AS ly_post_revenue,
        CAST(NULL AS FLOAT64) AS ly_pre_count_orders,
        CAST(NULL AS FLOAT64) AS ly_post_count_orders,
        CAST(NULL AS FLOAT64) AS ly_pre_gross_bookings,
        CAST(NULL AS FLOAT64) AS ly_post_gross_bookings,
        CAST(NULL AS FLOAT64) AS ly_pre_gross_bookings_completed,
        CAST(NULL AS FLOAT64) AS ly_post_gross_bookings_completed
    FROM UNNEST(CAST([] AS ARRAY<STRING>)) AS combined_entity_id
),

ly_funnel_pivoted AS (
    SELECT
        CAST(NULL AS STRING) AS combined_entity_id,
        CAST(NULL AS INT64) AS ly_pre_traffic,
        CAST(NULL AS INT64) AS ly_post_traffic,
        CAST(NULL AS INT64) AS ly_pre_converters,
        CAST(NULL AS INT64) AS ly_post_converters
    FROM UNNEST(CAST([] AS ARRAY<STRING>)) AS combined_entity_id
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
