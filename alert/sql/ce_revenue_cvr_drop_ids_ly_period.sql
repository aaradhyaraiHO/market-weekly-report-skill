-- One partition-pruned seven-day prior-year context window for weekly RCA.
-- weekly_rca_helper.py runs this once for LY Pre and once for LY Post, then
-- joins both small result sets onto the base WoW/L4W query in memory.
WITH revenue AS (
    SELECT
        TRIM(combined_entity_id) AS combined_entity_id,
        SUM(sum_revenue_predicted) AS revenue,
        SUM(count_orders) AS count_orders,
        SUM(sum_order_value) AS gross_bookings,
        SUM(sum_order_value_completed) AS gross_bookings_completed
    FROM `headout-analytics.analytics_reporting.combined_entity_stats`
    WHERE report_timestamp >= TIMESTAMP(DATE('{{PERIOD_START}}'))
      AND report_timestamp <  TIMESTAMP(DATE('{{PERIOD_END}}') + INTERVAL 1 DAY)
      AND combined_entity_id IN ({{CE_IDS}})
    GROUP BY 1
),
funnel AS (
    SELECT
        TRIM(combined_entity_id) AS combined_entity_id,
        COUNT(DISTINCT user_id) AS traffic,
        COUNT(DISTINCT IF(
            has_order_completed
              AND DATE_DIFF(order_completed_timestamp, session_start_timestamp, DAY) <= 30,
            user_id, NULL
        )) AS converters
    FROM `headout-analytics.analytics_reporting.mixpanel_user_page_funnel_progression`
    WHERE (advertising_channel_type <> 'PERFORMANCE_MAX' OR advertising_channel_type IS NULL)
      AND event_date BETWEEN DATE('{{PERIOD_START}}') AND DATE('{{PERIOD_END}}')
      AND combined_entity_id IN ({{CE_IDS}})
    GROUP BY 1
)
SELECT
    revenue.combined_entity_id,
    revenue.revenue,
    revenue.count_orders,
    revenue.gross_bookings,
    revenue.gross_bookings_completed,
    funnel.traffic,
    funnel.converters
FROM revenue
LEFT JOIN funnel USING (combined_entity_id)
