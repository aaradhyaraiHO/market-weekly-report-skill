{{
    config(
        materialized='table',
        tags=["refresh_schedule=weekly", "pii=false"],
        labels={'contains_pii': 'false', 'refresh_schedule': 'weekly'},
        persist_docs={'relation': true, 'columns': true},
        schema='intermediate'
    )
}}

/* Weekly channel-attribution split + BNPL for the CE weekly system. One row per
   combined entity per Monday week, from fct_orders ground-truth attribution
   (the same channel taxonomy + order filters as perf-audit and the monthly
   ce_buckets GA-contribution query).

   ga_contribution_pct = Google-paid revenue / total revenue, where Google-paid =
   channel_name 'Google Ads' EXCLUDING the '1 - %' campaigns (Bing-misclassified).
   This feeds the Scale bucket's GA-contribution arm. */

WITH orders AS (

    SELECT
        CAST(combined_entity_id AS STRING) AS combined_entity_id,
        DATE_TRUNC(DATE(created_at), WEEK(MONDAY)) AS week_start_date,
        amount_revenue_usd,
        is_using_pay_later,
        CASE
            WHEN channel_name = 'Google Ads'
                AND REGEXP_CONTAINS(campaign_name, CONCAT('cid', CAST(combined_entity_id AS STRING)))
                THEN 'google_same'
            WHEN channel_name = 'Google Ads' AND campaign_name LIKE '1 - %'
                THEN 'bing'
            WHEN channel_name = 'Bing Ads'
                AND REGEXP_CONTAINS(campaign_name, CONCAT('cid', CAST(combined_entity_id AS STRING)))
                THEN 'bing'
            WHEN channel_name = 'Google Ads'
                AND REGEXP_CONTAINS(LOWER(COALESCE(campaign_name, '')), r'pmax|performance.max')
                THEN 'pmax'
            WHEN channel_name = 'Google Ads'
                THEN 'google_other'
            WHEN channel_name = 'Bing Ads'
                THEN 'bing'
            WHEN channel_name = 'Organic Search'
                THEN 'organic'
            ELSE 'other'
        END AS channel_bucket

    FROM {{ ref('fct_orders') }}

    WHERE order_status NOT IN ('Dummy', 'Cancelled - Fraudulent')
        AND user_type = 'Customer'
        AND DATE(created_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL 78 WEEK)
        AND DATE(created_at) < DATE_TRUNC(CURRENT_DATE(), WEEK(MONDAY))
        AND combined_entity_id IS NOT NULL

),

aggregated AS (

    SELECT
        combined_entity_id,
        week_start_date,
        SUM(amount_revenue_usd) AS total_revenue,
        SUM(IF(channel_bucket = 'google_same', amount_revenue_usd, 0)) AS rev_google_same,
        SUM(IF(channel_bucket = 'google_other', amount_revenue_usd, 0)) AS rev_google_other,
        SUM(IF(channel_bucket = 'pmax', amount_revenue_usd, 0)) AS rev_pmax,
        SUM(IF(channel_bucket = 'bing', amount_revenue_usd, 0)) AS rev_bing,
        SUM(IF(channel_bucket = 'organic', amount_revenue_usd, 0)) AS rev_organic,
        SUM(IF(channel_bucket = 'other', amount_revenue_usd, 0)) AS rev_other,
        SUM(IF(channel_bucket IN ('google_same', 'google_other', 'pmax'), amount_revenue_usd, 0)) AS rev_google_paid,
        COUNT(*) AS count_orders,
        COUNTIF(is_using_pay_later) AS count_bnpl_orders

    FROM orders

    GROUP BY 1, 2

)

SELECT
    combined_entity_id,
    week_start_date,
    total_revenue,
    rev_google_same,
    rev_google_other,
    rev_pmax,
    rev_bing,
    rev_organic,
    rev_other,
    SAFE_DIVIDE(rev_google_paid, total_revenue) * 100 AS ga_contribution_pct,
    SAFE_DIVIDE(count_bnpl_orders, count_orders) * 100 AS bnpl_pct

FROM aggregated
