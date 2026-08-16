#!/usr/bin/env python3
"""Build the frozen monthly-goals sidecar consumed by the V2 renderer.

This command only reads BigQuery and writes a local JSON artifact. It does not
render, publish, post to Slack, update Sheets, or modify a weekly snapshot.
"""
from __future__ import annotations

import argparse
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


def _weekly_rows(market):
    rows = market.get("market_summary", {}).get("weekly", [])
    return sorted(rows, key=lambda row: row.get("week", ""))


def _current_week_revenue(market):
    week_start = market.get("meta", {}).get("week_start")
    rows = _weekly_rows(market)
    row = next((item for item in rows if item.get("week") == week_start), rows[-1] if rows else {})
    return _number(row.get("revenue"))


def _previous_week_revenue(market):
    week_start = market.get("meta", {}).get("week_start")
    rows = [row for row in _weekly_rows(market) if row.get("week", "") < (week_start or "")]
    return _number(rows[-1].get("revenue")) if rows else None


def build_market_goal(market):
    meta = market.get("meta", {})
    market_name = meta.get("market")
    market_slug = meta.get("market_slug")
    week_end = dt.date.fromisoformat(meta["week_end"])
    month = week_end.replace(day=1)

    goal_row = _first_row(fetch.market_monthly_goal(market_name, month))
    market_goal = _number(goal_row.get("market_goal"))
    ce_goal = _number(goal_row.get("ce_goal"))
    market_rows = int(goal_row.get("market_row_count") or 0)
    ce_rows = int(goal_row.get("ce_row_count") or 0)
    if market_rows and market_goal is not None:
        monthly_goal = market_goal
        goal_grain = "Market"
    elif ce_rows and ce_goal is not None:
        monthly_goal = ce_goal
        goal_grain = "Combined Entity roll-up"
    else:
        raise RuntimeError(f"No approved monthly target for {market_name} in {month:%Y-%m}")

    revenue_row = _first_row(fetch.market_period_revenue(market_name, month, week_end))
    mtd_revenue = _number(revenue_row.get("revenue"))
    current_revenue = _current_week_revenue(market)
    if mtd_revenue is None or current_revenue is None:
        raise RuntimeError(f"Missing canonical revenue inputs for {market_name}")

    forecast_revenue = current_revenue * WEEKS_TO_MONTH
    previous_revenue = _previous_week_revenue(market)
    result = {
        "month": month.strftime("%Y-%m"),
        "monthly_goal": monthly_goal,
        "mtd_revenue": mtd_revenue,
        "forecast_revenue": forecast_revenue,
        "as_of": week_end.isoformat(),
        "source": (
            f"revenue_goals ({goal_grain}); "
            "analytics_reporting.combined_entity_stats.sum_revenue_predicted"
        ),
        "goal_grain": goal_grain,
        "goal_row_count": market_rows if goal_grain == "Market" else ce_rows,
        "forecast_method": f"current weekly revenue × {WEEKS_TO_MONTH}",
    }
    if previous_revenue is not None and monthly_goal:
        result["prior_forecast_attainment_pct"] = (
            previous_revenue * WEEKS_TO_MONTH / monthly_goal * 100.0
        )
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
