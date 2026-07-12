{{
    config(
        materialized='table',
        tags=["refresh_schedule=weekly", "pii=false"],
        labels={'contains_pii': 'false', 'refresh_schedule': 'weekly'},
        persist_docs={'relation': true, 'columns': true},
        schema='intermediate'
    )
}}

WITH funnel_events AS (

    SELECT
        experience_id,
        DATE_TRUNC(event_date, WEEK(MONDAY)) AS week_start_date,
        user_id,
        CAST(has_either_ho_mb_page_viewed AS INT64) AS has_lp_view,
        CAST(has_select_page_viewed AS INT64) AS has_select_view,
        CAST(has_checkout_started AS INT64) AS has_checkout,
        CAST(has_order_completed AS INT64) AS has_order

    FROM {{ ref('mixpanel_user_funnel') }}

    WHERE event_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 52 WEEK)
        AND experience_id IS NOT NULL
        AND experience_id != 'null'

),

funnel_aggregated AS (

    SELECT
        experience_id,
        week_start_date,
        COUNT(DISTINCT user_id) AS count_users,
        SUM(has_lp_view) AS count_lp_views,
        SUM(has_select_view) AS count_select_views,
        SUM(has_checkout) AS count_checkouts,
        SUM(has_order) AS count_orders,
        SAFE_DIVIDE(SUM(has_select_view), NULLIF(SUM(has_lp_view), 0)) AS rate_lp_to_select,
        SAFE_DIVIDE(SUM(has_checkout), NULLIF(SUM(has_select_view), 0)) AS rate_select_to_checkout,
        SAFE_DIVIDE(SUM(has_order), NULLIF(SUM(has_checkout), 0)) AS rate_checkout_to_order

    FROM funnel_events

    GROUP BY 1, 2

),

final AS (

    SELECT
        experience_id,
        week_start_date,
        count_users,
        count_lp_views,
        count_select_views,
        count_checkouts,
        count_orders,
        rate_lp_to_select,
        rate_select_to_checkout,
        rate_checkout_to_order

    FROM funnel_aggregated

)

SELECT * FROM final
