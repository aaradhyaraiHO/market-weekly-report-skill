#!/usr/bin/env python3
"""Render and verify Weekly Report V2 artifacts without publishing them.

The release harness deliberately consumes schema-v1 snapshots.  It does not
recalculate weekly metrics, buckets, mover order, or Shapley evidence.  Monthly
goals are an optional live enrichment and fail independently by market.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
from pathlib import Path

import build_v2_goals
import headline_v2
import render as render_v1
import render_v2


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _close(left, right, tolerance=0.02):
    left, right = _number(left), _number(right)
    if left is None or right is None:
        return left is right
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=0.02)


def _non_finite_paths(value, path="payload"):
    failures = []
    if isinstance(value, dict):
        for key, item in value.items():
            failures.extend(_non_finite_paths(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            failures.extend(_non_finite_paths(item, f"{path}[{index}]"))
    elif isinstance(value, float) and not math.isfinite(value):
        failures.append(path)
    return failures


def _bucket_map(market):
    return {
        ce_id: sorted(item["key"] for item in memberships)
        for ce_id, memberships in headline_v2._ce_bucket_memberships(market).items()
    }


def _current_ce_revenue(ce):
    weekly = sorted(ce.get("weekly") or [], key=lambda row: row.get("week", ""))
    return _number((weekly[-1] if weekly else {}).get("revenue")) or 0.0


def verify_market(market, view, goal_error=None):
    """Return a release-gate record for one rendered market."""
    failures, warnings = [], []
    meta = market.get("meta") or {}
    summary = market.get("market_summary") or {}
    weekly = sorted(summary.get("weekly") or [], key=lambda row: row.get("week", ""))
    current = weekly[-1] if weekly else {}
    previous = weekly[-2] if len(weekly) > 1 else {}
    headlines = summary.get("headlines") or {}

    def require(condition, message):
        if not condition:
            failures.append(message)

    require(view.get("market_slug") == meta.get("market_slug"), "market slug changed")
    require(view.get("week_start") == meta.get("week_start"), "week start changed")
    require(_close(view.get("revenue"), current.get("revenue")), "W0 revenue differs from V1")
    if current and previous:
        require(
            _close(view.get("wow_abs"), _number(current.get("revenue")) - _number(previous.get("revenue"))),
            "WoW revenue movement differs from V1 operands",
        )

    source_ces = market.get("ces") or []
    view_ces = view.get("all_ces") or []
    source_ids = [str(row.get("ce_id")) for row in source_ces]
    view_ids = [str(row.get("ce_id")) for row in view_ces]
    require(len(view_ids) == len(set(view_ids)), "V2 contains duplicate CE IDs")
    require(set(view_ids) == set(source_ids), "All-CE membership differs from V1")

    headline_revenue = _number(current.get("revenue"))
    surfaced_ce_revenue = sum(_current_ce_revenue(ce) for ce in source_ces)
    ce_cap = view.get("ce_cap")
    revenue_coverage = (
        surfaced_ce_revenue / headline_revenue * 100
        if headline_revenue and headline_revenue > 0 else None
    )
    if ce_cap:
        require(
            revenue_coverage is not None and 0 < revenue_coverage <= 100.02,
            "capped All-CE revenue coverage is invalid",
        )
        warnings.append(
            f"All-CE view is capped at {ce_cap.get('shown')} of {ce_cap.get('total')} CEs "
            f"({revenue_coverage:.1f}% revenue coverage)"
        )
    else:
        require(
            revenue_coverage is None or revenue_coverage <= 100.02,
            "All-CE revenue exceeds headline revenue",
        )
        if not _close(surfaced_ce_revenue, headline_revenue):
            warnings.append(
                "All-CE revenue does not fully reconcile to headline revenue "
                f"({revenue_coverage:.1f}% coverage)"
            )

    projected_buckets = {
        str(row.get("ce_id")): sorted(item.get("key") for item in row.get("buckets") or [])
        for row in view_ces
        if row.get("buckets")
    }
    require(projected_buckets == _bucket_map(market), "bucket membership differs from buckets_final")

    trend = ((headlines.get("week_header") or {}).get("trend") or {})
    for direction, source_key in (("drops", "top_droppers"), ("gains", "top_gainers")):
        source_rows = trend.get(source_key) or headlines.get(
            "top_drops" if direction == "drops" else "top_gainers"
        ) or []
        source_order = [str(row.get("ce_id")) for row in source_rows]
        view_order = [str(row.get("ce_id")) for row in (view.get("movers") or {}).get(direction) or []]
        require(view_order == source_order, f"{direction} mover order differs from V1")

    source_shapley = headlines.get("shapley_wow")
    view_shapley = (view.get("detail") or {}).get("shapley")
    if isinstance(source_shapley, dict):
        require(isinstance(view_shapley, dict), "V1 Shapley evidence missing from V2")
        if isinstance(view_shapley, dict):
            values = {row.get("key"): row.get("value") for row in view_shapley.get("factors") or []}
            for key in ("traffic", "cvr", "aov", "cr", "tr"):
                require(_close(values.get(key), source_shapley.get(key)), f"Shapley {key} differs from V1")

    non_finite = _non_finite_paths(view)
    require(not non_finite, f"non-finite JSON values: {', '.join(non_finite[:3])}")

    resources = {}
    for key in ("tgids", "leadtime", "countries", "channels"):
        rows = sum(len(ce.get(key) or []) for ce in source_ces)
        ces = sum(bool(ce.get(key)) for ce in source_ces)
        histories = None if key == "tgids" else sum(
            sum(bool(row.get("history")) for row in ce.get(key) or []) for ce in source_ces
        )
        resources[key] = {"rows": rows, "ces": ces, "history_rows": histories}
        if rows == 0:
            warnings.append(f"optional {key} enrichment is empty")
        elif histories == 0:
            warnings.append(f"optional {key} history is empty")

    country_count = len({
        str((ce.get("metadata") or {}).get("country"))
        for ce in source_ces if (ce.get("metadata") or {}).get("country")
    })
    require(len(view.get("country_views") or {}) == country_count, "country views do not match CE business-country coverage")
    if goal_error:
        warnings.append(f"monthly target unavailable: {goal_error}")

    return {
        "market": meta.get("market"),
        "market_slug": meta.get("market_slug"),
        "week_start": meta.get("week_start"),
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "warnings": warnings,
        "coverage": {
            "ces": len(source_ces),
            "headline_revenue": headline_revenue,
            "surfaced_ce_revenue": surfaced_ce_revenue,
            "ce_revenue_coverage_pct": revenue_coverage,
            "countries": country_count,
            "resources": resources,
            "monthly_goal": (view.get("monthly") or {}).get("state"),
        },
    }


def release(snapshot_paths, output_dir, goals_path=None, fetch_goals=True, okr_results_path=None):
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    supplied_goals = render_v2.load_goals(goals_path) if goals_path else {}
    supplied_okrs = render_v2.load_okr_results(okr_results_path) if okr_results_path else {}
    goals_artifact = output_dir / "goals_v2.json"
    try:
        existing_goals = (
            render_v2.load_goals(goals_artifact)
            if goals_artifact.exists()
            else {}
        )
    except (OSError, ValueError, TypeError):
        # A damaged optional artifact must not take down V1/V2 generation. The
        # requested markets are rebuilt below; unrequested records cannot be
        # preserved safely when the prior file is unreadable.
        existing_goals = {}
    records, artifacts, goal_records = [], [], {}
    requested_slugs = set()
    prepared = []

    for snapshot_path in snapshot_paths:
        market = render_v1.load_markets([str(snapshot_path)])[0]
        slug = market.get("meta", {}).get("market_slug") or "market"
        requested_slugs.add(slug)
        week = market.get("meta", {}).get("week_start") or "week"
        goal_error = None
        goal = supplied_goals.get(slug)
        if fetch_goals and goal is None:
            try:
                _, goal = build_v2_goals.build_market_goal(market)
            except Exception as exc:  # optional live source must fail per market
                goal_error = str(exc)
        elif goal is None:
            goal_error = "live target fetch disabled and no supplied goal record"
        if goal is not None:
            goal_records[slug] = goal
        prepared.append((market, slug, week, goal_error))

    available_goals = {**existing_goals, **supplied_goals, **goal_records}
    if isinstance(goal_records.get("headout"), dict):
        goal_records["headout"] = build_v2_goals.merge_headout_ce_targets(
            goal_records["headout"], available_goals
        )
        available_goals["headout"] = goal_records["headout"]

    for market, slug, week, goal_error in prepared:
        goal = goal_records.get(slug)
        goals = {slug: goal} if goal is not None else {}
        view = headline_v2.build_headline_view(market, goal)
        output = output_dir / f"report_{slug}_{week}.html"
        output.write_text(render_v2.render([market], goals=goals, okr_results=supplied_okrs))
        record = verify_market(market, view, goal_error)
        record["artifact"] = str(output)
        records.append(record)
        artifacts.append(str(output))

    # A targeted release must not truncate goals for markets outside its input
    # set. Requested markets are always replaced (or removed after a failed
    # fetch) so an old record cannot masquerade as current data.
    preserved_goals = {
        slug: goal
        for slug, goal in existing_goals.items()
        if slug not in requested_slugs and isinstance(goal, dict)
    }
    merged_goals = {**preserved_goals, **goal_records}
    temporary_goals = goals_artifact.with_suffix(goals_artifact.suffix + ".tmp")
    temporary_goals.write_text(
        json.dumps({"schema_version": 1, "markets": merged_goals}, indent=2) + "\n"
    )
    temporary_goals.replace(goals_artifact)
    manifest = {
        "schema_version": 1,
        "status": "pass" if records and all(row["status"] == "pass" for row in records) else "fail",
        "markets": records,
        "artifacts": artifacts,
        "goals_artifact": str(goals_artifact),
        "published": False,
    }
    return manifest


def main():
    parser = argparse.ArgumentParser(description="Render and verify no-publish Weekly V2 artifacts")
    parser.add_argument("inputs", nargs="*", help="schema-v1 snapshot JSON files")
    parser.add_argument("--glob", dest="snapshot_glob", help="additional snapshot glob")
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--goals", help="existing goals sidecar")
    parser.add_argument("--okr-results", help="optional same-week market OKR sidecar")
    goal_fetch = parser.add_mutually_exclusive_group()
    goal_fetch.add_argument(
        "--fetch-goals",
        dest="fetch_goals",
        action="store_true",
        help="read approved monthly targets from BigQuery (default)",
    )
    goal_fetch.add_argument(
        "--no-fetch-goals",
        dest="fetch_goals",
        action="store_false",
        help="render without live target reads; missing supplied goals are warned",
    )
    parser.set_defaults(fetch_goals=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    paths = [Path(path) for path in args.inputs]
    if args.snapshot_glob:
        paths.extend(Path(path) for path in sorted(glob.glob(args.snapshot_glob)))
    if not paths:
        parser.error("at least one snapshot input is required")
    manifest = release(paths, args.out_dir, args.goals, args.fetch_goals, args.okr_results)
    manifest_path = Path(args.manifest).resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"V2 release gate: {manifest['status'].upper()} ({len(manifest['markets'])} market(s))")
    print(f"manifest: {manifest_path}")
    if manifest["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
