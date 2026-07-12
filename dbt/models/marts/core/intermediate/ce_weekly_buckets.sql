{{
    config(
        materialized='table',
        tags=["refresh_schedule=weekly", "pii=false"],
        labels={'contains_pii': 'false', 'refresh_schedule': 'weekly'},
        persist_docs={'relation': true, 'columns': true},
        schema='reporting'
    )
}}

/* CE weekly classification — the prioritized action queue, one row per combined
   entity per Monday week, on top of ce_weekly_snapshot + dim_combined_entities.

   Priority cascade (highest first): Burning -> Losing Ground -> Scale. The home
   bucket is the highest-priority qualifying bucket; the rest are tagged in
   also_in. CEs that qualify for none have home_bucket = NULL (not in the queue).

   Thresholds match the monthly ce_buckets engine, applied on weekly windows:
     - Losing Ground: was Pro+ last year AND trailing-13w revenue fell > 20% YoY.
       Reason cascade — clicks (4w YoY < -85%), inputs (RPC 4w YoY < -20%),
       paid optimization (ROI 4w YoY > +20% & ROI > 120%, OR ROI > 160%), else manual.
     - Scale (HO/GYG arm only): Pro+ now AND HO/competition GBV < 15%.
     - Burning: trailing-4w ROI < 100% AND 4w spend > $1,000.

   DEFERRED to a later iteration (need extra sources): Iteration & New buckets
   (launch recency + MMP), Gap-to-Target overlay (goals), and Scale's
   GA-contribution arm (channel attribution split). Scale's HO/GYG arm only fires
   when competitor GBV is present for the week (competitor_weekly_stats lags). */

WITH goals AS (

    SELECT
        CAST(entity_id AS STRING) AS combined_entity_id,
        target_month,
        SUM(target_revenue) AS monthly_target_revenue

    FROM {{ ref('revenue_goals') }}

    WHERE entity_type = 'Combined Entity'

    GROUP BY 1, 2

),

base AS (

    SELECT
        snapshot.combined_entity_id,
        snapshot.week_start_date,
        snapshot.combined_entity_name,
        snapshot.business_market,
        dim.combined_entity_category,
        dim.combined_entity_subcategory,
        dim.evolution_bucket,
        dim.management_type,

        snapshot.ga_contribution_pct,
        snapshot.bnpl_pct,
        snapshot.weeks_since_launch,
        goals.monthly_target_revenue,
        SAFE_DIVIDE(goals.monthly_target_revenue * 7, EXTRACT(DAY FROM LAST_DAY(snapshot.week_start_date))) AS weekly_target_revenue,

        snapshot.rev_w,
        snapshot.rev_13w,
        snapshot.rev_13w_yoy_pct,
        snapshot.run_rate_wk,
        snapshot.tier_now,
        snapshot.tier_ly,
        snapshot.is_pro_plus_now,
        snapshot.fall_levels_yoy,
        snapshot.trend_state,

        snapshot.roi_4w_pct,
        snapshot.roi_4w_yoy_pct,
        snapshot.rpc_4w_yoy_pct,
        snapshot.clicks_4w_yoy_pct,
        snapshot.spend_4w,

        snapshot.sum_competitor_gbv,
        snapshot.sum_ho_competition_gbv,
        SAFE_DIVIDE(snapshot.sum_ho_competition_gbv, snapshot.sum_competitor_gbv) * 100 AS ho_gyg_pct

    FROM {{ ref('ce_weekly_snapshot') }} AS snapshot
    LEFT JOIN {{ ref('dim_combined_entities') }} AS dim
        ON snapshot.combined_entity_id = dim.combined_entity_id
    LEFT JOIN goals
        ON snapshot.combined_entity_id = goals.combined_entity_id
        AND goals.target_month = DATE_TRUNC(snapshot.week_start_date, MONTH)

),

flags AS (

    SELECT
        *,

        SAFE_DIVIDE(run_rate_wk, weekly_target_revenue) * 100 AS attainment_pct,
        GREATEST(0, COALESCE(weekly_target_revenue, 0) - run_rate_wk) AS gap_to_target,

        -- Burning: trailing-4w ROI < 100% and meaningful spend
        (roi_4w_pct < 100 AND spend_4w > 1000) AS is_burning,

        -- Losing Ground: was Pro+ last year and trailing-13w revenue fell materially
        (tier_ly IN ('Hero', 'Pro')
            AND (rev_13w_yoy_pct < -0.20 OR fall_levels_yoy >= 1)) AS is_losing_ground,

        -- Scale: Pro+ under-scaled vs competition (HO/GYG < 15%) OR low Google-ads
        -- contribution (< 30%); or a Seed with zero Google-ads contribution.
        ((is_pro_plus_now AND (
                (ho_gyg_pct IS NOT NULL AND ho_gyg_pct < 15)
                OR (ga_contribution_pct IS NOT NULL AND ga_contribution_pct < 30)))
            OR (tier_now = 'Seed' AND ga_contribution_pct = 0)) AS is_scale,

        -- Iteration: launched in the last 26 weeks and not yet Pro+ (MMP-input
        -- refinement deferred — needs the MMP sheet landed in BQ).
        (weeks_since_launch IS NOT NULL
            AND weeks_since_launch <= 26
            AND NOT is_pro_plus_now
            AND tier_now IN ('Seed', 'Longtail', 'Does Not Exist')) AS is_iteration,

        -- New: does not exist on Headout but competition is present.
        (tier_now = 'Does Not Exist'
            AND sum_competitor_gbv IS NOT NULL
            AND sum_competitor_gbv > 0) AS is_new

    FROM base

),

classified AS (

    SELECT
        *,

        CASE
            WHEN is_burning THEN 6
            WHEN is_losing_ground THEN 2
            WHEN is_scale THEN 3
            WHEN is_iteration THEN 4
            WHEN is_new THEN 5
            ELSE NULL
        END AS home_bucket,

        -- Gap-to-Target overlay (never a home; flagged alongside the home bucket)
        (weekly_target_revenue > 0
            AND SAFE_DIVIDE(run_rate_wk, weekly_target_revenue) * 100 < 90
            AND gap_to_target > 467) AS qualifies_gap,

        -- Reason for the Losing Ground sub-cascade (descending priority)
        CASE
            WHEN clicks_4w_yoy_pct < -0.85 THEN 'Campaigns dormant'
            WHEN rpc_4w_yoy_pct < -0.20 THEN 'Inputs'
            WHEN (roi_4w_yoy_pct > 0.20 AND roi_4w_pct > 120) OR roi_4w_pct > 160 THEN 'Paid optimization required'
            ELSE 'Manual check required'
        END AS losing_ground_reason

    FROM flags

)

SELECT
    combined_entity_id,
    week_start_date,
    combined_entity_name,
    business_market,
    combined_entity_category,
    combined_entity_subcategory,
    evolution_bucket,
    management_type,

    home_bucket,
    CASE home_bucket
        WHEN 6 THEN 'Burning / Low ROI'
        WHEN 2 THEN 'Losing Ground'
        WHEN 3 THEN 'Scale Opportunities'
        WHEN 4 THEN 'Iteration'
        WHEN 5 THEN 'New Launches'
        ELSE NULL
    END AS home_bucket_name,

    CASE home_bucket
        WHEN 6 THEN CONCAT('Burning: ROI ', CAST(CAST(ROUND(roi_4w_pct) AS INT64) AS STRING), '%, $', CAST(CAST(ROUND(spend_4w) AS INT64) AS STRING), '/4w spend')
        WHEN 2 THEN CONCAT(losing_ground_reason, ' (13w rev ', CAST(CAST(ROUND(rev_13w_yoy_pct * 100) AS INT64) AS STRING), '% YoY)')
        WHEN 3 THEN CONCAT('Scale — HO/GYG ', IFNULL(CAST(CAST(ROUND(ho_gyg_pct) AS INT64) AS STRING), 'n/a'), '%, GA contrib ', IFNULL(CAST(CAST(ROUND(ga_contribution_pct) AS INT64) AS STRING), 'n/a'), '%')
        WHEN 4 THEN CONCAT('Launched ', CAST(weeks_since_launch AS STRING), 'w ago, ', tier_now, ' — iterate')
        WHEN 5 THEN 'DNE on Headout, competition present'
        ELSE NULL
    END AS bucket_reason,

    ARRAY_CONCAT(
        IF(is_burning AND home_bucket != 6, [6], []),
        IF(is_losing_ground AND home_bucket != 2, [2], []),
        IF(is_scale AND home_bucket != 3, [3], []),
        IF(is_iteration AND home_bucket != 4, [4], []),
        IF(is_new AND home_bucket != 5, [5], [])
    ) AS also_in,

    qualifies_gap,
    ROW_NUMBER() OVER (
        PARTITION BY business_market, week_start_date
        ORDER BY CASE WHEN is_burning THEN 1 WHEN is_losing_ground THEN 2 WHEN is_scale THEN 3 WHEN is_iteration THEN 4 WHEN is_new THEN 5 ELSE 99 END, rev_13w DESC
    ) AS priority_rank,
    is_burning,
    is_losing_ground,
    is_scale,
    is_iteration,
    is_new,

    -- Evidence columns (for the digest / drill-down)
    rev_w,
    rev_13w,
    rev_13w_yoy_pct,
    run_rate_wk,
    tier_now,
    tier_ly,
    fall_levels_yoy,
    trend_state,
    roi_4w_pct,
    roi_4w_yoy_pct,
    rpc_4w_yoy_pct,
    clicks_4w_yoy_pct,
    spend_4w,
    ho_gyg_pct,
    ga_contribution_pct,
    bnpl_pct,
    weeks_since_launch,
    monthly_target_revenue,
    weekly_target_revenue,
    attainment_pct,
    gap_to_target

FROM classified
