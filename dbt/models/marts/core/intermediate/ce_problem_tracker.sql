{{
    config(
        materialized='table',
        tags=["refresh_schedule=weekly", "pii=false"],
        labels={'contains_pii': 'false', 'refresh_schedule': 'weekly'},
        persist_docs={'relation': true, 'columns': true},
        schema='reporting'
    )
}}

/* "Did the intervention work?" tracker. One row per problem × CE × week, from
   the baseline week onward. Reads the manual problem registry (ce_problem_registry
   seed) + the curated metric library (metric_library seed) and diffs each CE's
   chosen success metric against its baseline-week value in ce_weekly_snapshot.

   Per problem the team logs: the cohort (one registry row per CE), the
   intervention/baseline week, and a success_metric_key from the library. The
   library defines the metric's improvement direction, the threshold to call it
   "working", and the minimum weeks before a verdict. Verdict per week:
   Too early -> Working / Not working (Inconclusive when baseline is missing/zero). */

WITH registry AS (

    SELECT
        problem_id,
        problem_name,
        CAST(combined_entity_id AS STRING) AS combined_entity_id,
        CAST(intervention_date AS DATE) AS intervention_date,
        CAST(baseline_week AS DATE) AS baseline_week,
        success_metric_key,
        status,
        owner

    FROM {{ ref('ce_problem_registry') }}

    WHERE status = 'active'

),

library AS (

    SELECT
        metric_key,
        metric_label,
        direction,
        CAST(threshold_pct AS FLOAT64) AS threshold_pct,
        CAST(min_weeks AS INT64) AS min_weeks

    FROM {{ ref('metric_library') }}

),

snap AS (

    SELECT
        combined_entity_id,
        week_start_date,
        rev_4w,
        roi_4w_pct,
        rpc_4w,
        cpc_4w,
        clicks_4w,
        paid_cvr_4w,
        take_rate_4w,
        ga_contribution_pct

    FROM {{ ref('ce_weekly_snapshot') }}

),

metrics_long AS (

    SELECT combined_entity_id, week_start_date, 'roi_recovered' AS metric_key, roi_4w_pct AS metric_value FROM snap
    UNION ALL
    SELECT combined_entity_id, week_start_date, 'rpc_recovered', rpc_4w FROM snap
    UNION ALL
    SELECT combined_entity_id, week_start_date, 'revenue_recovered', rev_4w FROM snap
    UNION ALL
    SELECT combined_entity_id, week_start_date, 'clicks_recovered', clicks_4w FROM snap
    UNION ALL
    SELECT combined_entity_id, week_start_date, 'cvr_improved', paid_cvr_4w FROM snap
    UNION ALL
    SELECT combined_entity_id, week_start_date, 'take_rate_improved', take_rate_4w FROM snap
    UNION ALL
    SELECT combined_entity_id, week_start_date, 'ga_share_shifted', ga_contribution_pct FROM snap
    UNION ALL
    SELECT combined_entity_id, week_start_date, 'cost_reduced', cpc_4w FROM snap

),

baseline AS (

    SELECT
        registry.problem_id,
        registry.combined_entity_id,
        metrics_long.metric_value AS metric_baseline

    FROM registry
    JOIN metrics_long
        ON metrics_long.combined_entity_id = registry.combined_entity_id
        AND metrics_long.metric_key = registry.success_metric_key
        AND metrics_long.week_start_date = registry.baseline_week

),

baseline_rev AS (

    SELECT
        registry.problem_id,
        registry.combined_entity_id,
        snap.rev_4w AS rev_baseline

    FROM registry
    JOIN snap
        ON snap.combined_entity_id = registry.combined_entity_id
        AND snap.week_start_date = registry.baseline_week

),

tracking AS (

    SELECT
        registry.problem_id,
        registry.problem_name,
        registry.combined_entity_id,
        metrics_long.week_start_date,
        registry.intervention_date,
        registry.baseline_week,
        registry.success_metric_key,
        registry.status,
        registry.owner,
        metrics_long.metric_value AS metric_current,
        DATE_DIFF(metrics_long.week_start_date, registry.baseline_week, WEEK) AS weeks_since_intervention

    FROM registry
    JOIN metrics_long
        ON metrics_long.combined_entity_id = registry.combined_entity_id
        AND metrics_long.metric_key = registry.success_metric_key
        AND metrics_long.week_start_date >= registry.baseline_week

),

assembled AS (

    SELECT
        tracking.problem_id,
        tracking.problem_name,
        tracking.combined_entity_id,
        tracking.week_start_date,
        tracking.intervention_date,
        tracking.baseline_week,
        tracking.success_metric_key,
        library.metric_label,
        tracking.status,
        tracking.owner,
        tracking.weeks_since_intervention,
        baseline.metric_baseline,
        tracking.metric_current,
        baseline_rev.rev_baseline,
        snap.rev_4w AS rev_current,
        tracking.metric_current - baseline.metric_baseline AS metric_delta_abs,
        SAFE_DIVIDE(tracking.metric_current - baseline.metric_baseline, ABS(baseline.metric_baseline)) AS metric_delta_pct,
        library.direction,
        library.threshold_pct,
        library.min_weeks,
        ARRAY_AGG(tracking.metric_current) OVER (
            PARTITION BY tracking.problem_id, tracking.combined_entity_id
            ORDER BY tracking.week_start_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS metric_since_baseline

    FROM tracking
    LEFT JOIN baseline
        USING (problem_id, combined_entity_id)
    LEFT JOIN baseline_rev
        USING (problem_id, combined_entity_id)
    LEFT JOIN snap
        ON snap.combined_entity_id = tracking.combined_entity_id
        AND snap.week_start_date = tracking.week_start_date
    LEFT JOIN library
        ON library.metric_key = tracking.success_metric_key

)

SELECT
    problem_id,
    problem_name,
    combined_entity_id,
    week_start_date,
    intervention_date,
    baseline_week,
    success_metric_key,
    metric_label,
    status,
    owner,
    weeks_since_intervention,
    metric_baseline,
    metric_current,
    metric_delta_abs,
    metric_delta_pct,
    rev_baseline,
    rev_current,
    metric_since_baseline,
    CASE
        WHEN metric_baseline IS NULL OR metric_baseline = 0 THEN 'Inconclusive'
        WHEN weeks_since_intervention < min_weeks THEN 'Too early'
        WHEN (direction = 'up' AND SAFE_DIVIDE(metric_current - metric_baseline, ABS(metric_baseline)) >= threshold_pct)
            OR (direction = 'down' AND SAFE_DIVIDE(metric_baseline - metric_current, ABS(metric_baseline)) >= threshold_pct)
            THEN 'Working'
        ELSE 'Not working'
    END AS verdict

FROM assembled
