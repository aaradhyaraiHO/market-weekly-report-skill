#!/usr/bin/env python3
"""
Publish weekly market reports to The Ledger's **Weekly view** — a trajectory MATRIX.

Weekly's job is week-over-week movement, so the homepage is a matrix: markets as
rows (region-grouped), the trailing N weeks as columns (current week highlighted),
each cell = revenue + WoW%. Columns come straight from each market's snapshot
`market_summary.weekly[]` (12-wk series), so one publish yields a full matrix.
Clicking a market row opens its full current-week report.

Shares the top nav + Monthly⇄Weekly toggle with the monthly card-grid ledger, but
the body is a matrix (different question: "where is each market heading?").

Usage:
    python3 publish_weekly.py <market|all> --week YYYY-MM-DD [--cols N]

Deploy (USER, from ~/analytics):  vercel deploy --prod --cwd market-notebook-v2
Local preview:                    open market-notebook-v2/weekly.html
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import sys
from pathlib import Path

import config

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
CACHE_DIR = REPO_ROOT / ".cache" / "weekly_report"
REPORT_DIR_V1 = REPO_ROOT / "thoughts" / "shared" / "weekly-report-v1"
REPORT_DIR_V2 = REPO_ROOT / "thoughts" / "shared" / "weekly-report-v2"
# Compatibility alias for existing callers/tests. V1 remains the safe default.
REPORT_DIR = REPORT_DIR_V1
N_COLS = 6


def notebook_dir() -> Path:
    env = os.environ.get("MMR_NOTEBOOK_DIR")
    return Path(os.path.expanduser(env)) if env else Path(os.path.expanduser("~/analytics/market-notebook-v2"))


# weekly slug -> (ledger slug, name, flag, region)
MARKET_META = {
    "headout": ("headout", "Headout — all markets", "🌐", "Portfolio"),
    "north_america": ("north-america", "North America", "🇺🇸", "Americas"),
    "italy": ("italy", "Italy", "🇮🇹", "Southern Europe"),
    "iberia": ("iberia", "Iberia", "🇪🇸", "Southern Europe"),
    "france": ("france", "France", "🇫🇷", "Western Europe"),
    "united_kingdom": ("united-kingdom", "United Kingdom", "🇬🇧", "British Isles"),
    "csee": ("csee", "CSEE", "🇪🇺", "Central & SE Europe"),
    "uae": ("united-arab-emirates", "United Arab Emirates", "🇦🇪", "Middle East"),
    "gcc": ("gcc", "GCC", "🇸🇦", "Middle East"),
    "north_africa": ("north-africa", "North Africa", "🇪🇬", "Middle East"),
    "rest_of_mea": ("rest-of-mea", "Rest of MEA", "🇿🇦", "Middle East"),
    "east_asia": ("east-asia-jpn-sk-hk", "East Asia (JPN/SK/HK)", "🇯🇵", "East Asia"),
    "sea": ("sea-sin-tha", "SEA (SIN+THA)", "🇸🇬", "Southeast Asia"),
    "oceania": ("oceania", "Oceania", "🇦🇺", "Oceania"),
    # Long-tail markets (2026-08-04)
    "benelux": ("benelux", "Benelux", "🇧🇪", "Western Europe"),
    "nordics": ("nordics", "Nordics", "🇸🇪", "Northern Europe"),
    "south_america": ("south-america", "South America", "🇧🇷", "Americas"),
    "mexico_central_america": ("mexico-central-america", "Mexico & Central America", "🇲🇽", "Americas"),
}
REGION_ORDER = ["Portfolio", "Americas", "Southern Europe", "Western Europe", "Northern Europe",
                "British Isles", "Central & SE Europe", "Middle East", "East Asia", "Southeast Asia", "Oceania"]


def _money(v):
    if v is None:
        return "—"
    v = float(v)
    return f"${v/1_000_000:.2f}M" if abs(v) >= 1_000_000 else f"${v/1000:.0f}K"


def _pct(v, dp=1):
    return "—" if v is None else f"{'+' if v >= 0 else ''}{float(v):.{dp}f}%"


def _collabel(iso):
    d = dt.date.fromisoformat(iso)
    return d.strftime("%b %-d")


def _sparkline(revs, w=120, h=30, pad=3):
    pts = [float(r) for r in revs if r is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts); span = (hi - lo) or 1.0; n = len(pts)
    xs = lambda i: round(pad + i * (w - 2 * pad) / (n - 1), 1)
    ys = lambda v: round(h - pad - (v - lo) * (h - 2 * pad) / span, 1)
    line = "M" + " L".join(f"{xs(i)} {ys(v)}" for i, v in enumerate(pts))
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}"><path d="{line}" '
            f'fill="none" stroke="#8000FF" stroke-width="1.5"/>'
            f'<circle cx="{xs(n-1)}" cy="{ys(pts[-1])}" r="2.3" fill="#8000FF"/></svg>')


def weekly_series(snap: dict, n: int):
    """Trailing n weeks: [{week, rev, wow_pct}] from market_summary.weekly[]."""
    wk = snap["market_summary"].get("weekly", []) or []
    rows = [(w.get("week"), w.get("revenue")) for w in wk if w.get("week")]
    out = []
    for i, (week, rev) in enumerate(rows):
        prev = rows[i - 1][1] if i > 0 else None
        wow = (100.0 * (rev / prev - 1)) if (rev is not None and prev) else None
        out.append({"week": week, "rev": rev, "wow_pct": round(wow, 1) if wow is not None else None})
    return out[-n:]


def load_state(deploy):
    p = deploy / "weekly_state.json"
    return json.loads(p.read_text()) if p.exists() else {"markets": []}


def upsert(state, entry):
    for i, m in enumerate(state["markets"]):
        if m["slug"] == entry["slug"]:
            state["markets"][i] = entry; return
    state["markets"].append(entry)


def publish_market(slug, week, deploy, n, report_dir=None):
    meta = MARKET_META.get(slug)
    if not meta:
        print(f"  ! no ledger metadata for '{slug}' — skipping"); return None
    ledger_slug, name, flag, region = meta
    snap_p = CACHE_DIR / f"snapshot_{slug}_{week}.json"
    rep_p = (report_dir or REPORT_DIR) / f"report_{slug}_{week}.html"
    if not snap_p.exists() or not rep_p.exists():
        print(f"  ! missing snapshot/report for {slug} {week} — run the producer first"); return None
    shutil.copyfile(rep_p, deploy / f"weekly-report-{ledger_slug}.html")            # current alias
    shutil.copyfile(rep_p, deploy / f"weekly-report-{ledger_slug}-{week}.html")     # week archive → Ledger history
    series = weekly_series(json.loads(snap_p.read_text()), n)
    print(f"  ✓ {name}: {_money(series[-1]['rev'])} · WoW {_pct(series[-1]['wow_pct'])} "
          f"({len(series)} wks)")
    return {"slug": ledger_slug, "name": name, "flag": flag, "region": region,
            "report_path": f"weekly-report-{ledger_slug}.html", "series": series,
            "spark": _sparkline([s["rev"] for s in series])}


def publish_headout(week, deploy, n, report_dir=None):
    """Headout = the true-global rollup (all ~69 markets). Rendered as a hero banner
    above the market matrix (not a region row), linking to its own full report."""
    snap_p = CACHE_DIR / f"snapshot_headout_{week}.json"
    rep_p = (report_dir or REPORT_DIR) / f"report_headout_{week}.html"
    if not snap_p.exists() or not rep_p.exists():
        print(f"  ! no headout snapshot/report for {week} — run build_global.py first"); return None
    shutil.copyfile(rep_p, deploy / "weekly-report-headout.html")
    shutil.copyfile(rep_p, deploy / f"weekly-report-headout-{week}.html")           # week archive
    snap = json.loads(snap_p.read_text())
    series = weekly_series(snap, n)
    nm = (snap.get("meta") or {}).get("n_markets")
    print(f"  ✓ Headout (all markets): {_money(series[-1]['rev'])} · WoW {_pct(series[-1]['wow_pct'])} "
          f"({nm} markets, {len(series)} wks)")
    return {"report_path": "weekly-report-headout.html", "series": series,
            "spark": _sparkline([s["rev"] for s in series]), "n_markets": nm}


def _hero_sparkline(revs, w=140, h=40, pad=3):
    pts = [float(r) for r in revs if r is not None]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts); span = (hi - lo) or 1.0; n = len(pts)
    xs = lambda i: round(pad + i * (w - 2 * pad) / (n - 1), 1)
    ys = lambda v: round(h - pad - (v - lo) * (h - 2 * pad) / span, 1)
    line = "M" + " L".join(f"{xs(i)} {ys(v)}" for i, v in enumerate(pts))
    fill = line + f" L{xs(n-1)} {h} L{xs(0)} {h} Z"
    cx, cy = xs(n - 1), ys(pts[-1])
    return (f'<svg viewBox="0 0 {w} {h}" width="100%" height="46" style="display:block" preserveAspectRatio="none">'
            f'<defs><linearGradient id="hfill" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="#B478FF" stop-opacity="0.45"/>'
            f'<stop offset="100%" stop-color="#B478FF" stop-opacity="0"/></linearGradient></defs>'
            f'<path d="{fill}" fill="url(#hfill)"/>'
            f'<path d="{line}" fill="none" stroke="#B478FF" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{cx}" cy="{cy}" r="2.8" fill="#fff"/></svg>')


def _headout_hero(ho):
    if not ho or not ho.get("series"):
        return ""
    s = ho["series"][-1]
    wow = s.get("wow_pct")
    wow_col = "#12A150" if (wow is not None and wow >= 1) else "#E5384F" if (wow is not None and wow <= -1) else "#B5AEC6"
    arr = "▲" if (wow is not None and wow >= 1) else "▼" if (wow is not None and wow <= -1) else "·"
    spark = _hero_sparkline([x["rev"] for x in ho["series"]])
    nm = ho.get("n_markets") or ""
    week_label = s.get("week", "")
    if week_label:
        try:
            week_label = dt.date.fromisoformat(week_label).strftime("Week of %b %-d")
        except Exception:
            pass
    return (
        f'<a href="{ho["report_path"]}" style="display:block;margin-top:20px;position:relative;overflow:hidden;'
        f'border-radius:22px;color:#fff;'
        f'background:radial-gradient(1200px 500px at 88% -10%,#3B1470 0%,#1C1726 46%,#14101E 100%);'
        f'box-shadow:0 24px 60px rgba(28,23,38,0.32)">'
        # glow overlay
        f'<div style="position:absolute;inset:0;background:radial-gradient(600px 300px at 92% 0%,rgba(128,0,255,0.35),transparent 60%);pointer-events:none"></div>'
        f'<div style="position:relative;padding:30px 36px;display:flex;align-items:center;gap:32px">'
        # LEFT
        f'<div style="flex:1;min-width:0">'
        # pill
        f'<div style="display:inline-flex;align-items:center;gap:9px;background:rgba(128,0,255,0.18);'
        f'border:1px solid rgba(180,120,255,0.35);border-radius:999px;padding:5px 13px;'
        f'font:700 10.5px \'Hanken Grotesk\';letter-spacing:.14em;text-transform:uppercase;color:#D9C2FF">'
        f'<span style="width:7px;height:7px;border-radius:50%;background:#B478FF;box-shadow:0 0 0 4px rgba(180,120,255,0.22)"></span>'
        f'Portfolio rollup · Live</div>'
        # title
        f'<div style="margin-top:16px;font:800 38px/1 \'Figtree\';letter-spacing:-.03em">Headout</div>'
        f'<div style="margin-top:6px;font:600 12px \'Hanken Grotesk\';letter-spacing:.05em;text-transform:uppercase;color:#B5AEC6">'
        f'{nm} markets · {week_label}</div>'
        # CTA
        f'<div style="display:inline-flex;align-items:center;gap:8px;margin-top:18px;background:#8000FF;'
        f'padding:10px 20px;border-radius:10px;box-shadow:0 10px 26px rgba(128,0,255,0.4);'
        f'font:800 13px \'Figtree\';letter-spacing:-.01em">View full report <span style="font-size:16px;line-height:1">→</span></div>'
        f'</div>'
        # RIGHT: stat card
        f'<div style="flex:0 0 280px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.12);'
        f'border-radius:18px;padding:22px 24px;backdrop-filter:blur(6px)">'
        f'<div style="font:700 10.5px \'Hanken Grotesk\';letter-spacing:.14em;text-transform:uppercase;color:#9C93B4">Weekly revenue</div>'
        f'<div style="display:flex;align-items:flex-end;gap:10px;margin-top:8px">'
        f'<div style="font:800 36px/1 \'Figtree\';letter-spacing:-.03em">{_money(s["rev"])}</div>'
        f'<div style="font:700 13px \'Hanken Grotesk\';color:{wow_col};padding-bottom:3px">{arr} {_pct(wow)} WoW</div></div>'
        # sparkline
        f'<div style="margin-top:16px">'
        f'<div style="font:700 10.5px \'Hanken Grotesk\';letter-spacing:.12em;text-transform:uppercase;color:#9C93B4">Trailing weeks</div>'
        f'<div style="margin-top:6px">{spark}</div></div>'
        f'</div>'
        f'</div></a>'
    )


# --------------------------------------------------------------------------- #
def _cell(s, is_current, ledger_slug=None, deploy=None):
    if not s or s.get("rev") is None:
        return '<td class="cell"><span class="dash">—</span></td>'
    wow = s.get("wow_pct")
    col = "#12A150" if (wow is not None and wow >= 1) else "#E5384F" if (wow is not None and wow <= -1) else "#9A92AC"
    arr = "▲" if (wow is not None and wow >= 1) else "▼" if (wow is not None and wow <= -1) else "·"
    wtxt = "" if wow is None else f'<div class="wow" style="color:{col}">{arr} {_pct(wow)}</div>'
    inner = f'<div class="rev">{_money(s["rev"])}</div>{wtxt}'
    # Whole-cell click → THAT week's archived report (Ledger history). Put the handler on the
    # <td> itself (not just an <a> around the number) so clicking anywhere in the cell — padding
    # included — opens that week; otherwise a click in the cell's padding fell through to the
    # row's current-week onclick. stopPropagation stops that row handler. Weeks without an
    # archive get no handler and fall through to the row (current report).
    click = ""
    if ledger_slug and deploy is not None:
        arch = f"weekly-report-{ledger_slug}-{s['week']}.html"
        if (deploy / arch).exists():
            click = f' onclick="event.stopPropagation();location.href=\'{arch}\'" style="cursor:pointer"'
    return f'<td class="cell{" cur" if is_current else ""}"{click}>{inner}</td>'


def render_matrix(state, week, cols, deploy=None):
    labels = "".join(f'<th class="wk{" cur" if c == cols[-1] else ""}">{_collabel(c)}'
                     f'{"<div class=cur-tag>current</div>" if c == cols[-1] else ""}</th>' for c in cols)
    body = ""
    live = [m for m in state["markets"] if m.get("series")]
    for region in REGION_ORDER + sorted({m["region"] for m in live} - set(REGION_ORDER)):
        rms = [m for m in live if m["region"] == region]
        if not rms:
            continue
        body += (f'<tr class="region"><td colspan="{len(cols)+1}">{region}'
                 f'<span class="rcount">{len(rms)} market{"s" if len(rms) != 1 else ""}</span></td></tr>')
        for m in rms:
            by = {s["week"]: s for s in m["series"]}
            cells = "".join(_cell(by.get(c), c == cols[-1], m["slug"], deploy) for c in cols)
            body += (f'<tr class="mrow" onclick="location.href=\'{m["report_path"]}\'">'
                     f'<td class="mkt"><span class="flag">{m["flag"]}</span>'
                     f'<span class="mname">{m["name"]}</span>'
                     f'<span class="mreg">{m["region"]}</span>'
                     f'<span class="msp">{m["spark"]}</span></td>{cells}</tr>')
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Weekly Ledger · Market Weekly</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800;900&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
 *{{box-sizing:border-box}} body{{margin:0;font-family:'Hanken Grotesk',system-ui,sans-serif;background:#F3F0F9;color:#1C1726;-webkit-font-smoothing:antialiased}}
 a{{color:inherit;text-decoration:none}} .wrap{{max-width:1400px;margin:0 auto;padding:0 40px}}
 .toggle{{display:flex;gap:4px;background:#fff;border:1px solid #E7E1F1;border-radius:999px;padding:3px}}
 .toggle a{{font:700 13px 'Hanken Grotesk';padding:6px 15px;border-radius:999px;color:#6E6680}} .toggle a.on{{background:#8000FF;color:#fff}}
 .board{{width:100%;border-collapse:separate;border-spacing:0;margin-top:24px;background:#fff;border:1px solid #EBE5F6;border-radius:18px;overflow:hidden;box-shadow:0 2px 14px rgba(88,0,170,.05)}}
 .board th,.board td{{padding:12px 14px;text-align:right}}
 .board thead th{{font:700 12px 'Figtree';color:#1C1726;border-bottom:2px solid #ECE6F8;background:#FBFAFF}}
 .board thead th.wk.cur{{color:#8000FF;background:#F4ECFF}} .cur-tag{{font:700 8px 'Hanken Grotesk';letter-spacing:.1em;text-transform:uppercase;color:#8000FF}}
 .board th.mkth{{text-align:left;font:700 10px 'Hanken Grotesk';letter-spacing:.1em;text-transform:uppercase;color:#9A92AC}}
 tr.region td{{text-align:left;font:700 10px 'Hanken Grotesk';letter-spacing:.12em;text-transform:uppercase;color:#8A82A0;background:#F7F4FD;padding:8px 14px}}
 tr.region .rcount{{float:right;color:#B4ABC7;text-transform:none;letter-spacing:0;font-weight:600}}
 tr.mrow{{cursor:pointer;transition:background .12s}} tr.mrow:hover{{background:#FBF9FF}}
 tr.mrow td{{border-bottom:1px solid #F1ECFA}}
 td.mkt{{text-align:left;min-width:230px}} .flag{{font-size:18px}} .mname{{font:800 15px 'Figtree';margin-left:7px}}
 .mreg{{display:block;font:600 10px 'Hanken Grotesk';letter-spacing:.04em;text-transform:uppercase;color:#B4ABC7;margin-top:1px}}
 .msp{{display:block;margin-top:4px}}
 td.cell .rev{{font:800 15px 'Figtree';font-variant-numeric:tabular-nums}} td.cell .wow{{font:700 11px 'Hanken Grotesk';font-variant-numeric:tabular-nums;margin-top:1px}}
 td.cell.cur{{background:#FAF6FF}} td.cell .dash{{color:#C4BCD6}}
 @media (max-width:900px){{.board{{font-size:12px}}}}
</style></head><body>
<div style="position:sticky;top:0;z-index:40;backdrop-filter:blur(12px);background:rgba(243,240,249,0.84);border-bottom:1px solid #E7E1F1">
 <div class="wrap" style="padding:13px 40px;display:flex;align-items:center;justify-content:space-between;gap:18px">
  <div style="display:flex;align-items:center;gap:11px">
   <span style="flex:none;width:26px;height:26px;border-radius:50% 50% 50% 4px;background:#8000FF"></span>
   <span style="font:800 16px 'Figtree'">Market Weekly</span><span style="color:#6E6680;font-size:13px">· The Ledger</span></div>
  <div class="toggle"><a href="/">Monthly</a><a class="on" href="/weekly">Weekly</a></div>
 </div>
</div>
<div class="wrap" style="padding:36px 40px 100px">
 <div style="font:700 12px 'Hanken Grotesk';letter-spacing:.2em;text-transform:uppercase;color:#8000FF">Market Weekly Review · Trajectory</div>
 <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:20px;margin-top:12px">
  <h1 style="font:800 52px/1 'Figtree';letter-spacing:-.03em;margin:0">The Weekly <span style="font-style:italic;font-weight:900;color:#8000FF">Ledger</span></h1>
  <div style="text-align:right;font:600 12px 'Hanken Grotesk';letter-spacing:.08em;text-transform:uppercase;color:#9A92AC;line-height:1.7">
   <div style="color:#6E6680">Week of {week}</div><div>{len(live)} market{"s" if len(live) != 1 else ""} · last {len(cols)} weeks</div></div>
 </div>
 {_headout_hero(state.get("headout"))}
 <table class="board"><thead><tr><th class="mkth">Market</th>{labels}</tr></thead><tbody>{body}</tbody></table>
 <div style="margin-top:14px;font:600 11px 'Hanken Grotesk';color:#9A92AC">Each cell: weekly revenue + WoW%. Click a row for the full report, or a cell for that week's report. Revenue = predicted.</div>
 <div style="margin-top:5px;font:600 11px 'Hanken Grotesk';color:#B4ABC7">Weeks run <b>Sun–Sat</b> from w/c 2026-07-26. Earlier columns are the pre-shift Mon–Sun reports (≈1 day offset), kept for history.</div>
</div></body></html>"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("market")
    ap.add_argument("--week", required=True)
    ap.add_argument("--cols", type=int, default=N_COLS)
    ap.add_argument("--renderer", choices=("v1", "v2"), default="v1",
                    help="report artifact set to stage; V1 remains the default")
    ap.add_argument(
        "--skip-perf-sheet",
        action="store_true",
        help="stage report artifacts without the optional Google Sheet exports",
    )
    args = ap.parse_args(argv)

    deploy = notebook_dir()
    if not deploy.exists():
        sys.exit(f"notebook dir not found: {deploy} (set MMR_NOTEBOOK_DIR)")
    # 'headout' publishes only the portfolio hero; 'all' does the 10 markets + refreshes headout if present
    targets = (list(config.MARKETS) if args.market == "all"
               else [] if args.market == "headout" else [args.market])
    report_dir = REPORT_DIR if args.renderer == "v1" else REPORT_DIR_V2
    print(f"Weekly Ledger (matrix) · week {args.week} · {targets or ['headout']}"
          f" · renderer {args.renderer}\n  reports: {report_dir}\n  deploy: {deploy}")

    state = load_state(deploy)
    n = 0
    for slug in targets:
        e = publish_market(slug, args.week, deploy, args.cols, report_dir=report_dir)
        if e:
            upsert(state, e); n += 1
    if args.market in ("headout", "all"):
        ho = publish_headout(args.week, deploy, args.cols, report_dir=report_dir)
        if ho:
            state["headout"] = ho; n += 1
    if not n:
        sys.exit("nothing published — run weekly_market_report.py / build_global.py first")
    # union of column weeks across markets + headout (they share the same Mondays), trailing N
    weeks = sorted({s["week"] for m in state["markets"] for s in m.get("series", [])}
                   | {s["week"] for s in state.get("headout", {}).get("series", [])})[-args.cols:]
    state["edition"] = {"week": args.week, "cols": weeks}
    (deploy / "weekly_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False))
    (deploy / "weekly.html").write_text(render_matrix(state, args.week, weeks, deploy))
    print(f"\n  wrote {deploy/'weekly.html'} + weekly_state.json ({n} market(s), {len(weeks)} cols)")
    print(f"\n  open {deploy/'weekly.html'}")
    print("  vercel deploy --prod --cwd market-notebook-v2   # from ~/analytics — USER runs")

    # Weekly Flagged export → perf sheet (Task 2). Runs once on a full `all` publish; writes the
    # `w/c <week>` tab (all markets, GM cols owned; perf's 3 cols untouched). Best-effort, main-only.
    if args.market == "all" and not args.skip_perf_sheet:
        try:
            import export_perf_sheet as eps
            camp_cat = eps._fetch_campaign_categories(args.week)   # campaign-level Category (one query)
            rows = []
            for slug in config.MARKETS:
                sp = CACHE_DIR / f"snapshot_{slug}_{args.week}.json"
                if not sp.exists():
                    continue
                snap = json.loads(sp.read_text())
                gm = eps._fetch_gm_actions(slug, args.week)
                rows += eps.rows_for_snapshot(snap, gm, camp_cat)
            if rows:
                ok, tab, txt = eps.write_weekly_tab(rows, args.week)
                print(f"  {'✓' if ok else '✗'} perf sheet: {len(rows)} rows → tab '{tab}'"
                      + ("" if ok else f"  [{txt[:120]}]"))
        except Exception as e:
            print(f"  ! perf-sheet export skipped: {e}")

        # Complete UNGATED Losing-Money view → its own "LM full (no gate)" tab in the same sheet.
        # Same engine at spend_gate=0 so perf's "every losing CE is listed" check always passes.
        # Separate tab — never touches the `w/c <week>` action tab. Best-effort, main-only.
        try:
            import export_full_lm as efl
            efl.write_tab(args.week, efl.build_rows(args.week, str(CACHE_DIR)))
        except Exception as e:
            print(f"  ! full-LM export skipped: {e}")


if __name__ == "__main__":
    main()
