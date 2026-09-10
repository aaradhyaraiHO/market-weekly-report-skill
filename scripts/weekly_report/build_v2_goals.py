#!/usr/bin/env python3
"""Build the frozen monthly-goals sidecar consumed by the V2 renderer.

This command only reads BigQuery and writes a local JSON artifact. It does not
render, publish, post to Slack, update Sheets, or modify a weekly snapshot.
"""
from __future__ import annotations

import argparse
import calendar
import copy
import datetime as dt
import json
import math
import os
from pathlib import Path

import fetch
import render

WEEKS_TO_MONTH = 4.345


def _number(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_row(frame):
    if frame is None or frame.empty:
        return {}
    return frame.iloc[0].to_dict()


def _percent_change(current, baseline):
    if current is None or baseline in (None, 0):
        return None
    return 100.0 * (current / baseline - 1.0)


def merge_headout_ce_targets(headout_goal, market_goals):
    """Attach the same-month market CE targets to the global Headout goal.

    Headout's approved monthly target is company-grain, while CE targets remain
    market-grain in ``revenue_goals``.  Keep those authorities separate: this
    function preserves every Headout monthly field and only builds the CE lookup
    used by global movers. Conflicting duplicate stable IDs are omitted rather
    than assigned to an arbitrary market.
    """
    if not isinstance(headout_goal, dict):
        return headout_goal

    # A fresh unfiltered Headout query already carries the company-wide CE
    # target lookup. Do not replace it with a partial/stale market-sidecar union
    # (or an empty union when Headout is generated on its own).
    if headout_goal.get('scope') == 'all markets' and isinstance(headout_goal.get('ce_target_pacing'), dict):
        return copy.deepcopy(headout_goal)

    month = headout_goal.get("month")
    merged = {}
    conflicts = set()
    for slug, goal in sorted((market_goals or {}).items()):
        if slug == "headout" or not isinstance(goal, dict) or goal.get("month") != month:
            continue
        for raw_ce_id, raw_pacing in (goal.get("ce_target_pacing") or {}).items():
            if not isinstance(raw_pacing, dict):
                continue
            ce_id = str(raw_ce_id)
            pacing = copy.deepcopy(raw_pacing)
            pacing["source_market_slug"] = slug
            existing = merged.get(ce_id)
            if existing is None:
                merged[ce_id] = pacing
                continue
            comparable_existing = {
                key: value for key, value in existing.items() if key != "source_market_slug"
            }
            comparable_new = {
                key: value for key, value in pacing.items() if key != "source_market_slug"
            }
            if comparable_existing != comparable_new:
                conflicts.add(ce_id)

    for ce_id in conflicts:
        merged.pop(ce_id, None)

    result = copy.deepcopy(headout_goal)
    result["ce_target_pacing"] = merged
    result["ce_target_row_count"] = len(merged)
    result["ce_target_conflict_count"] = len(conflicts)
    result["ce_target_source"] = "Same-month market CE target union keyed by stable CE ID"
    target_total = sum(_number(row.get("monthly_goal")) or 0.0 for row in merged.values())
    monthly_goal = _number(result.get("monthly_goal"))
    result["ce_target_coverage_pct"] = (
        100.0 * target_total / monthly_goal if monthly_goal else None
    )
    result["ce_gap_contributors"] = sorted(
        (
            row for row in merged.values()
            if (_number(row.get("mtd_gap")) or 0.0) < 0
        ),
        key=lambda row: _number(row.get("mtd_gap")) or 0.0,
    )[:5]
    return result


def _weekly_rows(market):
    rows = market.get("market_summary", {}).get("weekly", [])
    return sorted(rows, key=lambda row: row.get("week", ""))


def _current_week_revenue(market):
    week_start = market.get("meta", {}).get("week_start")
    rows = _weekly_rows(market)
    row = next((item for item in rows if item.get("week") == week_start), rows[-1] if rows else {})
    return _number(row.get("revenue"))


def _trailing_weekly_average(market, end_offset=0, weeks=4, as_of=None):
    rows = _weekly_rows(market)
    if as_of is not None:
        rows = [row for row in rows if dt.date.fromisoformat(row['week']) + dt.timedelta(days=6) <= as_of]
    if end_offset:
        rows = rows[:-end_offset]
    values = [_number(row.get("revenue")) for row in rows[-weeks:]]
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def build_market_goal(market, as_of=None):
    meta = market.get("meta", {})
    market_name = meta.get("market")
    market_slug = meta.get("market_slug")
    week_end = dt.date.fromisoformat(meta["week_end"])
    month = week_end.replace(day=1)
    # Headout is the whole business, never a literal warehouse market filter.
    query_market = None if market_slug == "headout" else market_name
    cutoff = min(week_end, as_of or (dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)))
    if cutoff < month:
        raise RuntimeError("No completed days in the target month yet")
    week_end = cutoff

    goal_row = _first_row(fetch.market_monthly_goal(query_market, month))
    market_goal = _number(goal_row.get("market_goal"))
    ce_goal = _number(goal_row.get("ce_goal"))
    market_rows = int(goal_row.get("market_row_count") or 0)
    ce_rows = int(goal_row.get("ce_row_count") or 0)
    if market_rows and market_goal is not None:
        monthly_goal = market_goal
        goal_grain = "Market"
    elif market_slug != "headout" and ce_rows and ce_goal is not None:
        monthly_goal = ce_goal
        goal_grain = "Combined Entity roll-up"
    else:
        raise RuntimeError(f"No approved monthly target for {market_name} in {month:%Y-%m}")

    revenue_row = _first_row(fetch.market_period_revenue(query_market, month, week_end))
    mtd_revenue = _number(revenue_row.get("revenue"))
    current_revenue = _current_week_revenue(market)
    if mtd_revenue is None or current_revenue is None:
        raise RuntimeError(f"Missing canonical revenue inputs for {market_name}")

    run_rate_weekly_revenue = _trailing_weekly_average(market, as_of=cutoff)
    if run_rate_weekly_revenue is None:
        raise RuntimeError(f"Missing trailing weekly revenue for {market_name}")
    run_rate_monthly_revenue = run_rate_weekly_revenue * WEEKS_TO_MONTH
    days_in_month = calendar.monthrange(month.year, month.month)[1]
    elapsed_days = min(week_end.day, days_in_month)
    remaining_days = max(0, days_in_month - elapsed_days)

    prior_end = month - dt.timedelta(days=1)
    prior_start = prior_end.replace(day=1)
    prior_mtd_end = prior_start.replace(day=min(elapsed_days, prior_end.day))
    ly_start = month.replace(year=month.year - 1)
    ly_end = ly_start.replace(day=calendar.monthrange(ly_start.year, ly_start.month)[1])
    ly_mtd_end = ly_start.replace(day=min(elapsed_days, ly_end.day))
    comparisons = _first_row(fetch.market_month_comparisons(
        query_market, prior_start, prior_mtd_end, prior_end, ly_start, ly_mtd_end, ly_end
    ))
    prior_month_revenue = _number(comparisons.get("prior_month_revenue"))
    prior_mtd_revenue = _number(comparisons.get("prior_mtd_revenue"))
    ly_month_revenue = _number(comparisons.get("ly_month_revenue"))
    ly_mtd_revenue = _number(comparisons.get("ly_mtd_revenue"))
    expected_mtd_share = elapsed_days / days_in_month
    expected_mtd_method = "calendar-linear target pacing"
    remaining_month_share = max(0.0, 1.0 - expected_mtd_share) if remaining_days else 0.0
    # Forecast the unelapsed calendar days at the observed trailing-four-week
    # daily pace. Do not prorate a synthetic 4.345-week month: that makes the
    # displayed "actual MTD + recent pace" method disagree with its numbers.
    forecast_remaining_revenue = run_rate_weekly_revenue * remaining_days / 7.0
    forecast_revenue = mtd_revenue + forecast_remaining_revenue
    expected_mtd_revenue = monthly_goal * expected_mtd_share
    mtd_gap = mtd_revenue - expected_mtd_revenue
    forecast_gap = forecast_revenue - monthly_goal
    required_revenue = max(0.0, monthly_goal - mtd_revenue)
    required_weekly_revenue = (
        required_revenue / remaining_days * 7.0 if remaining_days else required_revenue
    )

    ce_revenue = {
        str(row.get("ce_id")): _number(row.get("revenue")) or 0.0
        for row in fetch.market_ce_period_revenue(query_market, month, week_end).to_dict("records")
    }
    ce_prior_mtd_revenue = {
        str(row.get("ce_id")): _number(row.get("revenue")) or 0.0
        for row in fetch.market_ce_period_revenue(
            query_market, prior_start, prior_mtd_end
        ).to_dict("records")
    }
    ce_prior_month_revenue = {
        str(row.get("ce_id")): _number(row.get("revenue")) or 0.0
        for row in fetch.market_ce_period_revenue(
            query_market, prior_start, prior_end
        ).to_dict("records")
    }
    ce_ly_mtd_revenue = {
        str(row.get("ce_id")): _number(row.get("revenue")) or 0.0
        for row in fetch.market_ce_period_revenue(
            query_market, ly_start, ly_mtd_end
        ).to_dict("records")
    }
    ce_ly_month_revenue = {
        str(row.get("ce_id")): _number(row.get("revenue")) or 0.0
        for row in fetch.market_ce_period_revenue(
            query_market, ly_start, ly_end
        ).to_dict("records")
    }
    ce_goals = fetch.market_ce_monthly_goals(query_market, month).to_dict("records")
    contributors = []
    ce_target_pacing = {}
    ce_target_total = 0.0
    for row in ce_goals:
        ce_goal = _number(row.get("monthly_goal"))
        if ce_goal is None:
            continue
        ce_target_total += ce_goal
        ce_id = str(row.get("ce_id"))
        actual = ce_revenue.get(ce_id, 0.0)
        expected = ce_goal * expected_mtd_share
        gap = actual - expected
        pacing = {
            "ce_id": ce_id,
            "ce_name": row.get("ce_name") or ce_id,
            "mtd_revenue": actual,
            "expected_mtd_revenue": expected,
            "mtd_gap": gap,
            "mtd_gap_pct": _percent_change(actual, expected),
            "monthly_goal": ce_goal,
            "prior_mtd_revenue": ce_prior_mtd_revenue.get(ce_id, 0.0),
            "prior_month_revenue": ce_prior_month_revenue.get(ce_id, 0.0),
            "ly_mtd_revenue": ce_ly_mtd_revenue.get(ce_id, 0.0),
            "ly_month_revenue": ce_ly_month_revenue.get(ce_id, 0.0),
            "mtd_vs_last_month_pct": _percent_change(
                actual, ce_prior_mtd_revenue.get(ce_id)
            ),
            "mtd_vs_last_year_pct": _percent_change(
                actual, ce_ly_mtd_revenue.get(ce_id)
            ),
        }
        ce_target_pacing[ce_id] = pacing
        if gap < 0:
            contributors.append(pacing)
    contributors.sort(key=lambda row: row["mtd_gap"])

    result = {
        "month": month.strftime("%Y-%m"),
        "monthly_goal": monthly_goal,
        "mtd_revenue": mtd_revenue,
        "forecast_revenue": forecast_revenue,
        "as_of": week_end.isoformat(),
        "report_week_end": meta["week_end"],
        "partial_period": cutoff < dt.date.fromisoformat(meta["week_end"]),
        "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": (
            f"revenue_goals ({goal_grain}); "
            "analytics_reporting.combined_entity_stats.sum_revenue_predicted"
        ),
        "goal_grain": goal_grain,
        "scope": "all markets" if market_slug == "headout" else market_name,
        "goal_row_count": market_rows if goal_grain == "Market" else ce_rows,
        "forecast_method": (
            "actual MTD + latest 4 complete weeks run rate allocated to "
            "the remaining calendar days"
        ),
        "forecast_baseline_revenue": run_rate_monthly_revenue,
        "forecast_remaining_revenue": forecast_remaining_revenue,
        "forecast_remaining_share_pct": remaining_month_share * 100.0,
        "expected_mtd_method": expected_mtd_method,
        "expected_mtd_share_pct": expected_mtd_share * 100.0,
        "days_in_month": days_in_month,
        "elapsed_days": elapsed_days,
        "remaining_days": remaining_days,
        "expected_mtd_revenue": expected_mtd_revenue,
        "mtd_gap": mtd_gap,
        "mtd_pacing_pct": 100.0 * mtd_revenue / expected_mtd_revenue if expected_mtd_revenue else None,
        "forecast_gap": forecast_gap,
        "forecast_gap_pct": _percent_change(forecast_revenue, monthly_goal),
        "required_weekly_revenue": required_weekly_revenue,
        "current_week_revenue": current_revenue,
        "run_rate_weekly_revenue": run_rate_weekly_revenue,
        "prior_month_revenue": prior_month_revenue,
        "prior_mtd_revenue": prior_mtd_revenue,
        "ly_month_revenue": ly_month_revenue,
        "ly_mtd_revenue": ly_mtd_revenue,
        "mtd_vs_last_month_pct": _percent_change(mtd_revenue, prior_mtd_revenue),
        "mtd_vs_last_year_pct": _percent_change(mtd_revenue, ly_mtd_revenue),
        "forecast_vs_last_month_pct": _percent_change(forecast_revenue, prior_month_revenue),
        "forecast_vs_last_year_pct": _percent_change(forecast_revenue, ly_month_revenue),
        "ce_target_coverage_pct": 100.0 * ce_target_total / monthly_goal if monthly_goal else None,
        "ce_gap_contributors": contributors[:5],
        "ce_target_pacing": ce_target_pacing,
    }
    return market_slug, result


def build(markets):
    records = dict(build_market_goal(market) for market in markets)
    return {
        "schema_version": 1,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "markets": records,
    }


def main():
    parser = argparse.ArgumentParser(description="Build a frozen V2 monthly-goals sidecar")
    parser.add_argument("inputs", nargs="+", help="schema-v1 snapshot or bundle JSON files")
    parser.add_argument("--out", required=True, help="local JSON output path")
    args = parser.parse_args()

    payload = build(render.load_markets(args.inputs))
    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, output)
    print(f"wrote: {output}")


if __name__ == "__main__":
    main()
