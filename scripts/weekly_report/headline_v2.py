"""Pure view-model helpers for the Weekly Report V2 market headline.

The V2 headline deliberately consumes the existing schema-v1 snapshot.  It
does not mutate the snapshot or reimplement any production bucket logic.
Monthly goal data is optional and must come from an explicit sidecar.
"""
from __future__ import annotations

import datetime as dt
import math
from copy import deepcopy
from functools import reduce
from statistics import fmean

import flows
from paid_platforms import snapshot_platforms


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
    "completed_orders",
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
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return value if math.isfinite(value) else None


def _json_safe_optional(value):
    """Copy optional enrichment data while nulling non-finite JSON numbers."""
    if isinstance(value, dict):
        return {key: _json_safe_optional(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_optional(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return deepcopy(value)


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
    # A deliberately partial-week preview has real MTD data through its cutoff,
    # not through the future Saturday. Keep the visible "through" date honest.
    if (goal.get("partial_period") is True and goal.get("report_week_end") == week_end
            and report_end - dt.timedelta(days=6) <= as_of <= report_end):
        return "current"
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
        w0 = _number(metric.get("w0"))
        wm1 = _number(metric.get("wm1"))
        delta_abs = _number(metric.get("delta_abs"))
        delta_pct = _number(metric.get("delta_pct"))
        # Some legacy V1 snapshots retain the authoritative WoW percentage but
        # omit its displayed W-1 operand. Reconstruct that operand for the V2
        # evidence table only; the source snapshot and V1 calculation remain
        # untouched. Fail closed for the non-invertible -100% case.
        if wm1 is None and w0 is not None:
            if delta_abs is not None:
                wm1 = w0 - delta_abs
            elif delta_pct is not None and delta_pct != -100:
                wm1 = round(w0 / (1.0 + delta_pct / 100.0), 6)
        if delta_abs is None and w0 is not None and wm1 is not None:
            delta_abs = w0 - wm1
        current_ly = series[-1]["ly"] if series else None
        yoy_pct = _percent_change(w0, current_ly)
        views.append({
            "key": key,
            "label": metric.get("label") or default_label,
            "format": value_format,
            "paid": key in _PAID_METRICS,
            "has_ly": metric.get("has_ly") is not False and any(row["ly"] is not None for row in series),
            "w0": w0,
            "wm1": wm1,
            "delta_abs": delta_abs,
            "delta_pct": delta_pct,
            "ly_w0": current_ly,
            "yoy_pct": yoy_pct,
            "series": series,
        })
    return views


def _mover_views(headlines, direction, ce_target_pacing=None, ce_current_revenue=None, ce_last_year_revenue=None):
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
    ce_target_pacing = ce_target_pacing or {}
    ce_current_revenue = ce_current_revenue or {}
    ce_last_year_revenue = ce_last_year_revenue or {}
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
        ce_id = row.get("ce_id")
        target = ce_target_pacing.get(str(ce_id)) or {}
        yoy_growth = _number(row.get("yoy_growth"))
        revenue = _number(row.get("w0_rev"))
        if revenue is None:
            revenue = _number(ce_current_revenue.get(str(ce_id)))
        previous_revenue = revenue - wow_abs if revenue is not None and wow_abs is not None else None
        trailing_four_revenue = (
            revenue - delta_4w if revenue is not None and delta_4w is not None else None
        )
        result.append({
            "ce_id": ce_id,
            "ce_name": row.get("ce_name") or "Unnamed experience",
            "primary_delta": _number(primary[0]),
            "primary_lens": primary[1],
            "delta_4w": delta_4w,
            "delta_4w_pct": _percent_change(revenue, trailing_four_revenue),
            "yoy_abs": revenue - ce_last_year_revenue[str(ce_id)] if revenue is not None and ce_last_year_revenue.get(str(ce_id)) is not None else None,
            "wow_abs": wow_abs,
            "wow_pct": _percent_change(revenue, previous_revenue),
            "ly_wow": _number(row.get("ly_wow")),
            "revenue": revenue,
            "yoy_growth": yoy_growth,
            "yoy_pct": yoy_growth * 100.0 if yoy_growth is not None else None,
            "target_mtd_gap": _number(target.get("mtd_gap")),
            "target_mtd_gap_pct": _number(target.get("mtd_gap_pct")),
            "target_mtd_attainment_pct": (
                100.0 + _number(target.get("mtd_gap_pct"))
                if _number(target.get("mtd_gap_pct")) is not None
                else None
            ),
            "monthly_target": _number(target.get("monthly_goal")),
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


def _post_diagnostic_view(market):
    """Project the V1 sections that follow Diagnostic buckets verbatim.

    These collections are already produced by the V1 snapshot engine.  V2 is
    only a renderer for them: no thresholds, classifications, recommendations,
    or per-row calculations are reproduced here.
    """
    no_bid = market.get("no_bid_campaigns") or {}
    return {
        "seasonality_adjustments": deepcopy(market.get("seasonality_adjustments") or []),
        "levers": deepcopy(market.get("levers") or []),
        "no_bid_campaigns": {
            "totals": deepcopy(no_bid.get("totals") or {}),
            "rows": deepcopy(no_bid.get("rows") or []),
        },
        "prepurchase": deepcopy(market.get("prepurchase") or []),
    }


def _losing_money_roi_precision(market, rows):
    """Add presentation-only WoW from the original, same-week CM1/spend.

    Bucket week blocks round ROI to integers. Never use those integers as
    calculation operands, or change the authoritative criteria/weekly fields.
    Mirror the producer's Google-Search/pre-split scope and respect its null
    validity gate. Missing or mismatched frozen evidence remains unavailable.
    """
    ces = market.get("ces") or []
    by_id = {str(ce.get("ce_id")): ce for ce in ces}
    has_google = any("spend_g" in week for ce in ces for week in (ce.get("weekly") or []))
    spend_key, cm1_key, roi_key = ("spend_g", "cm1_g", "roi_g") if has_google else ("spend", "cm1", "roi_pct")

    def number(value):
        if value is None or isinstance(value, bool):
            return None
        try:
            result = float(value)
        except (TypeError, ValueError):
            return None
        return result if math.isfinite(result) else None

    out = deepcopy(rows or [])
    for row in out:
        row["roi_wow_pct"] = None
        blocks = row.get("weeks") or []
        if len(blocks) < 2:
            continue
        try:
            current_date, previous_date = (dt.date.fromisoformat(block["week"]) for block in blocks[:2])
        except (KeyError, TypeError, ValueError):
            continue
        if (current_date - previous_date).days != 7:
            continue
        source = {week.get("week"): week for week in (by_id.get(str(row.get("ce_id")), {}).get("weekly") or [])}
        values = []
        for block in blocks[:2]:
            week = source.get(block.get("week"), {})
            spend, cm1 = number(week.get(spend_key)), number(week.get(cm1_key))
            if number(week.get(roi_key)) is None or number(block.get("roi")) is None or spend is None or spend <= 0 or cm1 is None:
                break
            roi = 100 * cm1 / spend
            if not math.isfinite(roi) or round(roi) != block["roi"]:
                break
            if block.get("cm1") != round(cm1) or block.get("spend") != round(spend):
                break  # Do not mix a revised cache with a frozen published row.
            values.append(roi)
        if len(values) == 2 and values[1] != 0:
            change = (values[0] / values[1] - 1) * 100
            if math.isfinite(change):
                row["roi_wow_pct"] = change
    return out


def _diagnostic_bucket_view(market):
    """Project the authoritative V1 diagnostic buckets without reclassification."""
    final = market.get("buckets_final") or {}
    defend = final.get("defend") or {}
    compound = final.get("compound") or {}
    lifecycle = final.get("lifecycle") or {}
    losing = defend.get("losing_money") or {}
    meta = market.get("meta") or {}
    return {
        "losing_money": {
            "existing": _losing_money_roi_precision(market, losing.get("existing")),
            "new": _losing_money_roi_precision(market, losing.get("new")),
            "paused": deepcopy(losing.get("paused") or []),
            "tracking_gap": deepcopy(losing.get("tracking_gap") or []),
            "burn_line": deepcopy(losing.get("burn_line") or {}),
        },
        "fluctuations": {
            "down": deepcopy(defend.get("seasonality_down") or []),
            "up": deepcopy(compound.get("seasonality_up") or []),
            "window": {
                key: deepcopy(meta.get(key)) for key in (
                    "fluctuation_partial", "fluctuation_days",
                    "fluctuation_window_start", "fluctuation_window_end",
                    "fluctuation_compare_start", "fluctuation_compare_end",
                )
            },
        },
        "lifecycle": {
            "new_ces": deepcopy(lifecycle.get("new_ces") or []),
            "iteration": deepcopy(lifecycle.get("iteration") or []),
        },
    }


def _scope_diagnostic_buckets(market, ce_ids):
    """Country-scope bucket rows while preserving V1 order and row payloads."""
    scoped = deepcopy(market)
    ids = {str(value) for value in ce_ids}
    final = scoped.setdefault("buckets_final", {})
    defend = final.setdefault("defend", {})
    compound = final.setdefault("compound", {})
    lifecycle = final.setdefault("lifecycle", {})
    losing = defend.setdefault("losing_money", {})

    def keep(rows):
        return [row for row in (rows or []) if str(row.get("ce_id")) in ids]

    for key in ("existing", "new", "paused", "tracking_gap"):
        losing[key] = keep(losing.get(key))
    # The market-level burn line has no CID-keyed rows, so it must not leak into
    # a country slice. The unfiltered market retains the authoritative summary.
    losing["burn_line"] = {}
    defend["seasonality_down"] = keep(defend.get("seasonality_down"))
    compound["seasonality_up"] = keep(compound.get("seasonality_up"))
    lifecycle["new_ces"] = keep(lifecycle.get("new_ces"))
    lifecycle["iteration"] = keep(lifecycle.get("iteration"))
    return scoped


def _scope_post_diagnostic(market, ce_ids):
    """Scope V1 post-diagnostic outputs to the selected business country."""
    scoped = deepcopy(market)
    ids = {str(value) for value in ce_ids}

    def filtered(key):
        return [
            row for row in (market.get(key) or [])
            if str(row.get("ce_id")) in ids
        ]

    scoped["seasonality_adjustments"] = filtered("seasonality_adjustments")
    scoped["levers"] = filtered("levers")
    scoped["prepurchase"] = filtered("prepurchase")
    no_bid_rows = [
        row for row in ((market.get("no_bid_campaigns") or {}).get("rows") or [])
        if str(row.get("ce_id")) in ids
    ]
    scoped["no_bid_campaigns"] = {
        "totals": {
            "count": len(no_bid_rows),
            "spend_total": sum(_number(row.get("spend_wk")) or 0.0 for row in no_bid_rows),
        },
        "rows": no_bid_rows,
    }
    return scoped


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


def _funnel_revenue_shapley(weekly, funnel_levels):
    """V2-only mixed-source attribution with an explicit revenue residual.

    Traffic/CVR use the all-channel Mixpanel funnel. Completion, AOV and take
    rate use the business weekly snapshot. This is intentionally not expected
    to telescope to predicted revenue because Mixpanel counts users while the
    business source counts orders; ``residual`` makes that boundary visible.
    """
    if len(weekly) < 2 or not isinstance(funnel_levels, dict):
        return None
    rows = {"w0": weekly[-1], "wm1": weekly[-2]}
    factors = {}
    for period, row in rows.items():
        funnel = funnel_levels.get(period) or {}
        lp_users = _number(funnel.get("lp_users"))
        order_users = _number(funnel.get("order_users"))
        orders = _number(row.get("orders"))
        completed_orders = _number(row.get("completed_orders"))
        gbv = _number(row.get("gbv"))
        completed_gbv = _number(row.get("gbv_completed"))
        revenue = _number(row.get("revenue"))
        values = (lp_users, order_users, orders, completed_orders, gbv, completed_gbv, revenue)
        if any(value is None or value <= 0 for value in values):
            return None
        factors[period] = {
            "traffic": lp_users,
            "cvr": order_users / lp_users,
            "completion": completed_orders / orders,
            "aov": gbv / orders,
            "take_rate": revenue / completed_gbv,
        }
    keys = ("traffic", "cvr", "completion", "aov", "take_rate")
    labels = {
        "traffic": "Traffic", "cvr": "LP→Order CVR", "completion": "Order completion",
        "aov": "AOV", "take_rate": "Take rate",
    }
    from itertools import combinations
    from math import factorial
    impacts = {}
    for key in keys:
        total = 0.0
        rest = [other for other in keys if other != key]
        for size in range(len(rest) + 1):
            weight = factorial(size) * factorial(len(keys) - size - 1) / factorial(len(keys))
            for subset in combinations(rest, size):
                base = 1.0
                for other in rest:
                    base *= factors["w0"][other] if other in subset else factors["wm1"][other]
                total += weight * base * (factors["w0"][key] - factors["wm1"][key])
        impacts[key] = total
    product = lambda period: reduce(lambda total, key: total * factors[period][key], keys, 1.0)
    prior_product, current_product = product("wm1"), product("w0")
    factor_total = current_product - prior_product
    revenue_delta = rows["w0"]["revenue"] - rows["wm1"]["revenue"]
    return {
        "factors": [{"key": key, "label": labels[key], "value": round(impacts[key], 1)} for key in keys],
        "factor_total": round(factor_total, 1),
        "residual": round(revenue_delta - factor_total, 1),
        "net_delta": round(revenue_delta, 1),
        "prior_product": round(prior_product, 1),
        "current_product": round(current_product, 1),
    }


def _ce_drawer_metrics(weekly, weekly_ly, funnel=None):
    current = weekly[-1] if weekly else {}
    previous = weekly[-2] if len(weekly) > 1 else {}
    ly_by_week = {row.get("week"): row for row in weekly_ly}
    funnel_cvr = (funnel or {}).get("CVR") or {}
    platform_ty = {row.get("week"): snapshot_platforms(row) for row in weekly}
    platform_ly = {row.get("week"): snapshot_platforms(row) for row in weekly_ly}
    result = {}
    for group, specs in _CE_DRAWER_METRICS.items():
        rows = []
        for key, label, value_format in specs:
            if key == "funnel_cvr_pct":
                funnel_w0 = _number(funnel_cvr.get("current"))
                funnel_wm1 = _number(funnel_cvr.get("wm1"))
                funnel_yoy_points = _number(funnel_cvr.get("yoy"))
                funnel_ly = _number(funnel_cvr.get("ly"))
                if funnel_ly is None and funnel_w0 is not None and funnel_yoy_points is not None:
                    funnel_ly = funnel_w0 - funnel_yoy_points
                rows.append({
                    "key": key,
                    "label": label,
                    "format": value_format,
                    "w0": funnel_w0,
                    "wm1": funnel_wm1,
                    "delta_abs": funnel_w0 - funnel_wm1 if funnel_w0 is not None and funnel_wm1 is not None else None,
                    "delta_pct": _number(funnel_cvr.get("wow")),
                    "delta_kind": "pp",
                    "wow_kind": "pp",
                    "ly_w0": funnel_ly,
                    "yoy_pct": _percent_change(funnel_w0, funnel_ly),
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
            w0 = _number(current.get(key))
            wm1 = _number(previous.get(key))
            rows.append({
                "key": key,
                "label": label,
                "format": value_format,
                "w0": w0,
                "wm1": wm1,
                "delta_abs": w0 - wm1 if w0 is not None and wm1 is not None else None,
                "delta_pct": _percent_change(w0, wm1),
                "delta_kind": "pp" if value_format == "pct" else "abs",
                "wow_kind": "pct",
                "ly_w0": series[-1]["ly"] if series else None,
                "yoy_pct": _percent_change(w0, series[-1]["ly"] if series else None),
                "series": series,
            })
            if group == "paid":
                breakdown = []
                for platform, label in (("google", "Google Search"), ("bing", "Bing Search")):
                    history = [{"week": point.get("week"),
                                "ty": _number(platform_ty.get(point.get("week"), {}).get(platform, {}).get(key)),
                                "ly": _number(platform_ly.get(point.get("week"), {}).get(platform, {}).get(key))}
                               for point in weekly[-12:]]
                    now = history[-1]["ty"] if history else None
                    prior = history[-2]["ty"] if len(history) > 1 else None
                    ly = history[-1]["ly"] if history else None
                    breakdown.append({
                        "key": f"{key}:{platform}", "label": label, "format": value_format,
                        "w0": now, "wm1": prior, "ly_w0": ly,
                        "delta_abs": now - prior if now is not None and prior is not None else None,
                        "delta_pct": _percent_change(now, prior), "yoy_pct": _percent_change(now, ly),
                        "wow_kind": "pct", "series": history,
                        "unavailable_reason": "Google Search only" if key == "paid_sis_pct" and platform == "bing"
                        else ("Platform data unavailable" if now is None else None),
                    })
                rows[-1]["breakdown"] = breakdown
        result[group] = rows
    return result


def _ce_views(market, dimensions=None):
    dimensions = dimensions or {}
    meta = market.get("meta") or {}
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
            "market": meta.get("market"),
            "business_country": metadata.get("country"),
            "business_region": metadata.get("region"),
            "week_start": meta.get("week_start"),
            "week_end": meta.get("week_end"),
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
            "previous_revenue": previous_revenue,
            "wow_abs": revenue - previous_revenue if revenue is not None and previous_revenue is not None else None,
            "wow_pct": _percent_change(revenue, previous_revenue),
            "yoy_pct": _number(current.get("yoy_pct")),
            "weekly_ly_revenue": _number(ly.get("revenue")),
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
            "funnel_shapley": _funnel_revenue_shapley(weekly, ce.get("funnel_levels")),
            "channels": deepcopy(ce.get("channels") or []),
            "funnel": deepcopy(ce.get("funnel") or {}),
            "tgids": deepcopy(ce.get("tgids") or []),
            "leadtime": _json_safe_optional(ce.get("leadtime") or []),
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
                    "history": deepcopy(row.get("history") or []),
                }
                for row in (ce.get("countries") or [])
                if row.get("country")
            ],
        })
    return views


_ADDITIVE_FIELDS = (
    "revenue", "actual_revenue", "gbv", "orders", "clicks", "spend", "cm1", "cm2",
    "cm1_business", "gross_marketing_cost", "paid_impressions", "paid_clicks",
    "paid_conv_value", "paid_conversions", "paid_revenue", "paid_cm2",
    "sis_impr", "sis_elig", "organic_gbv", "gbv_completed", "ad_conversions",
)


def _aggregate_weekly(ces, series_key):
    """Aggregate CE weekly facts using the V1 sum-then-divide metric canon."""
    weeks = sorted({
        row.get("week")
        for ce in ces for row in (ce.get(series_key) or [])
        if row.get("week")
    })
    by_ce = {
        str(ce.get("ce_id")): {row.get("week"): row for row in (ce.get(series_key) or [])}
        for ce in ces
    }
    result = []
    for week in weeks:
        rows = [lookup.get(week, {}) for lookup in by_ce.values()]
        row = {"week": week}
        for field in _ADDITIVE_FIELDS:
            values = [_number(item.get(field)) for item in rows]
            present = [value for value in values if value is not None]
            row[field] = sum(present) if present else None
        revenue, gbv = row.get("revenue"), row.get("gbv")
        actual_revenue = row.get("actual_revenue")
        orders, clicks = row.get("orders"), row.get("clicks")
        completed = row.get("gbv_completed")
        paid_clicks, paid_conversions = row.get("paid_clicks"), row.get("paid_conversions")
        spend, cm1 = row.get("spend"), row.get("cm1")
        row.update({
            "aov": gbv / orders if gbv is not None and orders else None,
            "cvr_pct": 100.0 * (row.get("ad_conversions") or 0) / clicks if clicks else None,
            "cr_pct": 100.0 * completed / gbv if gbv and completed is not None else None,
            "tr_pct": 100.0 * (actual_revenue if actual_revenue is not None else revenue) / completed
            if completed and (actual_revenue is not None or revenue is not None) else None,
            "roi_pct": 100.0 * cm1 / spend if spend and cm1 is not None else None,
            "roi1_pct": (
                100.0 * row["cm1_business"] / row["gross_marketing_cost"]
                if row.get("gross_marketing_cost") and row.get("cm1_business") is not None else None
            ),
            "paid_cvr_pct": 100.0 * paid_conversions / paid_clicks if paid_clicks else None,
            "avg_cm1": cm1 / paid_conversions if paid_conversions and cm1 is not None else None,
            "cpc": spend / paid_clicks if paid_clicks and spend is not None else None,
            "paid_rpc": row.get("paid_revenue") / paid_clicks if paid_clicks and row.get("paid_revenue") is not None else None,
            "paid_sis_pct": 100.0 * row["sis_impr"] / row["sis_elig"] if row.get("sis_elig") else None,
        })
        result.append(row)
    return result


def _metric_blocks(rows, weekly_ly):
    ly_by_week = {row.get("week"): row for row in weekly_ly}
    current = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) > 1 else {}
    blocks = {}
    for key, label, _fmt, field in _METRIC_SPECS:
        w0, wm1 = _number(current.get(field)), _number(previous.get(field))
        if w0 is None:
            continue
        blocks[key] = {
            "label": label,
            "w0": w0,
            "wm1": wm1,
            "delta_abs": w0 - wm1 if wm1 is not None else None,
            "delta_pct": _percent_change(w0, wm1),
            "has_ly": any(_number(row.get(field)) is not None for row in ly_by_week.values()),
        }
    return blocks


def _country_goal(goal, ces, rows, weekly_ly):
    if not isinstance(goal, dict):
        return None
    pacing = goal.get("ce_target_pacing") or {}
    ids = {str(ce.get("ce_id")) for ce in ces}
    records = [pacing[ce_id] for ce_id in ids if ce_id in pacing]
    monthly_goal = sum(_number(row.get("monthly_goal")) or 0.0 for row in records)
    mtd = sum(_number(row.get("mtd_revenue")) or 0.0 for row in records)
    if monthly_goal <= 0:
        return None
    remaining_days = int(goal.get("remaining_days") or 0)
    recent = [_number(row.get("revenue")) for row in rows[-4:]]
    recent = [value for value in recent if value is not None]
    run_rate = fmean(recent) if recent else None
    forecast_remaining = run_rate * remaining_days / 7.0 if run_rate is not None else None
    forecast = mtd + forecast_remaining if forecast_remaining is not None else None
    prior_mtd = sum(_number(row.get("prior_mtd_revenue")) or 0.0 for row in records)
    ly_mtd = sum(_number(row.get("ly_mtd_revenue")) or 0.0 for row in records)
    prior_month = sum(_number(row.get("prior_month_revenue")) or 0.0 for row in records)
    ly_month = sum(_number(row.get("ly_month_revenue")) or 0.0 for row in records)
    expected_share = (_number(goal.get("expected_mtd_share_pct")) or 0.0) / 100.0
    expected_mtd = monthly_goal * expected_share
    result = {key: goal.get(key) for key in (
        "month", "as_of", "retrieved_at", "days_in_month", "elapsed_days",
        "remaining_days", "expected_mtd_method", "expected_mtd_share_pct",
    )}
    result.update({
        "monthly_goal": monthly_goal,
        "mtd_revenue": mtd,
        "forecast_revenue": forecast,
        "source": "revenue_goals (Combined Entity roll-up); V1 CE weekly facts",
        "goal_grain": "Combined Entity country roll-up",
        "goal_row_count": len(records),
        "forecast_method": goal.get("forecast_method"),
        "forecast_remaining_revenue": forecast_remaining,
        "expected_mtd_revenue": expected_mtd,
        "mtd_gap": mtd - expected_mtd,
        "mtd_pacing_pct": 100.0 * mtd / expected_mtd if expected_mtd else None,
        "forecast_gap": forecast - monthly_goal if forecast is not None else None,
        "forecast_gap_pct": _percent_change(forecast, monthly_goal),
        "run_rate_weekly_revenue": run_rate,
        "required_weekly_revenue": (
            max(0.0, monthly_goal - mtd) / remaining_days * 7.0 if remaining_days else 0.0
        ),
        "prior_mtd_revenue": prior_mtd,
        "prior_month_revenue": prior_month,
        "ly_mtd_revenue": ly_mtd,
        "ly_month_revenue": ly_month,
        "mtd_vs_last_month_pct": _percent_change(mtd, prior_mtd),
        "mtd_vs_last_year_pct": _percent_change(mtd, ly_mtd),
        "forecast_vs_last_month_pct": _percent_change(forecast, prior_month),
        "forecast_vs_last_year_pct": _percent_change(forecast, ly_month),
        "ce_target_coverage_pct": None,
        "ce_target_pacing": {ce_id: pacing[ce_id] for ce_id in ids if ce_id in pacing},
    })
    return result


def _country_market(market, country, ces):
    rows = _aggregate_weekly(ces, "weekly")
    weekly_ly = _aggregate_weekly(ces, "weekly_ly")
    ly_by_week = {row.get("week"): row for row in weekly_ly}
    for row in rows:
        ly = ly_by_week.get(row.get("week"), {}).get("revenue")
        row["yoy_pct"] = _percent_change(row.get("revenue"), ly)
    trend = flows.per_ce_trend(ces)
    drops = sorted(
        [row for row in trend if row["delta_4w"] < 0 or row["raw_wow"] < -flows.WOW_DROP_FLOOR],
        key=lambda row: min(row["raw_wow"], row["delta_4w"]),
    )[:10]
    drop_ids = {str(row.get("ce_id")) for row in drops}
    gains = sorted(
        [row for row in trend if str(row.get("ce_id")) not in drop_ids and (row["delta_4w"] > 0 or row["raw_wow"] > 0)],
        key=lambda row: -max(row["raw_wow"], row["delta_4w"]),
    )[:10]
    current = rows[-1] if rows else {}
    previous = rows[-2] if len(rows) > 1 else {}
    shapley_rows = [ce.get("shapley_wow") for ce in ces if isinstance(ce.get("shapley_wow"), dict)]
    shapley = None
    if shapley_rows:
        factors = ("traffic", "cvr", "aov", "cr", "tr")
        shapley = {
            key: sum(_number(row.get(key)) or 0.0 for row in shapley_rows)
            for key in factors
        }
        shapley["total"] = sum(shapley.values())
        shapley["net_delta"] = shapley["total"]
        shapley["reconstructs"] = all(row.get("reconstructs") is not False for row in shapley_rows)
        shapley["labels"] = deepcopy(shapley_rows[0].get("labels") or {})
    headlines = {
        "revenue_w0": current.get("revenue"),
        "wow_pct": _percent_change(current.get("revenue"), previous.get("revenue")),
        "yoy_pct": current.get("yoy_pct"),
        "key_metrics": _metric_blocks(rows, weekly_ly),
        "shapley_wow": shapley,
        "week_header": {"trend": {"top_droppers": drops, "top_gainers": gains}},
    }
    ce_ids = [ce.get("ce_id") for ce in ces]
    scoped = _scope_post_diagnostic(market, ce_ids)
    scoped = _scope_diagnostic_buckets(scoped, ce_ids)
    scoped["ces"] = ces
    scoped["market_summary"] = {"weekly": rows, "weekly_ly": weekly_ly, "headlines": headlines}
    scoped["meta"] = {**(market.get("meta") or {}), "country": country}
    return scoped


def build_headline_view(market, goal=None, ce_dimensions=None, include_country_views=True):
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
            "ce_target_pacing",
            "goal_grain", "goal_row_count", "forecast_method",
            "retrieved_at",
            "partial_period", "report_week_end", "scope", "reference",
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

    current_ly_revenue = chart[-1]["revenue_ly"] if chart else None
    ce_target_pacing = monthly.get("ce_target_pacing") or {}
    ce_current_revenue = {}
    ce_last_year_revenue = {}
    for ce in market.get("ces") or []:
        weekly = ce.get("weekly") or []
        if weekly:
            ce_current_revenue[str(ce.get("ce_id"))] = _number(weekly[-1].get("revenue"))
            matched = next((r for r in ce.get("weekly_ly", []) if r.get("week") == weekly[-1].get("week")), {})
            ce_last_year_revenue[str(ce.get("ce_id"))] = _number(matched.get("revenue"))

    result = {
        "market": meta.get("market", "Unknown market"),
        "market_slug": meta.get("market_slug"),
        "week_start": meta.get("week_start"),
        "week_end": meta.get("week_end"),
        "ce_cap": meta.get("ce_cap"),
        "revenue": revenue,
        "wow_abs": wow_abs,
        "wow_pct": wow_pct,
        "yoy_abs": revenue - current_ly_revenue if current_ly_revenue is not None else None,
        "weekly_ly_revenue": current_ly_revenue,
        "vs_trailing_four_pct": _percent_change(revenue, trailing_four),
        "trailing_four_revenue": trailing_four,
        "yoy_pct": yoy_pct,
        "paid_roi_pct": paid_roi_w0,
        "paid_roi_delta_pp": paid_roi_delta_pp,
        "monthly": monthly,
        "chart": chart,
        "movers": {
            "drops": _mover_views(headlines, "drop", ce_target_pacing, ce_current_revenue, ce_last_year_revenue),
            "gains": _mover_views(headlines, "gain", ce_target_pacing, ce_current_revenue, ce_last_year_revenue),
        },
        "detail": {
            "metrics": _metric_views(headlines, rows, weekly_ly),
            "shapley": _shapley_view(headlines),
        },
        "diagnostic_buckets": _diagnostic_bucket_view(market),
        "post_diagnostic": _post_diagnostic_view(market),
        "all_ces": _ce_views(market, ce_dimensions),
    }
    result["country"] = meta.get("country")
    result["country_views"] = {}
    if include_country_views:
        grouped = {}
        for ce in market.get("ces", []):
            country = (ce.get("metadata") or {}).get("country")
            if country:
                grouped.setdefault(str(country), []).append(ce)
        for country, country_ces in sorted(grouped.items()):
            scoped = _country_market(market, country, country_ces)
            scoped_rows = scoped["market_summary"]["weekly"]
            country_goal = _country_goal(goal, country_ces, scoped_rows, scoped["market_summary"]["weekly_ly"])
            country_view = build_headline_view(
                scoped, country_goal, ce_dimensions, include_country_views=False
            )
            # Keep the static artifact compact: the base view already contains
            # every CE drawer payload. The browser filters that canonical list
            # by business_country instead of embedding it a second time.
            country_view.pop("all_ces", None)
            result["country_views"][country] = country_view
    return result


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
