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
REPORT_DIR = REPO_ROOT / "thoughts" / "shared" / "weekly-report-v1"
N_COLS = 6


def notebook_dir() -> Path:
    env = os.environ.get("MMR_NOTEBOOK_DIR")
    return Path(os.path.expanduser(env)) if env else Path(os.path.expanduser("~/analytics/market-notebook-v2"))


# weekly slug -> (ledger slug, name, flag, region)
MARKET_META = {
    "north_america": ("north-america", "North America", "🇺🇸", "Americas"),
    "italy": ("italy", "Italy", "🇮🇹", "Southern Europe"),
    "iberia": ("iberia", "Iberia", "🇪🇸", "Southern Europe"),
    "france": ("france", "France", "🇫🇷", "Western Europe"),
    "united_kingdom": ("united-kingdom", "United Kingdom", "🇬🇧", "British Isles"),
    "csee": ("csee", "CSEE", "🇪🇺", "Central & SE Europe"),
    "uae": ("united-arab-emirates", "United Arab Emirates", "🇦🇪", "Middle East"),
    "east_asia": ("east-asia-jpn-sk-hk", "East Asia (JPN/SK/HK)", "🇯🇵", "East Asia"),
    "sea": ("sea-sin-tha", "SEA (SIN+THA)", "🇸🇬", "Southeast Asia"),
    "oceania": ("oceania", "Oceania", "🇦🇺", "Oceania"),
}
REGION_ORDER = ["Americas", "Southern Europe", "Western Europe", "British Isles",
                "Central & SE Europe", "Middle East", "East Asia", "Southeast Asia", "Oceania"]


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


def publish_market(slug, week, deploy, n):
    meta = MARKET_META.get(slug)
    if not meta:
        print(f"  ! no ledger metadata for '{slug}' — skipping"); return None
    ledger_slug, name, flag, region = meta
    snap_p = CACHE_DIR / f"snapshot_{slug}_{week}.json"
    rep_p = REPORT_DIR / f"report_{slug}_{week}.html"
    if not snap_p.exists() or not rep_p.exists():
        print(f"  ! missing snapshot/report for {slug} {week} — run the producer first"); return None
    shutil.copyfile(rep_p, deploy / f"weekly-report-{ledger_slug}.html")
    series = weekly_series(json.loads(snap_p.read_text()), n)
    print(f"  ✓ {name}: {_money(series[-1]['rev'])} · WoW {_pct(series[-1]['wow_pct'])} "
          f"({len(series)} wks)")
    return {"slug": ledger_slug, "name": name, "flag": flag, "region": region,
            "report_path": f"weekly-report-{ledger_slug}.html", "series": series,
            "spark": _sparkline([s["rev"] for s in series])}


# --------------------------------------------------------------------------- #
def _cell(s, is_current):
    if not s or s.get("rev") is None:
        return '<td class="cell"><span class="dash">—</span></td>'
    wow = s.get("wow_pct")
    col = "#12A150" if (wow is not None and wow >= 1) else "#E5384F" if (wow is not None and wow <= -1) else "#9A92AC"
    arr = "▲" if (wow is not None and wow >= 1) else "▼" if (wow is not None and wow <= -1) else "·"
    wtxt = "" if wow is None else f'<div class="wow" style="color:{col}">{arr} {_pct(wow)}</div>'
    return (f'<td class="cell{" cur" if is_current else ""}">'
            f'<div class="rev">{_money(s["rev"])}</div>{wtxt}</td>')


def render_matrix(state, week, cols):
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
            cells = "".join(_cell(by.get(c), c == cols[-1]) for c in cols)
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
 <table class="board"><thead><tr><th class="mkth">Market</th>{labels}</tr></thead><tbody>{body}</tbody></table>
 <div style="margin-top:14px;font:600 11px 'Hanken Grotesk';color:#9A92AC">Each cell: weekly revenue + WoW%. Click a row for the full report. Revenue = predicted.</div>
</div></body></html>"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("market")
    ap.add_argument("--week", required=True)
    ap.add_argument("--cols", type=int, default=N_COLS)
    args = ap.parse_args(argv)

    deploy = notebook_dir()
    if not deploy.exists():
        sys.exit(f"notebook dir not found: {deploy} (set MMR_NOTEBOOK_DIR)")
    targets = list(config.MARKETS) if args.market == "all" else [args.market]
    print(f"Weekly Ledger (matrix) · week {args.week} · {targets}\n  deploy: {deploy}")

    state = load_state(deploy)
    n = 0
    for slug in targets:
        e = publish_market(slug, args.week, deploy, args.cols)
        if e:
            upsert(state, e); n += 1
    if not n:
        sys.exit("nothing published — run weekly_market_report.py first")
    # union of column weeks across markets (they share the same Mondays), trailing N
    weeks = sorted({s["week"] for m in state["markets"] for s in m.get("series", [])})[-args.cols:]
    state["edition"] = {"week": args.week, "cols": weeks}
    (deploy / "weekly_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False))
    (deploy / "weekly.html").write_text(render_matrix(state, args.week, weeks))
    print(f"\n  wrote {deploy/'weekly.html'} + weekly_state.json ({n} market(s), {len(weeks)} cols)")
    print(f"\n  open {deploy/'weekly.html'}")
    print("  vercel deploy --prod --cwd market-notebook-v2   # from ~/analytics — USER runs")


if __name__ == "__main__":
    main()
