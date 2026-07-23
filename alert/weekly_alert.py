"""
Weekly Market Alert — POC (single market, from the weekly report HTML)
=====================================================================

Reads the weekly report's embedded `report-data` JSON and builds the SUMMARY
message + 3 bucket tables entirely from the report's own numbers (no BigQuery).
The per-CE revenue-diagnosis thread replies are NOT built here — they are emitted
as `{"$rca": "<ce_id>"}` references and computed separately, USER-BASED from
BigQuery, by weekly_rca_helper.py (exactly like the monthly alert). This mirrors
Omni and fixes the old report-JSON RCA that used clicks-based traffic/CVR.

Structure:
  MSG 1  Weekly summary
     └─ thread: Losing Money / CM1 table  (bucket_b1)
     └─ thread: RPC Fluctuations Down table
     └─ thread: RPC Fluctuations Up table
  MSG 2  Top movers by WoW revenue delta (across the 3 tables)
     └─ thread: per-CE revenue diagnosis  ({"$rca": ...} → weekly_rca_helper.py)

Emits a payload for post_message.py, plus a top-level `_rca` block
({ce_ids, week_start, week_end}) and prints RCA_CE_IDS/WEEK for the next step.

USAGE (3-command flow):
  python weekly_alert.py --file "<weekly-report.html>" --market-slug north_america --out payload_weekly.json
  python weekly_rca_helper.py --ce-ids "<RCA_CE_IDS>" --week-start <s> --week-end <e> --out rca_blocks_weekly.json
  python post_message.py --payload payload_weekly.json --rca-blocks rca_blocks_weekly.json --channel C0B6U94PGJ0
"""

from __future__ import annotations

import argparse
import html as H
import json
import re
import sys
from pathlib import Path

# ---------- formatting ----------
def fmt_money(v):
    if v is None: return "—"
    a = abs(v); sign = "-" if v < 0 else ""
    if a >= 1e6: return f"{sign}${a/1e6:.1f}M"
    if a >= 1e3: return f"{sign}${a/1e3:.1f}K"
    return f"{sign}${a:,.0f}"

def fmt_pct(v, dp=1):
    return "—" if v is None else f"{v:+.{dp}f}%"

def fmt_plain_pct(v, dp=1):
    return "—" if v is None else f"{v:.{dp}f}%"

def dot(attain):
    if attain is None: return ""
    return "🟢" if attain >= 100 else ("🟠" if attain >= 70 else "🔴")

def dir_emoji(v):
    if v is None: return "➖"
    return "🔻" if v <= -5 else ("🔺" if v >= 5 else "➖")

def trunc(s, w):
    s = str(s)
    return s if len(s) <= w else s[:w-1] + "…"


# ---------- report loading ----------
def load_market(html_path: Path, slug: str | None, index: int):
    raw = html_path.read_text(encoding="utf-8")
    m = re.search(r'<script[^>]*id="report-data"[^>]*>', raw)
    s = m.end(); e = raw.find("</script>", s)
    data = json.loads(raw[s:e])
    markets = data["markets"]
    if slug:
        for mk in markets:
            if mk["meta"].get("market_slug") == slug:
                return mk
        raise SystemExit(f"market_slug {slug} not found; have: {[m['meta']['market_slug'] for m in markets]}")
    return markets[index]


# ---------- monospace table ----------
def render_table(headers, rows, caps=None):
    n = len(headers)
    if caps is None:
        caps = [28] + [22] * (n - 1)
    widths = [min(caps[j], max([len(trunc(headers[j], caps[j]))] + [len(trunc(r[j], caps[j])) for r in rows] or [0])) for j in range(n)]
    def fr(cells): return "  ".join(trunc(c, widths[j]).ljust(widths[j]) for j, c in enumerate(cells)).rstrip()
    line = fr(headers); sep = "─" * len(line)
    return "```\n" + line + "\n" + sep + "\n" + "\n".join(fr(r) for r in rows) + "\n```"


# ---------- per-CE helpers ----------
def w0_wm1(ce):
    """Return (W0_week_entry, W-1_week_entry) from the report's `weekly` array.

    IMPORTANT: `weekly` is a 12-week series in ASCENDING date order, so the
    report week (W0) is the LAST element and the prior week (W-1) the one before
    it — NOT weekly[0]/weekly[1] (those are the OLDEST weeks). We select by max
    `week` so this is robust regardless of array order."""
    w = ce.get("weekly") or []
    if len(w) < 2: return None, None
    ws = sorted(w, key=lambda r: r.get("week") or "")
    return ws[-1], ws[-2]

def ce_wow_pct(ce):
    w0, wm1 = w0_wm1(ce)
    if w0 is None: return None
    r0, rm1 = w0.get("revenue"), wm1.get("revenue")
    if not rm1: return None
    return (r0 - rm1) / rm1 * 100

def ce_w0_rev(ce):
    w0, _ = w0_wm1(ce)
    return (w0.get("revenue") if w0 else 0) or 0

def ce_wow_rev_delta(ce):
    """Actual WoW revenue change (W0 − W-1), the basis used everywhere for
    ranking/headlines so the alert is internally consistent. W0/W-1 are the two
    most-recent weeks in the report's ascending `weekly` series (see w0_wm1)."""
    w0, wm1 = w0_wm1(ce)
    if w0 is None: return None
    r0, rm1 = w0.get("revenue"), wm1.get("revenue")
    if r0 is None or rm1 is None: return None
    return r0 - rm1


# ---------- report "biggest move" charts (TOP DROPS / TOP GAINS) ----------
def trend_charts(mk):
    """The report's own 'BIGGEST MOVE · 4-WK OR WoW' charts — ranked lists of
    top droppers / top gainers (matches the report's headline chart exactly, so
    the alert headline is always consistent with the report)."""
    tr = mk["market_summary"]["headlines"]["week_header"]["trend"]
    return tr.get("top_droppers", []) or [], tr.get("top_gainers", []) or []

def mover_bullet(r, side):
    """One headline mover line — CE id + name + WoW % change + actual W-1 → W0.
    W0 = report's `w0_rev`; WoW delta = `raw_wow`, so W-1 = w0_rev − raw_wow.
      🔴  `[6925]`  Medieval Dinner … — *-64%*  _($565 → $202)_
    """
    w0  = r.get("w0_rev") or 0
    wow = r.get("raw_wow") or 0
    wm1 = w0 - wow
    pct = (wow / wm1 * 100) if wm1 else None
    emoji = "🔴" if side == "drop" else "🟢"
    return (f"{emoji}  `[{r.get('ce_id')}]`  {r.get('ce_name')} — "
            f"*{fmt_pct(pct, 0)}*  _({fmt_money(wm1)} → {fmt_money(w0)})_")


# =============================================================================
# SUMMARY (MSG 1 top-level)
# =============================================================================
# Market team tag — mirrors the MONTHLY alert: a "Hello team @<market> <flag>" greeting
# addressed to the market team. NOTE: @handle text inside a Block Kit block does NOT create
# a real Slack notification (only <!subteam^ID> does, which needs usergroups:read to resolve).
# So this is a cosmetic team greeting, exactly like the monthly pings. Handles + flags match
# market-monthly-review/alert/payload-*.json.
MARKET_TEAM = {
    "north_america":  ("@growth-north-america", "🌎"),
    "italy":          ("@it", "🇮🇹"),
    "oceania":        ("@oceania", "🇦🇺🇳🇿"),
    "france":         ("@fr", "🇫🇷"),
    "united_kingdom": ("@uk", "🇬🇧"),
    "iberia":         ("@iberia", "🇪🇸🇵🇹"),
    "csee":           ("@csee", "🌍"),
    "east_asia":      ("@east-asia", "🇯🇵🇰🇷🇭🇰"),
    "sea":            ("@sea", "🇸🇬🇹🇭"),
    "uae":            ("@uae", "🇦🇪"),
}

def build_summary_blocks(mk, report_url):
    meta = mk["meta"]; hl = mk["market_summary"]["headlines"]; km = hl["key_metrics"]
    market = meta["market"]
    slug = meta.get("market_slug", "")
    wk = f"{meta['week_start']} → {meta['week_end']}"
    handle, flag = MARKET_TEAM.get(slug, ("", ""))
    greet = (f"Hello team {handle}  {flag}\n\n") if handle else ""

    def kmline(idx, label, key, money=False, pctval=False):
        d = km.get(key, {})
        w0 = d.get("w0"); dp = d.get("delta_pct")
        val = fmt_money(w0) if money else (f"{w0:.2f}%" if pctval and w0 is not None else (f"{w0:,.0f}" if w0 is not None else "—"))
        return f"{idx}. {label}: {val}, {fmt_pct(dp)} WoW {dir_emoji(dp)}"

    head = (
        greet +
        f"📊 *{market} — Weekly Review*  ·  _{wk}_\n\n"
        f"Revenue: *{fmt_money(hl.get('revenue_w0'))}* "
        f"({fmt_pct(hl.get('wow_pct'))} WoW {dir_emoji(hl.get('wow_pct'))} · "
        f"{fmt_pct(hl.get('yoy_pct'))} YoY {dir_emoji(hl.get('yoy_pct'))})  ·  "
        f"Paid ROI *{fmt_plain_pct(hl.get('roi_w0_pct'),0)}*"
    )
    metrics = "*Main metrics this week (WoW):*\n" + "\n".join([
        kmline(1, "Revenue", "revenue", money=True),
        kmline(2, "Paid ROI", "paid_roi", pctval=True),
        kmline(3, "Paid clicks", "paid_clicks"),
        kmline(4, "Paid CVR", "paid_cvr", pctval=True),
        kmline(5, "AOV", "aov", money=True),
        kmline(6, "Take rate", "tr_pct", pctval=True),
    ])

    # Top movers — the report's own TOP DROPS / TOP GAINS charts (biggest move,
    # 4-WK or WoW), top 5 each. Present in every market's headline, always
    # consistent with the report.
    drops, gains = trend_charts(mk)
    def bullets(rows, side):
        return "\n".join(mover_bullet(r, side) for r in rows[:5])
    top_drops = "🔻 *Top 5 Drops (WoW)*\n" + bullets(drops, "drop")
    top_gains = "🔺 *Top 5 Gains (WoW)*\n" + bullets(gains, "gain")

    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": head}},
        {"type": "section", "text": {"type": "mrkdwn", "text": metrics}},
        {"type": "section", "text": {"type": "mrkdwn", "text": top_drops}},
        {"type": "section", "text": {"type": "mrkdwn", "text": top_gains}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": "🧵 Losing Money · RPC Fluctuations Down · RPC Fluctuations Up tables in thread ⬇️"}]},
        report_ctx(report_url),
    ]


# =============================================================================
# THREE TABLES (MSG 1 thread replies)
# =============================================================================
def report_ctx(report_url, extra="", action=False):
    # Prominent section (not muted context) so the report link stands out.
    lines = []
    if action:
        lines.append("👉 *Action needed:* review each CE and set a status + note in the report's bucket section.")
    if extra:
        lines.append(extra)
    lines.append(f"📊 *<{report_url}|Open the weekly report →>*")
    return {"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}

# These 3 tables are built from Google Ads data only — called out above each table.
GOOGLE_ADS_ONLY = {"type": "context", "elements": [{"type": "mrkdwn",
        "text": "🔸 _Figures below are based on *Google Ads* data only._"}]}

TABLE_CAPS = lambda n: [14, 26] + [20] * (n - 2)  # CE ID | CE | rest

def table_losing(mk, report_url):
    # Mirror the report's §4 Losing Money bucket exactly (buckets_final.defend.losing_money):
    # full-waste pinned top, then bleeders + ERODERS merged worst-first by CM2 lost/wk
    # (report_template.html merges the same two lists the same way).
    #   Bleeding = ROI < 100% (losing money) · Eroding = ROI ≥ 100% but CM2 dropping ≥ $1k
    #   vs its 4-week average · Full waste = spend with 0 conversions.
    # Eroders were previously OMITTED here, so GM alerts silently dropped the biggest quiet
    # losers — high-ROI CEs shedding CM2 (e.g. Vatican Museums, Niagara Falls). lost_wk is the
    # unified positive "CM2 lost/wk vs healthy baseline" magnitude (cm2_bleed_wk has mixed signs
    # across the two lanes, so it can't rank them together).
    lm = (mk.get("buckets_final") or {}).get("defend", {}).get("losing_money", {}) or {}
    waste = [(r, "waste") for r in (lm.get("full_waste") or [])]
    merged = sorted([(r, "bleed") for r in (lm.get("bleeders") or [])]
                    + [(r, "erode") for r in (lm.get("eroding") or [])],
                    key=lambda t: -(t[0].get("lost_wk") or 0))
    ordered = waste + merged
    def stat(r, kind):
        if kind == "waste": return "FULL WASTE"
        if kind == "erode": return "Eroding"
        if r.get("recovering"): return "Recovering"
        s = r.get("status")
        return f"{s} bleed" if s else "—"
    hdr = ["CE ID", "CE", "Status", "ROI", "ROI Δ4w", "CM2 lost/wk", "RPC Δ4w", "CPC Δ4w"]
    body = [[r.get("ce_id"), r.get("ce_name"), stat(r, k), fmt_plain_pct(r.get("roi"),0),
             f"{r.get('roi_v4'):+.0f}pp" if r.get("roi_v4") is not None else "—",
             fmt_money(r.get("lost_wk")), fmt_pct(r.get("rpc_v4"),0),
             fmt_pct(r.get("cpc_v4"),0)] for r, k in ordered]
    # Paginate rows into fenced sections of ROWS_PER_BLOCK each — a single fenced
    # code block can't exceed Slack's ~3000-char section limit and can't be split
    # mid-fence, so we chunk the rows themselves (eroders push headout past 60 CEs).
    ROWS_PER_BLOCK = 18
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": f"🔴 Losing Money · {len(ordered)} CEs", "emoji": True}},
        GOOGLE_ADS_ONLY,
    ]
    for i in range(0, len(body) or 1, ROWS_PER_BLOCK):
        chunk = body[i:i + ROWS_PER_BLOCK]
        if not chunk and i:
            break
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": render_table(hdr, chunk, caps=TABLE_CAPS(len(hdr)))}})
    blocks.append(report_ctx(report_url, action=True))
    return blocks

# RPC fluctuation rows filtered by direction ("down" or "up")
FLUCT_META = {
    "down": ("🔻", "RPC Fluctuations Down"),
    "up":   ("🔺", "RPC Fluctuations Up"),
}
# Source the report's actual §4 Fluctuations buckets (buckets_final), NOT the raw
# bucket1_fluctuations list — so the alert's CE set matches the report/Ledger exactly.
# Report §4 ↓ = defend.seasonality_down · ↑ = compound.seasonality_up (processed + matured-window).
# Vercel report filename = publish_weekly's ledger slug (NOT the config slug). Must match
# scripts/weekly_report/publish_weekly.py:MARKET_META or the "→ weekly report" link 404s.
LEDGER_SLUG = {
    "north_america": "north-america", "italy": "italy", "oceania": "oceania",
    "france": "france", "united_kingdom": "united-kingdom", "iberia": "iberia",
    "csee": "csee", "uae": "united-arab-emirates",
    "east_asia": "east-asia-jpn-sk-hk", "sea": "sea-sin-tha",
}

FLUCT_SRC = {"down": ("defend", "seasonality_down"), "up": ("compound", "seasonality_up")}
_DRV_DELTA = {"cvr": "cvr_d", "aov": "aov_d", "cr": "cr_d", "tr": "tr_d"}

def fluct_rows(mk, direction):
    fam, key = FLUCT_SRC[direction]
    return (mk.get("buckets_final") or {}).get(fam, {}).get(key, []) or []

def table_fluct(mk, report_url, direction):
    emoji, title = FLUCT_META[direction]
    rows = fluct_rows(mk, direction)              # engine order — matches the report §4 rows
    def driver(r):
        dk = _DRV_DELTA.get(r.get("dominant_key"))
        d = fmt_pct(r.get(dk), 0) if dk and r.get(dk) is not None else ""
        return f"{r.get('dominant', '')} {d}".strip()
    hdr = ["CE ID", "CE", "Alert", "Swing%", "Root driver", "28d ROI", "Read"]
    body = [[r.get("ce_id"), r.get("ce_name"), r.get("alert_type"),
             fmt_pct(r.get("swing_pct"), 0), driver(r),
             fmt_plain_pct(r.get("roi_4w"), 0), r.get("verdict", "—")] for r in rows[:20]]
    return [
        {"type": "header", "text": {"type": "plain_text", "text": f"{emoji} {title} · {len(rows)} CEs", "emoji": True}},
        GOOGLE_ADS_ONLY,
        {"type": "section", "text": {"type": "mrkdwn", "text": render_table(hdr, body, caps=TABLE_CAPS(len(hdr)))}},
        report_ctx(report_url, action=True),
    ]


# =============================================================================
# TOP-10 DROPS (MSG 2) + per-CE RCA threads
# =============================================================================
def build_notable(mk, report_url):
    """MSG 2 — week-over-week revenue RCA for this week's TOP MOVERS (the report's
    TOP DROPS / TOP GAINS charts, top 5 each). The parent message is a topline +
    a drops/gains direction table; each mover's per-CE diagnosis is a thread
    reply, emitted as a `{"$rca": "<ce_id>"}` reference and computed later
    (user-based, from BigQuery) by weekly_rca_helper.py. Returns the ordered,
    de-duplicated CE-id list so main() can pass it to weekly_rca_helper.py."""
    drops, gains = trend_charts(mk)
    drops, gains = drops[:5], gains[:5]

    # Topline only — the drop/gain tables live in the summary message just above,
    # so we don't repeat them here; the thread carries the per-CE RCA.
    topline = (f"🚨 *Weekly Movers · {mk['meta']['market']}*\n"
               "PFA the week-over-week revenue RCA for this week's top movers 👇")

    # RCA set = the chart movers (drops then gains), de-duplicated, in order.
    # Each is a {"$rca": id} reference resolved to BigQuery-backed blocks by
    # post_message.py using weekly_rca_helper.py's output.
    ce_ids, threads, seen = [], [], set()
    for r in drops + gains:
        cid = str(r["ce_id"])
        if cid in seen: continue
        seen.add(cid); ce_ids.append(cid)
        threads.append({"$rca": cid})

    msg_blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": topline}},
        report_ctx(report_url, "🧵 Per-CE revenue diagnosis in thread ⬇️"),
    ]
    return msg_blocks, threads, ce_ids


# =============================================================================
def main():
    ap = argparse.ArgumentParser(description="Build the weekly market alert payload from the report HTML")
    ap.add_argument("--file", required=True)
    ap.add_argument("--market-slug", default=None, help="e.g. north_america; else --market-index")
    ap.add_argument("--market-index", type=int, default=0)
    ap.add_argument("--report-url", default=None, help="Vercel weekly report URL; else derived from slug")
    ap.add_argument("--out", default="payload_weekly.json")
    args = ap.parse_args()

    mk = load_market(Path(args.file).expanduser(), args.market_slug, args.market_index)
    slug = mk["meta"]["market_slug"]
    report_url = args.report_url or f"https://market-notebook.vercel.app/weekly-report-{LEDGER_SLUG.get(slug, slug.replace('_','-'))}"

    summary = build_summary_blocks(mk, report_url)
    t_los = table_losing(mk, report_url)
    t_dn  = table_fluct(mk, report_url, "down")
    t_up  = table_fluct(mk, report_url, "up")
    notable_blocks, rca_threads, rca_ce_ids = build_notable(mk, report_url)

    week_start = mk["meta"]["week_start"]
    week_end   = mk["meta"]["week_end"]

    payload = {
        "messages": [
            {"fallback": f"{mk['meta']['market']} — Weekly Review",
             "blocks": summary,
             "threads": [
                 {"fallback": "Losing Money", "blocks": t_los},
                 {"fallback": "RPC Fluctuations Down", "blocks": t_dn},
                 {"fallback": "RPC Fluctuations Up", "blocks": t_up},
             ]},
            {"fallback": f"Weekly Movers — {mk['meta']['market']}",
             "blocks": notable_blocks,
             "threads": rca_threads},
        ],
        # Hand-off to weekly_rca_helper.py: the exact CE ids + week to compute
        # the BigQuery-backed, user-based per-CE diagnosis blocks for the
        # {"$rca": ...} thread references above.
        "_rca": {"ce_ids": rca_ce_ids, "week_start": week_start, "week_end": week_end},
    }
    Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"✓ wrote {args.out}  ·  market={mk['meta']['market']}  ·  report={report_url}")
    print(f"  MSG1 summary + 3 tables · MSG2 top-{len(rca_threads)} drops + {len(rca_threads)} $rca thread refs")
    # Machine-readable hand-off lines — copy these into the weekly_rca_helper.py call.
    print("RCA_CE_IDS=" + ",".join(str(c) for c in rca_ce_ids))
    print(f"WEEK={week_start}..{week_end}")


if __name__ == "__main__":
    main()
