"""Build the V2 market-level OKR sidecar from the canonical KR engine logic.

This is a read-only BigQuery enrichment.  It deliberately does not read the
global ``weekly_kr_metrics`` table because that table has no market grain and
its older weekly-classification definitions do not match the current central
OKR dashboard.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "scripts" / "weekly_report"

OKR_IDS = (
    "grow_cumulative_pro_plus_ces",
    "launch_new_pro_plus_mature",
    "launch_new_pro_plus_emerging_growth",
    "grow_non_poi_gel_revenue_yoy",
)

STATUS_UNAVAILABLE = "Status unavailable"
GEL_STATUS_RULE = "central-okr/flowrev-progress-v1"
# The central tracker's flowrev computeKr + krStatus contract uses exact QTD
# YoY / target, with a neutral first-30%-of-quarter period. Never copy its old
# official_status constants or apply a company target to market contributions.
GEL_STATUS_SOURCE = "scripts/band_dashboards/okr_tracker_template.html:computeKr/krStatus"

# Company-grain targets from the authoritative H2 2026 OKR tracker. These are
# deliberately attached only to the Headout roll-up: comparing a company goal
# with an individual market actual would be a grain error.
COMPANY_TARGETS = {
    3: {
        "grow_cumulative_pro_plus_ces": "500 CEs",
        "launch_new_pro_plus_mature": "55 CEs",
        "launch_new_pro_plus_emerging_growth": "35 CEs",
        "grow_non_poi_gel_revenue_yoy": "+100% YoY",
    },
    4: {
        "grow_cumulative_pro_plus_ces": "520 CEs",
        "launch_new_pro_plus_mature": "45 CEs",
        "launch_new_pro_plus_emerging_growth": "25 CEs",
        "grow_non_poi_gel_revenue_yoy": "+90% YoY",
    },
}

COMPANY_GEL_TARGET_SOURCE = {
    "source": "https://docs.google.com/spreadsheets/d/1vRgfr9jnefP7grYKa-zaSkUzCpT7pnah7UCkaZuz5Dg/edit?gid=1972760172",
    "source_tab": "H2 2026",
    "source_verified_on": "2026-11-02",
    "source_cells": {3: "F30", 4: "G30"},
}

COMPANY_PRO_TARGET_CELLS = {
    OKR_IDS[0]: {3: 'F13', 4: 'G13'},
    OKR_IDS[1]: {3: 'F24', 4: 'G24'},
    OKR_IDS[2]: {3: 'F25', 4: 'G25'},
}

# Additive status evidence only. This reproduces central q5k's trailing-13-week
# count history; it does not replace the existing headline/member calculation.
PRO_PLUS_STATUS_HISTORY_SQL = r"""
WITH weekly AS (
  SELECT combined_entity_id, DATE_TRUNC(report_date, WEEK) AS report_week,
         SUM(sum_revenue_predicted) AS wrev
  FROM `headout-analytics.analytics_reporting.combined_entity_stats`
  WHERE report_timestamp >= TIMESTAMP(DATE_SUB(DATE(@week_start), INTERVAL 119 DAY))
    AND report_date BETWEEN DATE_SUB(DATE(@week_start), INTERVAL 119 DAY)
                        AND DATE_ADD(DATE(@week_start), INTERVAL 6 DAY)
  GROUP BY 1, 2
), rolling AS (
  SELECT combined_entity_id, report_week,
         SUM(wrev) OVER (PARTITION BY combined_entity_id ORDER BY UNIX_DATE(report_week)
                        RANGE BETWEEN 84 PRECEDING AND CURRENT ROW) AS l92
  FROM weekly
)
SELECT CAST(report_week AS STRING) AS week, COUNTIF(l92 >= 10000) AS value
FROM rolling
WHERE report_week BETWEEN DATE_SUB(DATE(@week_start), INTERVAL 35 DAY) AND DATE(@week_start)
GROUP BY 1 ORDER BY 1
"""


# Mirrors the current central-tracking engine:
# - O1-KR1: L92 predicted revenue >= $10K.
# - O2-KR1/2: achieved or projected to $10K this quarter using the exact
#   trailing-28-day/L4W pace formula, with every prior-four-quarter total < $10K.
# - O1-KR3: exact-calendar-QTD predicted GEL revenue vs the same month/day
#   span one year earlier; non-Mature, non-POI, Managed/Managed Lite only.
# CE -> market attribution uses the same dim-first/latest-stats fallback as the
# central dashboard and the weekly report.
MARKET_OKR_SQL = r"""
WITH params AS (
    SELECT
        DATE(@week_start) AS week_start,
        DATE_ADD(DATE(@week_start), INTERVAL 6 DAY) AS cutoff,
        DATE_TRUNC(DATE(@week_start), QUARTER) AS quarter_start,
        DATE_SUB(DATE_TRUNC(DATE(@week_start), QUARTER), INTERVAL 12 MONTH) AS prior_4q_start
),

stats_dims AS (
    SELECT
        combined_entity_id,
        business_market,
        business_region
    FROM `headout-analytics.analytics_reporting.combined_entity_stats`, params
    WHERE report_timestamp >= TIMESTAMP(prior_4q_start)
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY combined_entity_id
        ORDER BY report_date DESC
    ) = 1
),

ce_dims AS (
    SELECT
        stats_dims.combined_entity_id,
        CASE IFNULL(NULLIF(COALESCE(dim.market, stats_dims.business_market), ''), 'Unknown')
            WHEN 'East Asia (CN, TW)' THEN 'East Asia'
            WHEN 'East Asia (JPN, SK, HK)' THEN 'East Asia'
            WHEN 'SEA (MLY + IND + VN)' THEN 'South East Asia'
            WHEN 'SEA (SIN + THA)' THEN 'South East Asia'
            WHEN 'Cambodia' THEN 'South East Asia'
            WHEN 'India' THEN 'South East Asia'
            WHEN 'Egypt' THEN 'North Africa'
            WHEN 'Morocco' THEN 'North Africa'
            WHEN 'Tunisia' THEN 'North Africa'
            WHEN 'El Salvador' THEN 'Mexico & Central America'
            WHEN 'Armenia' THEN 'CSEE'
            WHEN 'Georgia' THEN 'CSEE'
            WHEN 'Uzbekistan' THEN 'CSEE'
            ELSE IFNULL(NULLIF(COALESCE(dim.market, stats_dims.business_market), ''), 'Unknown')
        END AS market,
        dim.evolution_bucket,
        dim.combined_entity_category AS category,
        dim.management_type
    FROM stats_dims
    LEFT JOIN `headout-analytics.analytics_reporting.dim_combined_entities` AS dim
        USING (combined_entity_id)
),

l92_ce AS (
    SELECT
        stats.combined_entity_id,
        SUM(stats.sum_revenue_predicted) AS l92_revenue
    FROM `headout-analytics.analytics_reporting.combined_entity_stats` AS stats, params
    WHERE stats.report_timestamp >= TIMESTAMP(DATE_SUB(week_start, INTERVAL 84 DAY))
        AND stats.report_date BETWEEN DATE_SUB(week_start, INTERVAL 84 DAY) AND cutoff
    GROUP BY 1
),

l92_by_market AS (
    SELECT
        ce_dims.market,
        COUNTIF(l92_ce.l92_revenue >= 10000) AS pro_plus_ces,
        STRING_AGG(IF(l92_ce.l92_revenue >= 10000, CAST(l92_ce.combined_entity_id AS STRING), NULL), ',') AS pro_plus_ce_ids
    FROM l92_ce
    INNER JOIN ce_dims USING (combined_entity_id)
    GROUP BY 1
    UNION ALL
    SELECT
        'Headout' AS market,
        COUNTIF(l92_ce.l92_revenue >= 10000) AS pro_plus_ces,
        STRING_AGG(IF(l92_ce.l92_revenue >= 10000, CAST(l92_ce.combined_entity_id AS STRING), NULL), ',') AS pro_plus_ce_ids
    FROM l92_ce
),

quarter_run_rate AS (
    SELECT
        stats.combined_entity_id,
        SUM(stats.sum_revenue_predicted) AS qtd_revenue,
        SUM(IF(
            stats.report_date >= GREATEST(quarter_start, DATE_SUB(cutoff, INTERVAL 27 DAY)),
            stats.sum_revenue_predicted,
            0
        )) AS l4w_revenue
    FROM `headout-analytics.analytics_reporting.combined_entity_stats` AS stats, params
    WHERE stats.report_timestamp >= TIMESTAMP(quarter_start)
        AND stats.report_timestamp <= TIMESTAMP(cutoff)
        AND stats.report_date BETWEEN quarter_start AND cutoff
    GROUP BY 1
),

prior_quarterly AS (
    SELECT
        stats.combined_entity_id,
        DATE_TRUNC(stats.report_date, QUARTER) AS quarter,
        SUM(stats.sum_revenue_predicted) AS quarter_revenue
    FROM `headout-analytics.analytics_reporting.combined_entity_stats` AS stats, params
    WHERE stats.report_timestamp >= TIMESTAMP(prior_4q_start)
        AND stats.report_timestamp <= TIMESTAMP(cutoff)
        AND stats.report_date BETWEEN prior_4q_start AND quarter_start
        AND DATE_TRUNC(stats.report_date, QUARTER) < quarter_start
    GROUP BY 1, 2
),

prior_max AS (
    SELECT
        combined_entity_id,
        MAX(quarter_revenue) AS max_prior_4q_revenue
    FROM prior_quarterly
    GROUP BY 1
),

scored AS (
    SELECT
        current_q.combined_entity_id,
        current_q.qtd_revenue,
        current_q.l4w_revenue,
        current_q.qtd_revenue
            + SAFE_DIVIDE(
                current_q.l4w_revenue,
                LEAST(28, DATE_DIFF(cutoff, quarter_start, DAY) + 1)
              )
              * DATE_DIFF(
                    DATE_SUB(DATE_ADD(quarter_start, INTERVAL 3 MONTH), INTERVAL 1 DAY),
                    cutoff,
                    DAY
                ) AS projected_quarter_revenue
    FROM quarter_run_rate AS current_q
    CROSS JOIN params
),

new_pro_plus_ce AS (
    SELECT scored.*
    FROM scored
    LEFT JOIN prior_max USING (combined_entity_id)
    WHERE IFNULL(prior_max.max_prior_4q_revenue, 0) < 10000
        AND (scored.qtd_revenue >= 10000 OR scored.projected_quarter_revenue >= 10000)
),

new_by_market AS (
    SELECT
        ce_dims.market,
        COUNTIF(ce_dims.evolution_bucket = 'Mature') AS new_pro_plus_mature_on_pace,
        COUNTIF(ce_dims.evolution_bucket = 'Mature' AND qtd_revenue >= 10000)
            AS new_pro_plus_mature_reached,
        COUNTIF(ce_dims.evolution_bucket IN ('Emerging', 'Growth'))
            AS new_pro_plus_emerging_growth_on_pace,
        COUNTIF(ce_dims.evolution_bucket IN ('Emerging', 'Growth') AND qtd_revenue >= 10000)
            AS new_pro_plus_emerging_growth_reached,
        STRING_AGG(IF(ce_dims.evolution_bucket = 'Mature', CAST(new_pro_plus_ce.combined_entity_id AS STRING), NULL), ',') AS mature_ce_ids,
        STRING_AGG(IF(ce_dims.evolution_bucket IN ('Emerging', 'Growth'), CAST(new_pro_plus_ce.combined_entity_id AS STRING), NULL), ',') AS emerging_growth_ce_ids
    FROM new_pro_plus_ce
    INNER JOIN ce_dims USING (combined_entity_id)
    GROUP BY 1
    UNION ALL
    SELECT
        'Headout' AS market,
        COUNTIF(ce_dims.evolution_bucket = 'Mature') AS new_pro_plus_mature_on_pace,
        COUNTIF(ce_dims.evolution_bucket = 'Mature' AND qtd_revenue >= 10000)
            AS new_pro_plus_mature_reached,
        COUNTIF(ce_dims.evolution_bucket IN ('Emerging', 'Growth'))
            AS new_pro_plus_emerging_growth_on_pace,
        COUNTIF(ce_dims.evolution_bucket IN ('Emerging', 'Growth') AND qtd_revenue >= 10000)
            AS new_pro_plus_emerging_growth_reached,
        STRING_AGG(IF(ce_dims.evolution_bucket = 'Mature', CAST(new_pro_plus_ce.combined_entity_id AS STRING), NULL), ',') AS mature_ce_ids,
        STRING_AGG(IF(ce_dims.evolution_bucket IN ('Emerging', 'Growth'), CAST(new_pro_plus_ce.combined_entity_id AS STRING), NULL), ',') AS emerging_growth_ce_ids
    FROM new_pro_plus_ce
    INNER JOIN ce_dims USING (combined_entity_id)
),

gel_by_market_base AS (
    SELECT
        ce_dims.market,
        SUM(IF(
            stats.report_date BETWEEN quarter_start AND cutoff,
            stats.sum_revenue_predicted,
            0
        )) AS gel_revenue_ty,
        SUM(IF(
            stats.report_date BETWEEN DATE_SUB(quarter_start, INTERVAL 1 YEAR)
                AND DATE_SUB(cutoff, INTERVAL 1 YEAR),
            stats.sum_revenue_predicted,
            0
        )) AS gel_revenue_ly
    FROM `headout-analytics.analytics_reporting.combined_entity_stats` AS stats
    INNER JOIN ce_dims USING (combined_entity_id)
    CROSS JOIN params
    WHERE stats.report_timestamp >= TIMESTAMP(DATE_SUB(quarter_start, INTERVAL 1 YEAR))
        AND stats.report_date BETWEEN DATE_SUB(quarter_start, INTERVAL 1 YEAR) AND cutoff
        AND ce_dims.evolution_bucket != 'Mature'
        AND ce_dims.category != 'POI/ Attractions'
        AND ce_dims.management_type IN ('Managed', 'Managed Lite')
    GROUP BY 1
),

gel_by_market AS (
    SELECT market, gel_revenue_ty, gel_revenue_ly
    FROM gel_by_market_base
    UNION ALL
    SELECT
        'Headout' AS market,
        SUM(gel_revenue_ty) AS gel_revenue_ty,
        SUM(gel_revenue_ly) AS gel_revenue_ly
    FROM gel_by_market_base
),

gel_candidates AS (
    SELECT
        market,
        STRING_AGG(combined_entity_id, ',' ORDER BY gel_revenue_ty DESC) AS gel_ce_ids
    FROM (
        SELECT
            ce_dims.market,
            CAST(stats.combined_entity_id AS STRING) AS combined_entity_id,
            SUM(IF(stats.report_date BETWEEN quarter_start AND cutoff, stats.sum_revenue_predicted, 0)) AS gel_revenue_ty
        FROM `headout-analytics.analytics_reporting.combined_entity_stats` AS stats
        INNER JOIN ce_dims USING (combined_entity_id)
        CROSS JOIN params
        WHERE stats.report_timestamp >= TIMESTAMP(DATE_SUB(quarter_start, INTERVAL 1 YEAR))
          AND stats.report_date BETWEEN DATE_SUB(quarter_start, INTERVAL 1 YEAR) AND cutoff
          AND ce_dims.evolution_bucket != 'Mature'
          AND ce_dims.category != 'POI/ Attractions'
          AND ce_dims.management_type IN ('Managed', 'Managed Lite')
        GROUP BY 1, 2
    )
    GROUP BY 1
)

SELECT
    requested_market AS market,
    COALESCE(l92.pro_plus_ces, 0) AS pro_plus_ces,
    l92.pro_plus_ce_ids,
    COALESCE(new_pp.new_pro_plus_mature_on_pace, 0) AS new_pro_plus_mature_on_pace,
    COALESCE(new_pp.new_pro_plus_mature_reached, 0) AS new_pro_plus_mature_reached,
    new_pp.mature_ce_ids,
    COALESCE(new_pp.new_pro_plus_emerging_growth_on_pace, 0)
        AS new_pro_plus_emerging_growth_on_pace,
    COALESCE(new_pp.new_pro_plus_emerging_growth_reached, 0)
        AS new_pro_plus_emerging_growth_reached,
    new_pp.emerging_growth_ce_ids,
    COALESCE(gel.gel_revenue_ty, 0) AS gel_revenue_ty,
    COALESCE(gel.gel_revenue_ly, 0) AS gel_revenue_ly,
    SAFE_DIVIDE(gel.gel_revenue_ty - gel.gel_revenue_ly, gel.gel_revenue_ly) * 100 AS gel_yoy_pct
    , gel_candidates.gel_ce_ids
FROM UNNEST(@markets) AS requested_market
LEFT JOIN l92_by_market AS l92 ON l92.market = requested_market
LEFT JOIN new_by_market AS new_pp ON new_pp.market = requested_market
LEFT JOIN gel_by_market AS gel ON gel.market = requested_market
LEFT JOIN gel_candidates ON gel_candidates.market = requested_market
ORDER BY 1
"""


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _money(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "—"
    if abs(number) >= 1_000_000:
        return f"${number / 1_000_000:.1f}M"
    if abs(number) >= 1_000:
        return f"${number / 1_000:.1f}K"
    return f"${number:,.0f}"


def _pct(value: Any) -> str:
    number = _number(value)
    if number is None:
        return "unavailable"
    sign = "+" if number > 0 else ("−" if number < 0 else "")
    return f"{sign}{abs(number):.1f}% YoY"


def _ce_ids(value: Any) -> list[str]:
    return [item for item in str(value or "").split(",") if item]


def _market_gel_target(slug, market_name, report_date, allocations):
    """Return only a source-evidenced target at the measured market/quarter grain."""
    if (allocations.get('schema') != 'weekly-market-okr-targets/v1'
            or allocations.get('kr_id') != OKR_IDS[3]
            or allocations.get('unit') != 'pct_yoy'):
        return None
    source = allocations.get('source') or {}
    record = (allocations.get('markets') or {}).get(slug) or {}
    quarter = f'{report_date.year}-Q{(report_date.month - 1) // 3 + 1}'
    period = (record.get('periods') or {}).get(quarter) or {}
    value = _number(period.get('value'))
    raw = str(period.get('raw', ''))
    try:
        verified = dt.date.fromisoformat(source.get('verified_on', ''))
    except (ValueError, TypeError):
        return None
    if (record.get('grain') != 'market' or record.get('source_market') != market_name
            or not source.get('url') or not source.get('tab') or not source.get('kr_cell')
            or not period.get('cell') or verified > dt.datetime.now(dt.timezone.utc).date()
            or value is None or value <= 0 or not raw.endswith('%')
            or _number(raw[:-1]) != value):
        return None
    return {'market_slug': slug, 'quarter': quarter, 'grain': 'market',
            'value': value, 'unit': 'pct_yoy', 'source': source['url'],
            'source_tab': source['tab'], 'source_cell': period['cell'],
            'source_verified_on': source['verified_on']}


def _pro_plus_status(*, slug, week_start, row, history=None):
    """Verified company stock/flow status; no market-target or missing-data fallback."""
    result = {'status': STATUS_UNAVAILABLE, 'status_reason': 'market_target_unavailable',
              'status_as_of': str(week_start + dt.timedelta(days=6)),
              'status_grain': 'company' if slug == 'headout' else 'market'}
    if slug != 'headout':
        return result
    quarter = (week_start.month - 1) // 3 + 1
    kr = row.get('id')
    target_label = COMPANY_TARGETS.get(quarter, {}).get(kr) if week_start.year == 2026 else None
    if kr not in COMPANY_PRO_TARGET_CELLS or not target_label or row.get('target') != target_label:
        return {**result, 'status_reason': 'verified_target_unavailable'}
    target = _number(target_label.removesuffix(' CEs'))
    current = _number(row.get('value'))
    drilldown = row.get('drilldown')
    ids = drilldown.get('ce_ids') if isinstance(drilldown, dict) else None
    if (current is None or current < 0 or not current.is_integer() or target is None or target <= 0
            or not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids)
            or len(ids) != len(set(ids)) or len(ids) != current):
        return {**result, 'status_reason': 'count_membership_unavailable'}
    first = dt.date(week_start.year, (quarter - 1) * 3 + 1, 1)
    end = dt.date(first.year + (quarter == 4), 1 if quarter == 4 else first.month + 3, 1) - dt.timedelta(days=1)
    if week_start + dt.timedelta(days=6) > end:
        return {**result, 'status_reason': 'quarter_boundary_unavailable'}
    weeks = []
    day = first
    while day.weekday() != 6:
        day += dt.timedelta(days=1)
    while day <= end:
        weeks.append(day)
        day += dt.timedelta(days=7)
    elapsed = sum(day <= week_start for day in weeks)
    ahead = max(0, (weeks[-1] - week_start).days // 7)
    evidence = {'status_target_value': target, 'status_target_source': COMPANY_GEL_TARGET_SOURCE['source'],
                'status_target_cell': COMPANY_PRO_TARGET_CELLS[kr][quarter],
                'status_target_verified_on': COMPANY_GEL_TARGET_SOURCE['source_verified_on'],
                'status_source': GEL_STATUS_SOURCE, 'status_weeks_elapsed': elapsed,
                'status_weeks_total': len(weeks), 'status_current_value': current}
    projected = current
    if kr == OKR_IDS[0]:
        expected = [str(week_start - dt.timedelta(weeks=i)) for i in reversed(range(6))]
        if (not isinstance(history, list) or len(history) != 6
                or any(not isinstance(r, dict) for r in history)
                or [r.get('week') for r in history] != expected):
            return {**result, 'status_reason': 'stock_history_unavailable'}
        values = [_number(r.get('value')) for r in history]
        if any(v is None or v < 0 or not v.is_integer() for v in values) or values[-1] != current:
            return {**result, 'status_reason': 'stock_history_mismatch'}
        mean = sum(values) / 6
        slope = sum((i - 2.5) * (value - mean) for i, value in enumerate(values)) / 17.5
        projected = current + slope * ahead
        evidence.update(status_rule='central-okr/stock-slope6-v1', status_slope=slope,
                        status_weeks_ahead=ahead, status_history=history)
    else:
        reached = _number(row.get('reached'))
        if reached is None or reached < 0 or not reached.is_integer() or reached > current:
            return {**result, 'status_reason': 'achieved_subset_unavailable'}
        # The canonical query's member set is already the achieved-or-projected
        # union. Do not linearly annualize this leading count or apply the final
        # quarter-end ROI quality gate to a live revenue-based outlook.
        evidence.update(status_rule='central-okr/flow-achieved-or-projected-v1',
                        status_reached=reached)
    tracking = elapsed / len(weeks) < 0.30
    return {**result, **evidence, 'status_projected_value': projected,
            'status_attainment_pct': projected / target * 100,
            'status_reason': 'early_quarter' if tracking else 'projected_finish_vs_target',
            'status': ('Tracking' if tracking else ':large_green_circle: On track' if projected >= target
                       else ':large_yellow_circle: At risk')}


def _gel_status(
    *, slug: str, year: int, week_start: dt.date, value: Any,
    target: str | None, revenue_ly: Any, approved_target: dict | None = None,
) -> dict:
    """Status-only projection; never changes the measured QTD YoY or SQL.

    Market targets require an exact, source-evidenced market/quarter allocation.
    Other KRs need their own central projection/qualification inputs. Missing
    allocations stay neutral; company/group goals never substitute for them.
    """
    evidence = {
        "status": STATUS_UNAVAILABLE,
        "status_reason": "market_target_unavailable",
        "status_as_of": str(week_start + dt.timedelta(days=6)),
        "status_grain": "market" if slug != "headout" else "company",
    }
    target_value = 100.0
    target_evidence = {}
    if slug != "headout":
        approval = approved_target or {}
        quarter = f'{year}-Q{(week_start.month - 1) // 3 + 1}'
        target_value = _number(approval.get('value'))
        if (approval.get('market_slug') != slug or approval.get('quarter') != quarter
                or approval.get('grain') != 'market' or approval.get('unit') != 'pct_yoy'
                or not approval.get('source') or not approval.get('source_cell')
                or not approval.get('source_verified_on')
                or target_value is None or target_value <= 0
                or target != f'+{target_value:g}% YoY'):
            return evidence
        target_evidence = {'status_target_source': approval['source'],
                           'status_target_cell': approval['source_cell'],
                           'status_target_verified_on': approval['source_verified_on']}
    else:
        quarter = (week_start.month - 1) // 3 + 1
        company_target = COMPANY_TARGETS.get(quarter, {}).get(OKR_IDS[3]) if year == 2026 else None
        target_value = _number((company_target or '').replace('% YoY', ''))
        if (company_target is None or target != company_target
                or target_value is None or target_value <= 0):
            return {**evidence, "status_reason": "verified_target_unavailable"}
        target_evidence = {
            'status_target_source': COMPANY_GEL_TARGET_SOURCE['source'],
            'status_target_cell': COMPANY_GEL_TARGET_SOURCE['source_cells'][quarter],
            'status_target_verified_on': COMPANY_GEL_TARGET_SOURCE['source_verified_on'],
        }
    observed, baseline = _number(value), _number(revenue_ly)
    if observed is None or baseline is None or baseline <= 0:
        return {**evidence, "status_reason": "comparison_unavailable"}
    quarter_month = (week_start.month - 1) // 3 * 3 + 1
    start = dt.date(year, quarter_month, 1)
    end = (dt.date(year + 1, 1, 1) if quarter_month == 10
           else dt.date(year, quarter_month + 3, 1))
    # Match the central engine: all Sunday starts inside the quarter, counting
    # only complete weeks through the frozen report's Sunday start.
    first_sunday = start + dt.timedelta(days=(6 - start.weekday()) % 7)
    total = ((end - dt.timedelta(days=1) - first_sunday).days // 7) + 1
    elapsed = max(0, (week_start - first_sunday).days // 7 + 1)
    tracking = elapsed / total < 0.30
    return {
        **evidence,
        "status": ("Tracking" if tracking else
                   ":large_green_circle: On track" if observed >= target_value else
                   ":large_yellow_circle: At risk"),
        "status_reason": "early_quarter" if tracking else "qtd_growth_vs_target",
        "status_rule": GEL_STATUS_RULE,
        "status_source": GEL_STATUS_SOURCE,
        "status_target_value": target_value,
        "status_attainment_pct": observed / target_value * 100,
        "status_weeks_elapsed": elapsed,
        "status_weeks_total": total,
        **target_evidence,
    }


def build_results(
    rows: Iterable[dict],
    market_names: dict[str, str],
    week_start: str,
    market_targets: dict | None = None,
) -> dict:
    """Convert one query row per market into the alert's stable sidecar contract."""
    by_market = {str(row["market"]): row for row in rows}
    report_date = dt.date.fromisoformat(week_start)
    week_end = str(report_date + dt.timedelta(days=6))
    quarter = (report_date.month - 1) // 3 + 1
    if market_targets is None:
        path = Path(__file__).with_name('okr_market_targets.json')
        market_targets = json.loads(path.read_text()) if path.is_file() else {}
    markets: dict[str, list[dict]] = {}
    for slug, market_name in market_names.items():
        if market_name not in by_market:
            raise ValueError(f"OKR query returned no row for configured market {market_name!r}")
        row = by_market[market_name]
        pro_plus = int(_number(row.get("pro_plus_ces")) or 0)
        mature = int(_number(row.get("new_pro_plus_mature_on_pace")) or 0)
        mature_reached = int(_number(row.get("new_pro_plus_mature_reached")) or 0)
        emerging = int(_number(row.get("new_pro_plus_emerging_growth_on_pace")) or 0)
        emerging_reached = int(
            _number(row.get("new_pro_plus_emerging_growth_reached")) or 0
        )
        gel_ty = _number(row.get("gel_revenue_ty")) or 0.0
        gel_ly = _number(row.get("gel_revenue_ly")) or 0.0
        gel_yoy = _number(row.get("gel_yoy_pct"))
        markets[slug] = [
            {
                "id": OKR_IDS[0],
                "label": "Grow cumulative Pro+ CEs",
                "current": f"{pro_plus} CEs",
                "detail": "L92 predicted revenue ≥ $10K",
                "value": pro_plus,
                "status": STATUS_UNAVAILABLE,
                "status_reason": "projection_rule_not_verified",
                "drilldown": {"ce_ids": _ce_ids(row.get("pro_plus_ce_ids"))},
            },
            {
                "id": OKR_IDS[1],
                "label": "Launch new Pro+ CEs — Mature",
                "current": f"{mature} on pace",
                "detail": f"{mature_reached} reached · L4W projection · new vs prior 4 quarters",
                "value": mature,
                "reached": mature_reached,
                "status": STATUS_UNAVAILABLE,
                "status_reason": "projection_rule_not_verified",
                "drilldown": {"ce_ids": _ce_ids(row.get("mature_ce_ids"))},
            },
            {
                "id": OKR_IDS[2],
                "label": "Launch new Pro+ CEs — Emerging & Growth",
                "current": f"{emerging} on pace",
                "detail": (
                    f"{emerging_reached} reached · L4W projection · new vs prior 4 quarters"
                ),
                "value": emerging,
                "reached": emerging_reached,
                "status": STATUS_UNAVAILABLE,
                "status_reason": "projection_rule_not_verified",
                "drilldown": {"ce_ids": _ce_ids(row.get("emerging_growth_ce_ids"))},
            },
            {
                "id": OKR_IDS[3],
                "label": "Grow non-POI GEL revenue YoY",
                "current": _pct(gel_yoy),
                "detail": f"{_money(gel_ty)} vs {_money(gel_ly)} QTD LY",
                "value": gel_yoy,
                "status": STATUS_UNAVAILABLE,
                "drilldown": {"ce_ids": _ce_ids(row.get("gel_ce_ids"))},
            },
        ]
        if slug == "headout":
            targets = COMPANY_TARGETS.get(quarter, {}) if report_date.year == 2026 else {}
            for result in markets[slug]:
                target = targets.get(result["id"])
                if target is not None:
                    result["target"] = target
        raw_fields = ('pro_plus_ces', 'new_pro_plus_mature_on_pace', 'new_pro_plus_emerging_growth_on_pace')
        for result, field in zip(markets[slug][:3], raw_fields):
            status_row = {**result, 'value': row.get(field)}
            if 'reached' in result:
                status_row['reached'] = row.get(field.replace('_on_pace', '_reached'))
            result.update(_pro_plus_status(slug=slug, week_start=report_date, row=status_row,
                                          history=row.get('pro_plus_status_history')))
        gel = markets[slug][3]
        approved_target = _market_gel_target(slug, market_name, report_date, market_targets)
        if approved_target is not None and slug != 'headout':
            gel['target'] = f"+{approved_target['value']:g}% YoY"
            gel['target_provenance'] = approved_target
        gel.update(_gel_status(
            slug=slug, year=report_date.year, week_start=report_date,
            value=gel_yoy, target=gel.get("target"),
            revenue_ly=row.get("gel_revenue_ly"),
            approved_target=approved_target,
        ))
    return {
        "schema_version": 1,
        "week_start": week_start,
        "week_end": week_end,
        "markets": markets,
        "_meta": {
            "source": "scripts/band_dashboards/generate_dashboards.py",
            "status_source": GEL_STATUS_SOURCE,
            "status_rule": GEL_STATUS_RULE,
            "status_policy": "Verified company stock/flow projections; GEL exact market/quarter allocations only; no company/group fallback",
            "grain": "market",
            "okr_ids": list(OKR_IDS),
            "read_only": True,
        },
    }


def query_results(week_start: str) -> tuple[list[dict], dict[str, str]]:
    sys.path.insert(0, str(REPORT_DIR))
    import config  # type: ignore
    from bq import query_df  # type: ignore

    market_names = {**config.MARKETS, "headout": "Headout"}
    df = query_df(
        MARKET_OKR_SQL,
        "market_okr_v2",
        {"week_start": week_start, "markets": list(market_names.values())},
    )
    records = df.to_dict("records")
    try:
        history = query_df(PRO_PLUS_STATUS_HISTORY_SQL, 'pro_plus_status_history',
                           {'week_start': week_start}).to_dict('records')
    except Exception as exc:
        # Optional status evidence must not replace existing measurements or
        # silently invent a flat history after a failed read.
        print(f'Pro+ status history unavailable ({type(exc).__name__}); stock badge stays unavailable',
              file=sys.stderr)
        history = None
    for row in records:
        if row['market'] == 'Headout':
            row['pro_plus_status_history'] = history
    return records, market_names


def main() -> None:
    parser = argparse.ArgumentParser(description="Build market-level V2 OKR results")
    parser.add_argument("--week-start", required=True, help="Sunday report week YYYY-MM-DD")
    parser.add_argument("--out", default="okr_results_weekly_v2.json")
    parser.add_argument("--print-sql", action="store_true", help="Print parameterized SQL and exit")
    args = parser.parse_args()

    if args.print_sql:
        print(MARKET_OKR_SQL)
        return

    rows, market_names = query_results(args.week_start)
    payload = build_results(rows, market_names, args.week_start)
    Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✓ wrote {args.out} · {len(payload['markets'])} market OKR slices")


if __name__ == "__main__":
    main()
