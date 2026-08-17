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

# Current H2 2026 official statuses from the authoritative central OKR engine.
# These are company KR statuses displayed beside market-grain evidence; they are
# not inferred from company targets or recomputed per market.
OFFICIAL_STATUS = {
    "grow_cumulative_pro_plus_ces": ":large_yellow_circle: At risk",
    "launch_new_pro_plus_mature": ":large_yellow_circle: At risk",
    "launch_new_pro_plus_emerging_growth": ":large_yellow_circle: At risk",
    "grow_non_poi_gel_revenue_yoy": ":large_green_circle: On track",
}


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
        COUNTIF(l92_ce.l92_revenue >= 10000) AS pro_plus_ces
    FROM l92_ce
    INNER JOIN ce_dims USING (combined_entity_id)
    GROUP BY 1
    UNION ALL
    SELECT
        'Headout' AS market,
        COUNTIF(l92_ce.l92_revenue >= 10000) AS pro_plus_ces
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
            AS new_pro_plus_emerging_growth_reached
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
            AS new_pro_plus_emerging_growth_reached
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
)

SELECT
    requested_market AS market,
    COALESCE(l92.pro_plus_ces, 0) AS pro_plus_ces,
    COALESCE(new_pp.new_pro_plus_mature_on_pace, 0) AS new_pro_plus_mature_on_pace,
    COALESCE(new_pp.new_pro_plus_mature_reached, 0) AS new_pro_plus_mature_reached,
    COALESCE(new_pp.new_pro_plus_emerging_growth_on_pace, 0)
        AS new_pro_plus_emerging_growth_on_pace,
    COALESCE(new_pp.new_pro_plus_emerging_growth_reached, 0)
        AS new_pro_plus_emerging_growth_reached,
    COALESCE(gel.gel_revenue_ty, 0) AS gel_revenue_ty,
    COALESCE(gel.gel_revenue_ly, 0) AS gel_revenue_ly,
    SAFE_DIVIDE(gel.gel_revenue_ty - gel.gel_revenue_ly, gel.gel_revenue_ly) * 100 AS gel_yoy_pct
FROM UNNEST(@markets) AS requested_market
LEFT JOIN l92_by_market AS l92 ON l92.market = requested_market
LEFT JOIN new_by_market AS new_pp ON new_pp.market = requested_market
LEFT JOIN gel_by_market AS gel ON gel.market = requested_market
ORDER BY 1
"""


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
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


def build_results(
    rows: Iterable[dict],
    market_names: dict[str, str],
    week_start: str,
) -> dict:
    """Convert one query row per market into the alert's stable sidecar contract."""
    by_market = {str(row["market"]): row for row in rows}
    week_end = str(dt.date.fromisoformat(week_start) + dt.timedelta(days=6))
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
                "status": OFFICIAL_STATUS[OKR_IDS[0]],
            },
            {
                "id": OKR_IDS[1],
                "label": "Launch new Pro+ CEs — Mature",
                "current": f"{mature} on pace",
                "detail": f"{mature_reached} reached · L4W projection · new vs prior 4 quarters",
                "value": mature,
                "reached": mature_reached,
                "status": OFFICIAL_STATUS[OKR_IDS[1]],
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
                "status": OFFICIAL_STATUS[OKR_IDS[2]],
            },
            {
                "id": OKR_IDS[3],
                "label": "Grow non-POI GEL revenue YoY",
                "current": _pct(gel_yoy),
                "detail": f"{_money(gel_ty)} vs {_money(gel_ly)} QTD LY",
                "value": gel_yoy,
                "status": OFFICIAL_STATUS[OKR_IDS[3]],
            },
        ]
    return {
        "schema_version": 1,
        "week_start": week_start,
        "week_end": week_end,
        "markets": markets,
        "_meta": {
            "source": "scripts/band_dashboards/generate_dashboards.py",
            "status_source": "H2 2026 official_status in central OKR engine",
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
    return df.to_dict("records"), market_names


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
