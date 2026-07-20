"""
Weekly RCA Helper  (computed, trustworthy half of the WEEKLY alert)
===================================================================

The WoW twin of rca_helper.py. Given a list of CE ids + the report's week,
runs the CE-id-filtered WoW RCA SQL and emits ready-to-post Slack blocks for
each CE's per-CE revenue-diagnosis thread reply — reusing the SAME engine as the
monthly alert (revenue_drop_alert.analyze_ce_row / build_ce_thread_detail_blocks)
so every number is USER-BASED and matches Omni:
  - Traffic  = distinct users (COUNT DISTINCT user_id)
  - CVR      = users_order_completed / traffic
  - Demand RCA = paid vs organic USERS (+ channel mix in users)
  - CVR RCA  = user funnel (LP2S / S2C / C2O)
The weekly path shows 5 drivers (Traffic, CVR, AOV, Completion, Take rate —
Orders/User dropped) and picks the primary driver from the displayed table.

USAGE:
    .venv/bin/python weekly_rca_helper.py \
        --ce-ids "6925,3111,2554,18 - Chicago Cruises - Chicago" \
        --week-start 2026-06-29 --week-end 2026-07-05 \
        --out rca_blocks_weekly.json

Output: JSON  { "<ce_id>": {"fallback": "...", "blocks": [ <Block Kit blocks> ]} }
Feed the file to post_message.py via --rca-blocks; reference a CE in a thread
with {"$rca": "<ce_id>"}.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import sys
import urllib.parse
from pathlib import Path

from google.cloud import bigquery

from revenue_drop_alert import (
    PROJECT_ID,
    analyze_ce_row,
    build_ce_thread_detail_blocks,
    fmt_money,
    fmt_pct_signed,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("weekly_rca_helper")

WOW_SQL = Path(__file__).parent / "sql" / "ce_revenue_cvr_drop_ids.sql"
RECENT_LABEL = "L4W avg"   # Long-term Context recent-baseline column label (weekly)

OMNI_DASHBOARD_URL = "https://headout.omniapp.co/dashboards/5368ab53"

# Cap every query at 10 GB (analytics-skill requirement) and label it so it's
# identifiable in BQ audit logs / the billing dashboard.
MAX_BYTES_BILLED = 40 * 1024 ** 3   # ~10-22GB actual for ~10 CEs (Italy's larger CE set hit the old 20GB cap); headroom for popular CEs/LY windows
JOB_LABELS = {"source": "analytics_skill", "alert": "weekly_wow_rca"}

# Thick, unmistakable separator between stacked CE replies in a bucket thread.
THICK_SEPARATOR = {
    "type": "section",
    "text": {"type": "mrkdwn",
             "text": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"},
}


def build_omni_week_link(ce_id: str, week_start: str, week_end: str) -> str:
    """
    Week-over-week Omni deep-link — same logic as weekly_alert.build_omni_week_link
    (dashboard 5368ab53; CE filter f--iv8lWOuS; date filter f--uvd3KWWJ as a
    BETWEEN whose right_side is week_end + 1 day, since Omni's BETWEEN is
    end-exclusive). Clicking from Slack lands on the same WoW view as the report.
    """
    ce_filter = {"values": [str(ce_id)]}
    try:
        end_plus1 = (datetime.date.fromisoformat(week_end) + datetime.timedelta(days=1)).isoformat()
    except Exception:
        end_plus1 = week_end
    date_filter = {"kind": "BETWEEN", "left_side": week_start, "right_side": end_plus1,
                   "ui_type": "BETWEEN", "offset_interval_string": None}
    params = {"f--iv8lWOuS": json.dumps(ce_filter, separators=(",", ":")),
              "f--uvd3KWWJ": json.dumps(date_filter, separators=(",", ":"))}
    return f"{OMNI_DASHBOARD_URL}?{urllib.parse.urlencode(params)}"


def _sql_quote(ce_id: str) -> str:
    """Safely quote a CE id (a STRING that may be composite, e.g.
    `18 - Chicago Cruises - Chicago`) for a SQL IN(...) list."""
    return "'" + ce_id.replace("\\", "\\\\").replace("'", "''") + "'"


def run_wow_query(ce_ids: list[str], week_start: str):
    sql = WOW_SQL.read_text()
    quoted = ", ".join(_sql_quote(c) for c in ce_ids)
    sql = sql.replace("{{CE_IDS}}", quoted).replace("{{WEEK_START}}", week_start)
    log.info("Running WoW RCA query for %d CE(s), week starting %s…", len(ce_ids), week_start)
    client = bigquery.Client(project=PROJECT_ID)
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=MAX_BYTES_BILLED,
        labels=JOB_LABELS,
    )
    df = client.query(sql, job_config=job_config).to_dataframe()
    log.info("Returned %d rows", len(df))
    return df


def ce_header_block(name: str, ce_id: str) -> dict:
    """Lightweight CE-name header so replies are identifiable in the shared thread."""
    return {
        "type": "header",
        "text": {"type": "plain_text", "text": f"📋 {name}  ·  CE {ce_id}", "emoji": True},
    }


def revenue_line_block(alert: dict) -> dict:
    """One-line WoW revenue summary above the drivers (week-over-week)."""
    pre, post = alert["pre_revenue"], alert["post_revenue"]
    signed = (post - pre) / pre if pre else 0.0
    return {
        "type": "section",
        "text": {"type": "mrkdwn",
                 "text": f"*Revenue (WoW):* {fmt_money(pre)} → {fmt_money(post)} "
                         f"*({fmt_pct_signed(signed, 1)})*"},
    }


def build_rca_entry(row, week_start: str, week_end: str) -> dict:
    alert = analyze_ce_row(row, always=True, skip_floor_check=True, weekly=True)
    ce_id = str(row["combined_entity_id"])
    name = row.get("combined_entity_name") or "(unknown)"
    omni = build_omni_week_link(ce_id, week_start, week_end)
    omni_block = {
        "type": "context",
        "elements": [{"type": "mrkdwn",
                      "text": f"📊  <{omni}|Open in Omni — week over week>"}],
    }

    if alert is None:
        # Pre revenue was 0 / unusable — emit a minimal note instead of full RCA
        return {
            "fallback": f"{name} — insufficient data",
            "blocks": [
                ce_header_block(name, ce_id),
                {"type": "section", "text": {"type": "mrkdwn",
                    "text": "_Insufficient revenue data to compute a week-over-week RCA._"}},
                omni_block,
                THICK_SEPARATOR,
            ],
        }
    blocks = [ce_header_block(name, ce_id), revenue_line_block(alert), omni_block]
    blocks += build_ce_thread_detail_blocks(alert, recent_label=RECENT_LABEL, weekly=True)
    blocks.append(THICK_SEPARATOR)
    return {"fallback": f"{name} — WoW revenue diagnosis", "blocks": blocks}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute WoW RCA blocks for a set of CEs")
    parser.add_argument("--ce-ids", required=True,
                        help="Comma-separated CE ids (composite strings allowed), e.g. "
                             "'6925,3111,18 - Chicago Cruises - Chicago'")
    parser.add_argument("--week-start", required=True, help="W0 Monday (YYYY-MM-DD)")
    parser.add_argument("--week-end", required=True, help="W0 Sunday (YYYY-MM-DD)")
    parser.add_argument("--out", default="rca_blocks_weekly.json", help="Output JSON path")
    args = parser.parse_args()

    ce_ids = [c.strip() for c in args.ce_ids.split(",") if c.strip()]
    if not ce_ids:
        log.error("No CE ids provided"); sys.exit(1)

    df = run_wow_query(ce_ids, args.week_start)
    by_id = {str(r["combined_entity_id"]): r for _, r in df.iterrows()}

    out: dict[str, dict] = {}
    for ce_id in ce_ids:
        row = by_id.get(ce_id)
        if row is None:
            log.warning("CE %s not returned by SQL (no data in window) — skipping", ce_id)
            continue
        out[ce_id] = build_rca_entry(row, args.week_start, args.week_end)
        log.info("  ✓ built RCA for CE %s (%s)", ce_id, out[ce_id]["fallback"])

    Path(args.out).write_text(json.dumps(out, indent=2))
    log.info("Wrote %d RCA entries → %s", len(out), args.out)


if __name__ == "__main__":
    main()
