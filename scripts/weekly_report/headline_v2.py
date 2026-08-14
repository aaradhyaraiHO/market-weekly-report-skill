"""Pure view-model helpers for the Weekly Report V2 market headline.

The V2 headline deliberately consumes the existing schema-v1 snapshot.  It
does not mutate the snapshot or reimplement any production bucket logic.
Monthly goal data is optional and must come from an explicit sidecar.
"""
from __future__ import annotations

import datetime as dt
from statistics import fmean


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


def build_headline_view(market, goal=None):
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
    metrics = headlines.get("key_metrics", {})
    revenue = _number(headlines.get("revenue_w0"))
    if revenue is None:
        revenue = _number(current.get("revenue"))
    previous_revenue = _number(previous.get("revenue"))
    wow_abs = revenue - previous_revenue if revenue is not None and previous_revenue is not None else None
    wow_pct = _number(headlines.get("wow_pct"))
    if wow_pct is None:
        wow_pct = _percent_change(revenue, previous_revenue)

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
            yoy = _number(headlines.get("yoy_pct"))
            if yoy is not None and yoy != -100:
                ly = row["revenue"] / (1.0 + yoy / 100.0)
        chart.append({"week": row.get("week"), "revenue": row["revenue"], "revenue_ly": ly})

    return {
        "market": meta.get("market", "Unknown market"),
        "market_slug": meta.get("market_slug"),
        "week_start": meta.get("week_start"),
        "week_end": meta.get("week_end"),
        "revenue": revenue,
        "wow_abs": wow_abs,
        "wow_pct": wow_pct,
        "vs_trailing_four_pct": _percent_change(revenue, trailing_four),
        "trailing_four_revenue": trailing_four,
        "yoy_pct": _number(headlines.get("yoy_pct")),
        "paid_roi_pct": paid_roi_w0,
        "paid_roi_delta_pp": paid_roi_delta_pp,
        "monthly": monthly,
        "chart": chart,
    }


def build_headline_payload(markets, goals=None):
    goals = goals or {}
    return [build_headline_view(market, goals.get(market.get("meta", {}).get("market_slug"))) for market in markets]
