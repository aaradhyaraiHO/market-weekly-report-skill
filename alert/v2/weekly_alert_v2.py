"""Build the isolated two-message Weekly Market Alert V2 payload.

The authoritative KPI and mover input is the schema-v2 ``headlines`` payload
produced by ``codex/v2-market-headlines``. V1 remains independent.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


HERE = Path(__file__).resolve().parent
DEFAULT_BGMS = HERE / "market_bgms.json"
DEFAULT_FEEDBACK_CANVAS_URL = "https://headout.slack.com/docs/T029AQ5LB/F0BKPP4C7GC"
DEFAULT_OKR_TRACKER_URL = "https://central-tracking.vercel.app/okr-tracker"
LOCKED_FORMAT_VERSION = "2026-08-17.1"

OKR_SHORT_LABELS = {
    "grow_cumulative_pro_plus_ces": "Grow cumulative Pro+ CEs",
    "launch_new_pro_plus_mature": "New Pro+ CEs · Mature",
    "launch_new_pro_plus_emerging_growth": "New Pro+ CEs · Emerging & Growth",
    "grow_non_poi_gel_revenue_yoy": "Non-POI GEL revenue",
    "Launch new Pro+ CEs — Mature": "New Pro+ CEs · Mature",
    "Launch new Pro+ CEs — Emerging & Growth": "New Pro+ CEs · Emerging & Growth",
    "Grow non-POI GEL revenue YoY": "Non-POI GEL revenue",
}

LEDGER_SLUG = {
    "north_america": "north-america",
    "italy": "italy",
    "oceania": "oceania",
    "france": "france",
    "united_kingdom": "united-kingdom",
    "iberia": "iberia",
    "csee": "csee",
    "uae": "united-arab-emirates",
    "east_asia": "east-asia-jpn-sk-hk",
    "sea": "sea-sin-tha",
    "gcc": "gcc",
    "north_africa": "north-africa",
    "rest_of_mea": "rest-of-mea",
    "benelux": "benelux",
    "nordics": "nordics",
    "south_america": "south-america",
    "mexico_central_america": "mexico-central-america",
    "headout": "headout",
}


def _report_data(html_path: Path) -> dict:
    raw = html_path.read_text(encoding="utf-8")
    match = re.search(r'<script[^>]*id="report-data"[^>]*>', raw)
    if not match:
        raise ValueError(f"No report-data script found in {html_path}")
    end = raw.find("</script>", match.end())
    if end < 0:
        raise ValueError(f"Unclosed report-data script in {html_path}")
    payload = json.loads(raw[match.end():end])
    if payload.get("schema_version") != 2 or not isinstance(payload.get("headlines"), list):
        raise ValueError(
            "Weekly Alert V2 requires the schema-v2 headlines payload from "
            "codex/v2-market-headlines; V1 report-data is not a fallback"
        )
    return payload


def load_headline(
    html_path: Path,
    slug: str | None,
    index: int = -1,
    week_start: str | None = None,
) -> dict:
    rows = _report_data(html_path)["headlines"]
    if slug is not None:
        rows = [row for row in rows if row.get("market_slug") == slug]
    if week_start is not None:
        rows = [row for row in rows if row.get("week_start") == week_start]
    if not rows:
        raise ValueError(f"No V2 headline for market={slug!r}, week={week_start!r}")
    rows.sort(key=lambda row: row.get("week_start") or "")
    return rows[index]


def _read_json(path: Path | None, default: Any) -> Any:
    if path is None or not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fmt_money(value: Any, *, signed: bool = False) -> str:
    number = _number(value)
    if number is None:
        return "—"
    if number < 0:
        sign = "−"
    elif number > 0 and signed:
        sign = "+"
    else:
        sign = ""
    amount = abs(number)
    if amount >= 1_000_000:
        return f"{sign}${amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"{sign}${amount / 1_000:.1f}K"
    return f"{sign}${amount:,.0f}"


def fmt_delta(value: Any, digits: int = 1) -> str:
    number = _number(value)
    if number is None:
        return "—"
    sign = "+" if number > 0 else ("−" if number < 0 else "")
    return f"{sign}{abs(number):.{digits}f}%"


def fmt_attainment(value: Any, digits: int = 0) -> str:
    number = _number(value)
    return "—" if number is None else f"{number:.{digits}f}%"


def fmt_count(value: Any) -> str:
    number = _number(value)
    return "—" if number is None else f"{number:,.0f}"


def _metric_index(headline: dict) -> dict[str, dict]:
    """Index the authoritative V2 detail metrics without recalculating them."""
    metrics = ((headline.get("detail") or {}).get("metrics") or [])
    return {
        str(metric["key"]): metric
        for metric in metrics
        if isinstance(metric, dict) and metric.get("key")
    }


def _metric_actual(metric: dict | None, kind: str) -> str:
    value = (metric or {}).get("w0")
    if kind == "money":
        return fmt_money(value)
    if kind == "count":
        return fmt_count(value)
    if kind == "pct0":
        return fmt_attainment(value, 0)
    return fmt_attainment(value, 2)


def _metric_wow(metric: dict | None) -> str:
    return fmt_delta((metric or {}).get("delta_pct"), 1)


def _metric_yoy(metric: dict | None) -> str:
    if not metric or metric.get("has_ly") is False:
        return "—"
    return fmt_delta(metric.get("yoy_pct"), 1)


def alert_1_kpi_section(headline: dict, kpis: dict) -> str:
    """Render Revenue, Overall, and Paid tables from the V2 headline."""
    metrics = _metric_index(headline)
    overall_roi = metrics.get("roi1")
    paid_roi = metrics.get("paid_roi")
    aov = metrics.get("aov")
    take_rate = metrics.get("tr_pct")
    paid_clicks = metrics.get("paid_clicks")
    paid_cvr = metrics.get("paid_cvr")

    return "\n".join([
        ":bar_chart: *Revenue*",
        "|KPI|Actual|vs LW|vs same week LY|vs target|",
        "|---|---:|---:|---:|---:|",
        (
            f"|Revenue|{fmt_money(kpis['revenue'])}|{fmt_delta(kpis['vs_lw_pct'])}|"
            f"{fmt_delta(kpis['vs_ly_pct'])}|"
            f"{fmt_attainment(kpis['target_attainment_pct'])} projected "
            f"({fmt_money(kpis['forecast_revenue'])} / {fmt_money(kpis['monthly_goal'])})|"
        ),
        "",
        "*Overall*",
        "|KPI|Actual|vs LW|vs same week LY|",
        "|---|---:|---:|---:|",
        f"|Overall ROI|{_metric_actual(overall_roi, 'pct2')}|{_metric_wow(overall_roi)}|{_metric_yoy(overall_roi)}|",
        f"|AOV|{_metric_actual(aov, 'money')}|{_metric_wow(aov)}|{_metric_yoy(aov)}|",
        f"|Take rate|{_metric_actual(take_rate, 'pct2')}|{_metric_wow(take_rate)}|{_metric_yoy(take_rate)}|",
        "",
        "*Paid · Google Search + Bing*",
        "|KPI|Actual|vs LW|vs same week LY|",
        "|---|---:|---:|---:|",
        f"|Paid ROI|{_metric_actual(paid_roi, 'pct2')}|{_metric_wow(paid_roi)}|{_metric_yoy(paid_roi)}|",
        f"|Paid clicks|{_metric_actual(paid_clicks, 'count')}|{_metric_wow(paid_clicks)}|{_metric_yoy(paid_clicks)}|",
        f"|Paid CVR|{_metric_actual(paid_cvr, 'pct2')}|{_metric_wow(paid_cvr)}|{_metric_yoy(paid_cvr)}|",
        "_Paid ROI LY uses the report's calculated-CM fallback before Sep 2025, where applicable._",
    ])


def bgm_mentions(slug: str, config: dict) -> list[str]:
    entry = (config.get("markets") or {}).get(slug, {})
    ids = entry.get("slack_user_ids") or []
    invalid = [value for value in ids if not re.fullmatch(r"U[A-Z0-9]+", str(value))]
    if invalid:
        raise ValueError(f"Invalid Slack user IDs for {slug}: {invalid}")
    return [f"<@{user_id}>" for user_id in ids]


def _okr_rows(slug: str, results: dict | None, week_start: str | None = None) -> list[dict]:
    if not results:
        return []
    result_week = results.get("week_start")
    if week_start and result_week and result_week != week_start:
        raise ValueError(
            f"OKR sidecar week {result_week} does not match headline week {week_start}"
        )
    if "markets" in results:
        return list((results.get("markets") or {}).get(slug) or [])
    return list(results.get(slug) or [])


def _okr_line(row: dict, slug: str) -> str:
    label = row.get("label") or row.get("kr") or row.get("name")
    if not label:
        raise ValueError(f"OKR result for {slug} is missing label/kr/name: {row}")
    short_label = OKR_SHORT_LABELS.get(str(row.get("id"))) or OKR_SHORT_LABELS.get(
        str(label), str(label)
    )
    current = str(row.get("current", "—"))
    if row.get("id") == "grow_non_poi_gel_revenue_yoy" or label == "Grow non-POI GEL revenue YoY":
        current += " QTD"
    line = f"• *{short_label}* — {current}"
    if row.get("reached") is not None:
        line += f" ({row['reached']} reached)"
    if row.get("target") is not None:
        line += f" vs {row['target']} target"
    if row.get("status"):
        line += f" · {row['status']}"
    return line


def headline_kpis(headline: dict) -> dict:
    monthly = headline.get("monthly") or {}
    if monthly.get("state") != "current":
        raise ValueError(
            f"V2 headline for {headline.get('market_slug')} has no current approved target sidecar"
        )
    target_attainment = _number(monthly.get("forecast_attainment_pct"))
    values = {
        "revenue": _number(headline.get("revenue")),
        "vs_lw_pct": _number(headline.get("wow_pct")),
        "vs_ly_pct": _number(headline.get("yoy_pct")),
        "target_attainment_pct": target_attainment,
        "forecast_revenue": _number(monthly.get("forecast_revenue")),
        "monthly_goal": _number(monthly.get("monthly_goal")),
    }
    if any(values[key] is None for key in ("revenue", "vs_lw_pct", "vs_ly_pct", "target_attainment_pct")):
        raise ValueError(f"Incomplete V2 KPI evidence for {headline.get('market_slug')}: {values}")
    return values


def build_alert_1(
    headline: dict,
    report_url: str,
    bgms: dict,
    okr_results: dict | None,
    feedback_canvas_url: str = DEFAULT_FEEDBACK_CANVAS_URL,
) -> list[dict]:
    slug = headline["market_slug"]
    mentions = bgm_mentions(slug, bgms)
    if not mentions:
        raise ValueError(
            f"No BGM Slack IDs configured for {slug}; fill alert/v2/market_bgms.json "
            "before generating a publishable V2 payload"
        )
    kpis = headline_kpis(headline)
    title = (
        f"Hello {' '.join(mentions)}\n\n"
        f"📊 *{headline['market']} — Weekly Review*  ·  "
        f"_{headline['week_start']} → {headline['week_end']}_"
    )
    summary = alert_1_kpi_section(headline, kpis)
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": title}},
        {"type": "section", "text": {"type": "mrkdwn", "text": summary}},
    ]

    okrs = _okr_rows(slug, okr_results, headline.get("week_start"))
    if okrs:
        lines = [f"🎯 *<{DEFAULT_OKR_TRACKER_URL}|Selected OKRs>*"]
        for row in okrs:
            lines.append(_okr_line(row, slug))
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}})

    links = f"📊 *<{report_url}|Open this market's weekly report →>*"
    if feedback_canvas_url:
        links += f"   ·   📝 *<{feedback_canvas_url}|Add report feedback →>*"
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": links}})
    return blocks


def report_movers(headline: dict) -> tuple[list[dict], list[dict]]:
    movers = headline.get("movers") or {}
    return list(movers.get("gains") or [])[:5], list(movers.get("drops") or [])[:5]


def _validate_mover(row: dict) -> None:
    # Match the V2 headline: missing comparison evidence renders as an em dash;
    # identity and current revenue are the only hard requirements.
    required = ("ce_id", "ce_name", "revenue")
    missing = [key for key in required if row.get(key) is None]
    if missing:
        raise ValueError(f"Incomplete V2 mover {row.get('ce_id')}: missing {missing}")


def _mover_line(row: dict, direction: str) -> str:
    _validate_mover(row)
    icon = "🟢" if direction == "top" else "🔴"
    if row.get("monthly_target") is None:
        target = "No target"
    elif row.get("target_mtd_attainment_pct") is None:
        # A target without pacing evidence is not equivalent to no target. Keep
        # the row usable while failing closed on the unavailable comparison.
        target = "Unavailable"
    else:
        target = fmt_attainment(row.get("target_mtd_attainment_pct"))
    return (
        f"{icon} `[{row['ce_id']}]` *{row['ce_name']}* — {fmt_money(row['revenue'])}\n"
        f"   LW {fmt_money(row['wow_abs'], signed=True)} · "
        f"L4W {fmt_money(row['delta_4w'], signed=True)} · "
        f"LY {fmt_delta(row['yoy_pct'], 0)} · Target {target}"
    )


def _unique_ids(rows: Iterable[dict]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for row in rows:
        ce_id = str(row["ce_id"])
        if ce_id not in seen:
            seen.add(ce_id)
            ids.append(ce_id)
    return ids


def build_alert_2(headline: dict, report_url: str) -> tuple[list[dict], list[dict], list[str]]:
    top, bottom = report_movers(headline)
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text":
            f"📈 *{headline['market']} — Top 5 & Bottom 5*\n"
            "Source order and comparisons are taken directly from the V2 market headline."}},
        {"type": "section", "text": {"type": "mrkdwn", "text":
            "*Top 5*\n" + ("\n".join(_mover_line(row, "top") for row in top) or "—")}},
        {"type": "section", "text": {"type": "mrkdwn", "text":
            "*Bottom 5*\n" + ("\n".join(_mover_line(row, "bottom") for row in bottom) or "—")}},
        {"type": "section", "text": {"type": "mrkdwn", "text":
            "🧵 Per-CE weekly alerts in thread ↓"}},
        {"type": "section", "text": {"type": "mrkdwn", "text":
            f"📊 *<{report_url}|Open the weekly report →>*"}},
    ]
    ids = _unique_ids(top + bottom)
    return blocks, [{"$rca": ce_id} for ce_id in ids], ids


def build_payload(
    headline: dict,
    bgms: dict,
    okr_results: dict | None = None,
    report_url: str | None = None,
    feedback_canvas_url: str = DEFAULT_FEEDBACK_CANVAS_URL,
) -> dict:
    slug = headline["market_slug"]
    url = report_url or (
        "https://market-notebook.vercel.app/weekly-report-"
        + LEDGER_SLUG.get(slug, slug.replace("_", "-"))
    )
    alert_1 = build_alert_1(headline, url, bgms, okr_results, feedback_canvas_url)
    alert_2, threads, rca_ids = build_alert_2(headline, url)
    return {
        "messages": [
            {
                "fallback": f"{headline['market']} — Weekly KPI & OKR Review",
                "blocks": alert_1,
                "threads": [],
            },
            {
                "fallback": f"{headline['market']} — Top 5 & Bottom 5",
                "blocks": alert_2,
                "threads": threads,
            },
        ],
        "_rca": {
            "ce_ids": rca_ids,
            "week_start": headline["week_start"],
            "week_end": headline["week_end"],
        },
        "_v2": {
            "schema_version": 2,
            "format_version": LOCKED_FORMAT_VERSION,
            "format_locked": True,
            "headline_source": "codex/v2-market-headlines",
            "okr_selection_status": (
                "configured" if _okr_rows(slug, okr_results, headline.get("week_start")) else "pending"
            ),
            "v1_fallback_unchanged": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Weekly Market Alert V2 from V2 headline data")
    parser.add_argument("--file", required=True, help="Rendered V2 weekly report HTML")
    parser.add_argument("--market-slug", default=None)
    parser.add_argument("--week-start", default=None)
    parser.add_argument("--bgms", default=str(DEFAULT_BGMS), help="V2 market → Slack user IDs JSON")
    parser.add_argument("--okr-results", default=None, help="Selected OKR query results JSON")
    parser.add_argument("--report-url", default=None)
    parser.add_argument("--feedback-canvas-url", default=DEFAULT_FEEDBACK_CANVAS_URL)
    parser.add_argument("--out", default="payload_weekly_v2.json")
    args = parser.parse_args()

    headline = load_headline(
        Path(args.file).expanduser(), args.market_slug, week_start=args.week_start
    )
    bgms = _read_json(Path(args.bgms).expanduser(), {"markets": {}})
    okrs = _read_json(Path(args.okr_results).expanduser(), {}) if args.okr_results else None
    payload = build_payload(
        headline, bgms, okrs, args.report_url, args.feedback_canvas_url
    )
    Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✓ wrote {args.out} · V2 · market={headline['market']}")
    print("RCA_CE_IDS=" + ",".join(payload["_rca"]["ce_ids"]))
    print(f"WEEK={payload['_rca']['week_start']}..{payload['_rca']['week_end']}")
    if payload["_v2"]["okr_selection_status"] == "pending":
        print("OKR_SELECTION=pending")


if __name__ == "__main__":
    main()
