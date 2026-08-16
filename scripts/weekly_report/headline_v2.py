"""Pure view-model helpers for the Weekly Report V2 market headline.

The V2 headline deliberately consumes the existing schema-v1 snapshot.  It
does not mutate the snapshot or reimplement any production bucket logic.
Monthly goal data is optional and must come from an explicit sidecar.
"""
from __future__ import annotations

import datetime as dt
from copy import deepcopy
from statistics import fmean


_METRIC_SPECS = (
    ("revenue", "Revenue", "money", "revenue"),
    ("gbv", "GBV", "money", "gbv"),
    ("orders", "Orders", "count", "orders"),
    ("aov", "AOV", "money", "aov"),
    ("cr_pct", "CR", "pct", "cr_pct"),
    ("tr_pct", "TR", "pct", "tr_pct"),
    ("paid_clicks", "Paid clicks", "count", "paid_clicks"),
    ("paid_cvr", "Paid CVR", "pct", "paid_cvr_pct"),
    ("paid_conv_value", "Paid conversion value", "money", "paid_conv_value"),
    ("avg_cm1", "Average CM1", "money", "avg_cm1"),
    ("paid_roi", "Paid ROI", "pct", "roi_pct"),
    ("roi1", "ROI 1", "pct", "roi1_pct"),
)

_SHAPLEY_LABELS = {
    "traffic": "Traffic",
    "cvr": "CVR",
    "aov": "AOV",
    "cr": "Completion",
    "tr": "Take rate",
}

_PAID_METRICS = frozenset({"paid_clicks", "paid_cvr", "paid_conv_value", "avg_cm1", "paid_roi"})

_CE_PERIOD_FIELDS = (
    "revenue", "orders", "aov", "tr_pct", "cr_pct", "clicks", "paid_clicks",
    "cvr_pct", "paid_cvr_pct", "cpc", "paid_rpc", "spend", "cm1", "paid_cm2",
    "roi_pct", "coupon_wallet", "gbv", "gbv_completed", "ad_conversions",
    "organic_gbv", "paid_revenue", "overall_cvr_pct", "paid_ctr_pct",
    "paid_sis_pct", "paid_conversions", "cm2", "cm1_per_conv", "roi1_pct",
)

_CE_DRAWER_METRICS = {
    "overall": (
        ("revenue", "Revenue", "money"), ("gbv", "GBV", "money"),
        ("orders", "Orders", "count"), ("funnel_cvr_pct", "LP→Order CVR", "pct"),
        ("aov", "AOV", "money"), ("tr_pct", "TR", "pct"),
        ("cm2", "CM2", "money"), ("cr_pct", "CR", "pct"),
        ("roi1_pct", "ROI 1", "pct"),
    ),
    "paid": (
        ("paid_clicks", "Paid clicks", "count"),
        ("paid_ctr_pct", "Paid CTR", "pct"),
        ("paid_sis_pct", "Paid SIS · Google", "pct"),
        ("spend", "Paid ads spend", "money"), ("cpc", "Paid CPC", "cpc"),
        ("paid_rpc", "Paid RPC", "cpc"),
        ("paid_conversions", "Paid conversions", "count"),
        ("paid_cvr_pct", "Paid CVR", "pct"), ("cm1", "Paid CM1", "money"),
        ("paid_cm2", "Paid CM2", "money"), ("roi_pct", "Paid ROI", "pct"),
        ("cm1_per_conv", "Paid average CM1", "money"),
    ),
}


def _number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _percent_change(current, baseline):
    if current is None or baseline in (None, 0):
        return None
    return 100.0 * (current / baseline - 1.0)


def _goal_state(goal, week_end):
    if not isinstance(goal, dict):
        return "missing"
    required = ("month", "monthly_goal", "mtd_revenue", "forecast_revenue", "as_of")
    if any(goal.get(key) in (None, "") for key in required):
        return "missing"
    if goal.get("status") == "stale":
        return "stale"
    try:
        as_of = dt.date.fromisoformat(str(goal["as_of"]))
        report_end = dt.date.fromisoformat(str(week_end))
    except ValueError:
        return "stale"
    return "current" if as_of >= report_end else "stale"


def _metric_views(headlines, rows, weekly_ly):
    metrics = headlines.get("key_metrics", {})
    ly_by_week = {row.get("week"): row for row in weekly_ly}

    def row_value(row, field):
        value = _number(row.get(field))
        if value is None and field == "avg_cm1":
            cm1 = _number(row.get("cm1"))
            conversions = _number(row.get("paid_conversions"))
            if cm1 is not None and conversions not in (None, 0):
                value = cm1 / conversions
        return value

    views = []
    for key, default_label, value_format, weekly_field in _METRIC_SPECS:
        metric = metrics.get(key)
        if not isinstance(metric, dict):
            # V1's market drawer backfills these three fields for snapshots that
            # predate the complete key_metrics block. Keep the same fallback,
            # but build a view instead of mutating the source snapshot.
            if key not in {"orders", "aov", "avg_cm1"} or not rows:
                continue
            w0 = row_value(rows[-1], weekly_field)
            wm1 = row_value(rows[-2], weekly_field) if len(rows) > 1 else None
            if w0 is None:
                continue
            metric = {
                "label": default_label,
                "w0": w0,
                "wm1": wm1,
                "delta_abs": w0 - wm1 if wm1 is not None else None,
                "delta_pct": _percent_change(w0, wm1),
                "has_ly": True,
            }
        series = []
        for row in rows[-12:]:
            ly_row = ly_by_week.get(row.get("week"), {})
            series.append({
                "week": row.get("week"),
                "ty": row_value(row, weekly_field),
                "ly": row_value(ly_row, weekly_field),
            })
        views.append({
            "key": key,
            "label": metric.get("label") or default_label,
            "format": value_format,
            "paid": key in _PAID_METRICS,
            "has_ly": metric.get("has_ly") is not False and any(row["ly"] is not None for row in series),
            "w0": _number(metric.get("w0")),
            "wm1": _number(metric.get("wm1")),
            "delta_abs": _number(metric.get("delta_abs")),
            "delta_pct": _number(metric.get("delta_pct")),
            "series": series,
        })
    return views


def _mover_views(headlines, direction):
    trend = (headlines.get("week_header") or {}).get("trend") or {}
    rich_key = "top_droppers" if direction == "drop" else "top_gainers"
    fallback_key = "top_drops" if direction == "drop" else "top_gainers"
    rich_source = trend.get(rich_key)
    source = rich_source or headlines.get(fallback_key) or []
    source_path = (
        f"market_summary.headlines.week_header.trend.{rich_key}"
        if rich_source
        else f"market_summary.headlines.{fallback_key}"
    )
    ranking_method = (
        "V1 dual-lens ranking: the larger directional movement across WoW and trailing 4-week average"
        if rich_source
        else "V1 raw WoW revenue ranking"
    )
    result = []
    for rank, row in enumerate(source, start=1):
        delta_4w = _number(row.get("delta_4w"))
        wow_abs = _number(row.get("raw_wow"))
        if wow_abs is None:
            wow_abs = _number(row.get("delta_wow"))
        candidates = [(delta_4w, "vs trailing 4w"), (wow_abs, "vs last week")]
        candidates = [(value, lens) for value, lens in candidates if value is not None]
        if direction == "drop":
            candidates = [(value, lens) for value, lens in candidates if value < 0]
            primary = min(candidates, default=(wow_abs or delta_4w, "movement"), key=lambda item: item[0])
        else:
            candidates = [(value, lens) for value, lens in candidates if value > 0]
            primary = max(candidates, default=(wow_abs or delta_4w, "movement"), key=lambda item: item[0])
        result.append({
            "ce_id": row.get("ce_id"),
            "ce_name": row.get("ce_name") or "Unnamed experience",
            "primary_delta": _number(primary[0]),
            "primary_lens": primary[1],
            "delta_4w": delta_4w,
            "wow_abs": wow_abs,
            "ly_wow": _number(row.get("ly_wow")),
            "revenue": _number(row.get("w0_rev")),
            "yoy_growth": _number(row.get("yoy_growth")),
            "tag": row.get("tag"),
            # The V1 flow engine owns the seasonal classification. V2 must not
            # reproduce that threshold logic or silently change its verdict.
            "seasonality_tag": row.get("tag") if rich_source else "no LY",
            "source_rank": rank,
            "source_path": source_path,
            "ranking_method": ranking_method,
        })
    return result


def _shapley_view(headlines):
    source = headlines.get("shapley_wow")
    if not isinstance(source, dict):
        return None
    factors = [
        {"key": key, "label": label, "value": _number(source.get(key))}
        for key, label in _SHAPLEY_LABELS.items()
        if _number(source.get(key)) is not None
    ]
    return {
        "factors": factors,
        "net_delta": _number(source.get("net_delta")) if _number(source.get("net_delta")) is not None else _number(source.get("total")),
        "reconstructs": source.get("reconstructs") is True,
    }


def _ce_bucket_memberships(market):
    """Project current buckets_final membership without changing bucket logic."""
    memberships = {}

    def add(rows, key, label, family):
        for row in rows or []:
            ce_id = row.get("ce_id") if isinstance(row, dict) else None
            if ce_id is None:
                continue
            memberships.setdefault(str(ce_id), []).append({
                "key": key,
                "label": label,
                "family": family,
            })

    final = market.get("buckets_final") or {}
    defend = final.get("defend") or {}
    compound = final.get("compound") or {}
    lifecycle = final.get("lifecycle") or {}
    losing = defend.get("losing_money") or {}
    add(losing.get("existing"), "losing_money", "Losing Money", "Defend")
    add(losing.get("new"), "losing_money", "Losing Money", "Defend")
    add(defend.get("seasonality_down"), "fluct_down", "RPC Fluctuations ↓", "Defend")
    add(compound.get("scale_up"), "scale_up", "Scale-Up", "Compound")
    add(compound.get("seasonality_up"), "fluct_up", "RPC Fluctuations ↑", "Compound")
    add(lifecycle.get("new_ces"), "new_ces", "New CEs", "Lifecycle")
    add(lifecycle.get("iteration"), "iteration", "Iteration", "Lifecycle")
    return memberships


def _ce_period(row):
    row = row if isinstance(row, dict) else {}
    return {key: _number(row.get(key)) for key in _CE_PERIOD_FIELDS}


def _ce_drawer_metrics(weekly, weekly_ly, funnel=None):
    current = weekly[-1] if weekly else {}
    previous = weekly[-2] if len(weekly) > 1 else {}
    ly_by_week = {row.get("week"): row for row in weekly_ly}
    funnel_cvr = (funnel or {}).get("CVR") or {}
    result = {}
    for group, specs in _CE_DRAWER_METRICS.items():
        rows = []
        for key, label, value_format in specs:
            if key == "funnel_cvr_pct":
                rows.append({
                    "key": key,
                    "label": label,
                    "format": value_format,
                    "w0": _number(funnel_cvr.get("current")),
                    "wm1": _number(funnel_cvr.get("wm1")),
                    "delta_pct": _number(funnel_cvr.get("wow")),
                    "delta_kind": "pp",
                    # The live funnel query supplies W0/W-1/LY, not 12 weeks.
                    # An empty series is an explicit unavailable state.
                    "series": [],
                })
                continue
            series = [
                {
                    "week": row.get("week"),
                    "ty": _number(row.get(key)),
                    "ly": _number(ly_by_week.get(row.get("week"), {}).get(key)),
                }
                for row in weekly[-12:]
            ]
            rows.append({
                "key": key,
                "label": label,
                "format": value_format,
                "w0": _number(current.get(key)),
                "wm1": _number(previous.get(key)),
                "delta_pct": _percent_change(_number(current.get(key)), _number(previous.get(key))),
                "delta_kind": "pct",
                "series": series,
            })
        result[group] = rows
    return result


def _ce_views(market, dimensions=None):
    dimensions = dimensions or {}
    bucket_memberships = _ce_bucket_memberships(market)
    views = []
    for ce in market.get("ces", []):
        weekly = [row for row in (ce.get("weekly") or []) if isinstance(row, dict)]
        weekly.sort(key=lambda row: row.get("week", ""))
        weekly_ly_rows = [row for row in (ce.get("weekly_ly") or []) if isinstance(row, dict)]
        weekly_ly = {
            row.get("week"): row
            for row in weekly_ly_rows
        }
        current = weekly[-1] if weekly else {}
        previous = weekly[-2] if len(weekly) > 1 else {}
        revenue = _number(current.get("revenue"))
        previous_revenue = _number(previous.get("revenue"))
        countries = sorted({
            row.get("country")
            for row in (ce.get("countries") or [])
            if row.get("country")
        })
        metadata = ce.get("metadata") or {}
        ce_dimensions = dimensions.get(str(ce.get("ce_id")), {})
        ly = weekly_ly_rows[-1] if weekly_ly_rows else {}
        views.append({
            "ce_id": ce.get("ce_id"),
            "ce_name": ce.get("ce_name") or "Unnamed experience",
            "city": metadata.get("city"),
            "category": metadata.get("category"),
            "subcategory": metadata.get("subcategory"),
            "management_type": metadata.get("management_type"),
            "growth_stage": metadata.get("evolution"),
            "lifecycle": metadata.get("new_vs_existing"),
            "tier": metadata.get("tier"),
            "countries": countries,
            "bdm_region": ce_dimensions.get("bdm_region"),
            "growth_region": ce_dimensions.get("growth_region"),
            "revenue": revenue,
            "wow_abs": revenue - previous_revenue if revenue is not None and previous_revenue is not None else None,
            "wow_pct": _percent_change(revenue, previous_revenue),
            "yoy_pct": _number(current.get("yoy_pct")),
            "orders": _number(current.get("orders")),
            "aov": _number(current.get("aov")),
            "rpc": _number(current.get("paid_rpc")),
            "cm1_per_conv": _number(current.get("cm1_per_conv")),
            "roi_pct": _number(current.get("roi_pct")),
            "periods": {
                "w0": _ce_period(current),
                "w1": _ce_period(previous),
                "ly": _ce_period(ly),
            },
            "buckets": bucket_memberships.get(str(ce.get("ce_id")), []),
            "chart": [
                {
                    "week": row.get("week"),
                    "revenue": _number(row.get("revenue")),
                    "revenue_ly": _number(weekly_ly.get(row.get("week"), {}).get("revenue")),
                }
                for row in weekly[-12:]
            ],
            "drawer_metrics": _ce_drawer_metrics(weekly, weekly_ly_rows, ce.get("funnel")),
            "shapley": deepcopy(ce.get("shapley_wow")) if isinstance(ce.get("shapley_wow"), dict) else None,
            "channels": deepcopy(ce.get("channels") or []),
            "funnel": deepcopy(ce.get("funnel") or {}),
            "tgids": deepcopy(ce.get("tgids") or []),
            "leadtime": deepcopy(ce.get("leadtime") or []),
            "country_mix": [
                {
                    "country": row.get("country"),
                    "orders": _number(row.get("orders")),
                    "orders_wow": _number(row.get("orders_wow")),
                    "orders_yoy": _number(row.get("orders_yoy")),
                    "revenue": _number(row.get("rev")),
                    "revenue_wm1": _number(row.get("rev_wm1")),
                    "revenue_wow": _number(row.get("rev_wow")),
                    "revenue_yoy": _number(row.get("rev_yoy")),
                    "share_pct": _number(row.get("rev_share_pct")),
                    "aov": _number(row.get("aov")),
                    "aov_wm1": _number(row.get("aov_wm1")),
                    "aov_ly": _number(row.get("aov_ly")),
                }
                for row in (ce.get("countries") or [])
                if row.get("country")
            ],
        })
    return views


def build_headline_view(market, goal=None, ce_dimensions=None):
    """Return the V2 headline projection without changing the source market."""
    meta = market.get("meta", {})
    summary = market.get("market_summary", {})
    rows = [row for row in summary.get("weekly", []) if _number(row.get("revenue")) is not None]
    rows.sort(key=lambda row: row.get("week", ""))
    current = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) > 1 else {}
    prior_four = [_number(row.get("revenue")) for row in rows[-5:-1]]
    trailing_four = fmean(prior_four) if prior_four else None

    headlines = summary.get("headlines", {})
    week_header = headlines.get("week_header") or {}
    engine_raw = week_header.get("raw") if isinstance(week_header.get("raw"), dict) else {}
    metrics = headlines.get("key_metrics", {})
    revenue = _number(headlines.get("revenue_w0"))
    if revenue is None:
        revenue = _number(engine_raw.get("revenue_w0"))
    if revenue is None:
        revenue = _number(current.get("revenue"))
    previous_revenue = _number(previous.get("revenue"))
    wow_abs = revenue - previous_revenue if revenue is not None and previous_revenue is not None else None
    wow_pct = _number(headlines.get("wow_pct"))
    if wow_pct is None:
        wow_pct = _number(engine_raw.get("wow_pct"))
    if wow_pct is None:
        wow_pct = _percent_change(revenue, previous_revenue)
    yoy_pct = _number(headlines.get("yoy_pct"))
    if yoy_pct is None:
        yoy_pct = _number(engine_raw.get("yoy_pct"))

    paid_roi = metrics.get("paid_roi", {})
    paid_roi_w0 = _number(paid_roi.get("w0"))
    if paid_roi_w0 is None:
        paid_roi_w0 = _number(headlines.get("roi_w0_pct"))
    paid_roi_delta_pp = _number(paid_roi.get("delta_abs"))
    if paid_roi_delta_pp is None:
        paid_roi_delta_pp = (
            paid_roi_w0 - paid_roi["wm1"]
            if paid_roi_w0 is not None and _number(paid_roi.get("wm1")) is not None
            else None
        )

    state = _goal_state(goal, meta.get("week_end"))
    monthly = {"state": state}
    if isinstance(goal, dict) and state != "missing":
        monthly.update({key: goal.get(key) for key in (
            "month", "monthly_goal", "mtd_revenue", "forecast_revenue", "as_of", "source",
            "yoy_pct", "mom_pct", "prior_forecast_attainment_pct",
            "expected_mtd_method", "expected_mtd_share_pct", "days_in_month", "elapsed_days", "remaining_days",
            "expected_mtd_revenue", "mtd_gap", "mtd_pacing_pct", "forecast_gap",
            "forecast_gap_pct", "forecast_baseline_revenue", "forecast_remaining_revenue",
            "forecast_remaining_share_pct", "required_weekly_revenue", "current_week_revenue", "run_rate_weekly_revenue",
            "prior_month_revenue", "prior_mtd_revenue", "ly_month_revenue", "ly_mtd_revenue",
            "mtd_vs_last_month_pct", "mtd_vs_last_year_pct", "forecast_vs_last_month_pct",
            "forecast_vs_last_year_pct", "ce_target_coverage_pct", "ce_gap_contributors",
            "goal_grain", "goal_row_count", "forecast_method",
            "retrieved_at",
        )})
        attainment = _number(goal.get("forecast_attainment_pct"))
        if attainment is None:
            attainment = _percent_change(goal.get("forecast_revenue"), goal.get("monthly_goal"))
            if attainment is not None:
                attainment += 100.0
        monthly["forecast_attainment_pct"] = attainment
        monthly["mtd_attainment_pct"] = (
            100.0 * goal["mtd_revenue"] / goal["monthly_goal"] if goal.get("monthly_goal") else None
        )

    weekly_ly = summary.get("weekly_ly", [])
    ly_by_week = {row.get("week"): _number(row.get("revenue")) for row in weekly_ly}
    chart = []
    for row in rows[-12:]:
        ly = ly_by_week.get(row.get("week"))
        if ly is None and row is current:
            yoy = yoy_pct
            if yoy is not None and yoy != -100:
                ly = row["revenue"] / (1.0 + yoy / 100.0)
        chart.append({"week": row.get("week"), "revenue": row["revenue"], "revenue_ly": ly})

    return {
        "market": meta.get("market", "Unknown market"),
        "market_slug": meta.get("market_slug"),
        "week_start": meta.get("week_start"),
        "week_end": meta.get("week_end"),
        "ce_cap": meta.get("ce_cap"),
        "revenue": revenue,
        "wow_abs": wow_abs,
        "wow_pct": wow_pct,
        "vs_trailing_four_pct": _percent_change(revenue, trailing_four),
        "trailing_four_revenue": trailing_four,
        "yoy_pct": yoy_pct,
        "paid_roi_pct": paid_roi_w0,
        "paid_roi_delta_pp": paid_roi_delta_pp,
        "monthly": monthly,
        "chart": chart,
        "movers": {
            "drops": _mover_views(headlines, "drop"),
            "gains": _mover_views(headlines, "gain"),
        },
        "detail": {
            "metrics": _metric_views(headlines, rows, weekly_ly),
            "shapley": _shapley_view(headlines),
        },
        "all_ces": _ce_views(market, ce_dimensions),
    }


def build_headline_payload(markets, goals=None, ce_dimensions=None):
    goals = goals or {}
    ce_dimensions = ce_dimensions or {}
    return [
        build_headline_view(
            market,
            goals.get(market.get("meta", {}).get("market_slug")),
            ce_dimensions.get(market.get("meta", {}).get("market_slug")),
        )
        for market in markets
    ]
