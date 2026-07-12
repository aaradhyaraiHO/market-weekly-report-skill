{{
    config(
        materialized='table',
        tags=["refresh_schedule=weekly", "pii=false"],
        labels={'contains_pii': 'false', 'refresh_schedule': 'weekly'},
        persist_docs={'relation': true, 'columns': true},
        schema='intermediate'
    )
}}

/* CE weekly state layer. One row per combined entity per Monday week, built on
   int_ce_weekly_fact via window functions:
     - trailing windows (4w, prior-4w, 13w) and same-week-last-year (YoY, 52w lag)
     - the 18-week trajectory (revenue / ROI / RPC / clicks) as an inline array
     - quarterly run-rate bands (tier_now vs tier_ly) and YoY fall levels
     - trend_state (Improving / Declining / Stable / Volatile)

   Weeks are dense (every CE has every week in the fact), so ROWS frames map 1:1
   to calendar weeks. YoY uses a 52-week lag (ISO 52/53-week drift is accepted).

   The full bucket classification (Losing Ground / Scale / Iteration / New /
   Burning) is a downstream model: it additionally needs dim_combined_entities
   (category, launch, evolution), MMP execution, targets, and the channel
   attribution split. This model stops at state + bands + trend. */

WITH windowed AS (

    SELECT
        combined_entity_id,
        week_start_date,
        combined_entity_name,
        business_market,
        country,
        sum_revenue,
        sum_competitor_gbv,
        sum_ho_competition_gbv,
        weeks_since_launch,
        ga_contribution_pct,
        bnpl_pct,
        rev_google_same,
        rev_google_other,
        rev_pmax,
        rev_bing,
        rev_organic,
        rev_other,

        COUNT(*) OVER ce_to_date AS weeks_of_history,

        -- Single-week revenue context
        LAG(sum_revenue, 1) OVER ce_ordered AS rev_w_prev,
        LAG(sum_revenue, 52) OVER ce_ordered AS rev_w_ly,

        -- Trailing windows on revenue
        SUM(sum_revenue) OVER ce_4w AS rev_4w,
        SUM(sum_revenue) OVER ce_prev_4w AS rev_4w_prev4,
        SUM(sum_revenue) OVER ce_4w_ly AS rev_4w_ly,
        SUM(sum_revenue) OVER ce_13w AS rev_13w,
        SUM(sum_revenue) OVER ce_13w_ly AS rev_13w_ly,

        -- Trailing 4w paid + funnel sums (this year)
        SUM(count_paid_clicks) OVER ce_4w AS clicks_4w,
        SUM(sum_google_ads_spend) OVER ce_4w AS spend_4w,
        SUM(count_orders) OVER ce_4w AS orders_4w,
        SUM(sum_gross_bookings) OVER ce_4w AS gbv_4w,
        SUM(count_completed_orders) OVER ce_4w AS completed_4w,

        -- Trailing 4w paid + funnel sums (same window last year)
        SUM(count_paid_clicks) OVER ce_4w_ly AS clicks_4w_ly,
        SUM(sum_google_ads_spend) OVER ce_4w_ly AS spend_4w_ly,
        SUM(count_orders) OVER ce_4w_ly AS orders_4w_ly,
        SUM(sum_gross_bookings) OVER ce_4w_ly AS gbv_4w_ly,
        SUM(count_completed_orders) OVER ce_4w_ly AS completed_4w_ly,

        -- Volatility inputs (last 8 weeks)
        STDDEV_SAMP(sum_revenue) OVER ce_8w AS rev_stddev_8w,
        AVG(sum_revenue) OVER ce_8w AS rev_avg_8w,

        -- 18-week trajectory (ascending), one rich array
        ARRAY_AGG(
            STRUCT(
                week_start_date,
                sum_revenue,
                paid_roi_pct,
                revenue_per_click,
                count_paid_clicks
            )
        ) OVER ce_18w AS trajectory_18w

    FROM (
        SELECT
            f.*,
            attr.ga_contribution_pct,
            attr.bnpl_pct,
            attr.rev_google_same,
            attr.rev_google_other,
            attr.rev_pmax,
            attr.rev_bing,
            attr.rev_organic,
            attr.rev_other
        FROM {{ ref('int_ce_weekly_fact') }} AS f
        LEFT JOIN {{ ref('int_ce_weekly_attribution') }} AS attr
            USING (combined_entity_id, week_start_date)
    )

    WINDOW
        ce_ordered AS (PARTITION BY combined_entity_id ORDER BY week_start_date),
        ce_to_date AS (PARTITION BY combined_entity_id ORDER BY week_start_date ROWS UNBOUNDED PRECEDING),
        ce_4w AS (PARTITION BY combined_entity_id ORDER BY week_start_date ROWS BETWEEN 3 PRECEDING AND CURRENT ROW),
        ce_prev_4w AS (PARTITION BY combined_entity_id ORDER BY week_start_date ROWS BETWEEN 7 PRECEDING AND 4 PRECEDING),
        ce_4w_ly AS (PARTITION BY combined_entity_id ORDER BY week_start_date ROWS BETWEEN 55 PRECEDING AND 52 PRECEDING),
        ce_13w AS (PARTITION BY combined_entity_id ORDER BY week_start_date ROWS BETWEEN 12 PRECEDING AND CURRENT ROW),
        ce_13w_ly AS (PARTITION BY combined_entity_id ORDER BY week_start_date ROWS BETWEEN 64 PRECEDING AND 52 PRECEDING),
        ce_8w AS (PARTITION BY combined_entity_id ORDER BY week_start_date ROWS BETWEEN 7 PRECEDING AND CURRENT ROW),
        ce_18w AS (PARTITION BY combined_entity_id ORDER BY week_start_date ROWS BETWEEN 17 PRECEDING AND CURRENT ROW)

),

final AS (

    SELECT
        combined_entity_id,
        week_start_date,
        combined_entity_name,
        business_market,
        country,
        weeks_of_history,

        -- Revenue state
        sum_revenue AS rev_w,
        rev_w_prev,
        rev_w_ly,
        SAFE_DIVIDE(sum_revenue - rev_w_prev, rev_w_prev) AS wow_pct,
        rev_4w,
        rev_4w_prev4,
        rev_4w_ly,
        SAFE_DIVIDE(rev_4w - rev_4w_ly, rev_4w_ly) AS rev_4w_yoy_pct,
        rev_13w,
        rev_13w_ly,
        SAFE_DIVIDE(rev_13w - rev_13w_ly, rev_13w_ly) AS rev_13w_yoy_pct,
        rev_4w / 4 AS run_rate_wk,

        -- Paid funnel (trailing 4w, computed from sums)
        clicks_4w,
        spend_4w,
        SAFE_DIVIDE(rev_4w, spend_4w) * 100 AS roi_4w_pct,
        SAFE_DIVIDE(rev_4w, clicks_4w) AS rpc_4w,
        SAFE_DIVIDE(spend_4w, clicks_4w) AS cpc_4w,
        SAFE_DIVIDE(orders_4w, clicks_4w) AS paid_cvr_4w,
        SAFE_DIVIDE(gbv_4w, orders_4w) AS aov_4w,
        SAFE_DIVIDE(rev_4w, gbv_4w) AS take_rate_4w,
        SAFE_DIVIDE(completed_4w, orders_4w) AS completion_rate_4w,
        SAFE_DIVIDE(clicks_4w - clicks_4w_ly, clicks_4w_ly) AS clicks_4w_yoy_pct,
        SAFE_DIVIDE(
            SAFE_DIVIDE(rev_4w, spend_4w) - SAFE_DIVIDE(rev_4w_ly, spend_4w_ly),
            SAFE_DIVIDE(rev_4w_ly, spend_4w_ly)
        ) AS roi_4w_yoy_pct,
        SAFE_DIVIDE(
            SAFE_DIVIDE(rev_4w, clicks_4w) - SAFE_DIVIDE(rev_4w_ly, clicks_4w_ly),
            SAFE_DIVIDE(rev_4w_ly, clicks_4w_ly)
        ) AS rpc_4w_yoy_pct,

        -- Quality, last year + CVR YoY
        SAFE_DIVIDE(rev_4w_ly, gbv_4w_ly) AS take_rate_4w_ly,
        SAFE_DIVIDE(gbv_4w_ly, orders_4w_ly) AS aov_4w_ly,
        SAFE_DIVIDE(completed_4w_ly, orders_4w_ly) AS completion_rate_4w_ly,
        SAFE_DIVIDE(
            SAFE_DIVIDE(orders_4w, clicks_4w) - SAFE_DIVIDE(orders_4w_ly, clicks_4w_ly),
            SAFE_DIVIDE(orders_4w_ly, clicks_4w_ly)
        ) AS cvr_4w_yoy_pct,

        -- Faster band on trailing-4w run-rate (×3.25 ≈ quarter)
        CASE WHEN rev_4w IS NULL OR rev_4w <= 0 THEN 'Does Not Exist' WHEN rev_4w*3.25 >= 50000 THEN 'Hero' WHEN rev_4w*3.25 >= 10000 THEN 'Pro' WHEN rev_4w*3.25 >= 2000 THEN 'Seed' ELSE 'Longtail' END AS tier_4w,
        CASE WHEN rev_4w_ly IS NULL OR rev_4w_ly <= 0 THEN 'Does Not Exist' WHEN rev_4w_ly*3.25 >= 50000 THEN 'Hero' WHEN rev_4w_ly*3.25 >= 10000 THEN 'Pro' WHEN rev_4w_ly*3.25 >= 2000 THEN 'Seed' ELSE 'Longtail' END AS tier_4w_ly,

        -- Meta
        EXTRACT(ISOYEAR FROM week_start_date) AS iso_year,
        EXTRACT(ISOWEEK FROM week_start_date) AS iso_week,
        CURRENT_TIMESTAMP() AS generated_at,
        SAFE_DIVIDE(rev_4w - rev_4w_prev4, 4) AS trend_slope,
        CONCAT('https://headout.omniapp.co/dashboards/5368ab53?f--iv8lWOuS=%7B%22values%22%3A%5B%22', combined_entity_id, '%22%5D%7D') AS omni_url,
        CAST(NULL AS STRING) AS team_comment,

        -- MMP placeholders (populated once stg_sheetload__mmp lands in BQ)
        CAST(NULL AS DATE) AS mmp_handover_date,
        CAST(NULL AS DATE) AS first_mmp_handover_date,
        CAST(NULL AS INT64) AS mmp_iteration_count_l26w,
        CAST(NULL AS BOOL) AS has_team_input_l6m,

        -- Shapley driver decomposition (5-factor multiplicative, via JS UDF)
        {{ target.schema }}.shapley_decomp(
            [STRUCT('traffic' AS k, CAST(clicks_4w AS FLOAT64) AS v),
             STRUCT('cvr' AS k, SAFE_DIVIDE(orders_4w, clicks_4w) AS v),
             STRUCT('aov' AS k, SAFE_DIVIDE(gbv_4w, orders_4w) AS v),
             STRUCT('cr' AS k, SAFE_DIVIDE(completed_4w, orders_4w) AS v),
             STRUCT('tr' AS k, SAFE_DIVIDE(rev_4w, NULLIF(gbv_4w * SAFE_DIVIDE(completed_4w, orders_4w), 0)) AS v)],
            [STRUCT('traffic' AS k, CAST(clicks_4w_ly AS FLOAT64) AS v),
             STRUCT('cvr' AS k, SAFE_DIVIDE(orders_4w_ly, clicks_4w_ly) AS v),
             STRUCT('aov' AS k, SAFE_DIVIDE(gbv_4w_ly, orders_4w_ly) AS v),
             STRUCT('cr' AS k, SAFE_DIVIDE(completed_4w_ly, orders_4w_ly) AS v),
             STRUCT('tr' AS k, SAFE_DIVIDE(rev_4w_ly, NULLIF(gbv_4w_ly * SAFE_DIVIDE(completed_4w_ly, orders_4w_ly), 0)) AS v)]
        ) AS shapley_struct,

        -- Bands on the 13-week (quarterly) run-rate
        CASE
            WHEN rev_13w IS NULL OR rev_13w <= 0 THEN 'Does Not Exist'
            WHEN rev_13w >= 50000 THEN 'Hero'
            WHEN rev_13w >= 10000 THEN 'Pro'
            WHEN rev_13w >= 2000 THEN 'Seed'
            ELSE 'Longtail'
        END AS tier_now,
        CASE
            WHEN rev_13w_ly IS NULL OR rev_13w_ly <= 0 THEN 'Does Not Exist'
            WHEN rev_13w_ly >= 50000 THEN 'Hero'
            WHEN rev_13w_ly >= 10000 THEN 'Pro'
            WHEN rev_13w_ly >= 2000 THEN 'Seed'
            ELSE 'Longtail'
        END AS tier_ly,

        -- Competition passthrough
        sum_competitor_gbv,
        sum_ho_competition_gbv,

        -- Attribution + inputs passthrough
        weeks_since_launch,
        ga_contribution_pct,
        bnpl_pct,
        rev_google_same,
        rev_google_other,
        rev_pmax,
        rev_bing,
        rev_organic,
        rev_other,

        -- Trajectory
        trajectory_18w,

        -- State label
        CASE
            WHEN weeks_of_history < 8 OR rev_4w_prev4 IS NULL THEN 'Insufficient History'
            WHEN SAFE_DIVIDE(rev_stddev_8w, rev_avg_8w) > 0.5 THEN 'Volatile'
            WHEN SAFE_DIVIDE(rev_4w - rev_4w_prev4, rev_4w_prev4) > 0.15 THEN 'Improving'
            WHEN SAFE_DIVIDE(rev_4w - rev_4w_prev4, rev_4w_prev4) < -0.15 THEN 'Declining'
            ELSE 'Stable'
        END AS trend_state,
        SAFE_DIVIDE(rev_4w - rev_4w_prev4, rev_4w_prev4) AS trend_4w_vs_prev4_pct

    FROM windowed

)

SELECT
    final.* EXCEPT (shapley_struct),
    shapley_struct.shapley AS shapley,
    shapley_struct.primary_driver AS primary_driver,
    shapley_struct.followed_by AS followed_by,
    -- Tier movement YoY (positive = fell N bands; uses 13w bands above)
    (
        CASE tier_ly
            WHEN 'Hero' THEN 4 WHEN 'Pro' THEN 3 WHEN 'Seed' THEN 2
            WHEN 'Longtail' THEN 1 ELSE 0
        END
    ) - (
        CASE tier_now
            WHEN 'Hero' THEN 4 WHEN 'Pro' THEN 3 WHEN 'Seed' THEN 2
            WHEN 'Longtail' THEN 1 ELSE 0
        END
    ) AS fall_levels_yoy,
    tier_now IN ('Hero', 'Pro') AS is_pro_plus_now,
    (tier_now IN ('Hero', 'Pro') OR tier_ly IN ('Hero', 'Pro')) AS pro_plus_l26w,

    -- Identity (from dim)
    dim.combined_entity_category AS category,
    dim.combined_entity_subcategory AS subcategory,
    dim.evolution_bucket AS evolution_bucket,

    -- Competition ratio + per-metric 18-week trajectory arrays (split out of trajectory_18w)
    SAFE_DIVIDE(sum_ho_competition_gbv, sum_competitor_gbv) * 100 AS ho_gyg_pct,
    ARRAY(SELECT CAST(ROUND(COALESCE(x.sum_revenue, 0)) AS INT64) FROM UNNEST(trajectory_18w) x) AS rev_last_18w,
    ARRAY(SELECT ROUND(COALESCE(x.paid_roi_pct, 0), 1) FROM UNNEST(trajectory_18w) x) AS roi_last_18w,
    ARRAY(SELECT ROUND(COALESCE(x.revenue_per_click, 0), 2) FROM UNNEST(trajectory_18w) x) AS rpc_last_18w,
    ARRAY(SELECT CAST(ROUND(COALESCE(x.count_paid_clicks, 0)) AS INT64) FROM UNNEST(trajectory_18w) x) AS clicks_last_18w,

    -- Full-schema columns not yet populated here — typed NULL placeholders so the
    -- schema is complete and nothing is silently missing.
    -- (competition detail + launch + category benchmark — available in int_ce_weekly_fact / a future benchmark model)
    CAST(NULL AS DATE) AS launch_date,
    CAST(NULL AS FLOAT64) AS gyg_rev_monthly,
    CAST(NULL AS STRING) AS gyg_tier,
    CAST(NULL AS INT64) AS ho_product_count,
    CAST(NULL AS INT64) AS competitor_product_count,
    CAST(NULL AS FLOAT64) AS cvr_category_median,
    -- (classification + targets — populated for real in ce_weekly_buckets; NULL here to mirror the full schema)
    CAST(NULL AS INT64) AS home_bucket,
    CAST(NULL AS STRING) AS home_bucket_name,
    CAST(NULL AS STRING) AS also_in,
    CAST(NULL AS STRING) AS bucket_reason,
    CAST(NULL AS INT64) AS priority_rank,
    CAST(NULL AS BOOL) AS qualifies_gap,
    CAST(NULL AS FLOAT64) AS target_rev_qtr,
    CAST(NULL AS FLOAT64) AS target_rev_week,
    CAST(NULL AS FLOAT64) AS attainment_pct,
    CAST(NULL AS FLOAT64) AS gap_to_target

FROM final
LEFT JOIN {{ ref('dim_combined_entities') }} AS dim
    ON dim.combined_entity_id = final.combined_entity_id
