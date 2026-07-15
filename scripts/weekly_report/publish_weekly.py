#!/usr/bin/env python3
"""
Publish weekly market reports to The Ledger's **Weekly view**.

For each market it: reads the cached weekly snapshot, copies the rendered HTML
into the market-notebook-v2 deploy dir as ``weekly-report-{slug}.html``, computes
the card toplines, upserts ``weekly_state.json`` (kept separate from the monthly
``ledger_state.json``), and re-renders ``weekly.html`` (served at ``/weekly`` via
cleanUrls). Mirrors the monthly ``publish_ledger.py`` pattern; single-week (no
edition switcher yet — that's deferred).

The Monthly ⇄ Weekly toggle is rendered on this page (Weekly active, Monthly → "/").
The matching link on the monthly index is a separate one-line edit to the monthly
render (see the fan-out plan).

Usage:
    python3 publish_weekly.py <market|all> --week YYYY-MM-DD [--spotlight <slug>]

Deploy (USER runs, from ~/analytics):
    vercel deploy --prod --cwd market-notebook-v2
Local preview:
    open market-notebook-v2/weekly.html
"""
from __future__ import annotations

import argparse
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


def notebook_dir() -> Path:
    env = os.environ.get("MMR_NOTEBOOK_DIR")
    if env:
        return Path(os.path.expanduser(env))
    return Path(os.path.expanduser("~/analytics/market-notebook-v2"))


# weekly config slug -> (ledger slug, display name, flag, region)
MARKET_META = {
    "north_america": ("north-america", "North America", "🇺🇸", "Americas"),
    "italy": ("italy", "Italy", "🇮🇹", "Southern Europe"),
    "oceania": ("oceania", "Oceania", "🇦🇺", "Oceania"),
    "france": ("france", "France", "🇫🇷", "Western Europe"),
    "united_kingdom": ("united-kingdom", "United Kingdom", "🇬🇧", "British Isles"),
    "iberia": ("iberia", "Iberia", "🇪🇸", "Southern Europe"),
    "csee": ("csee", "CSEE", "🇪🇺", "Central & SE Europe"),
    "east_asia": ("east-asia-jpn-sk-hk", "East Asia (JPN/SK/HK)", "🇯🇵", "East Asia"),
    "sea": ("sea-sin-tha", "SEA (SIN+THA)", "🇸🇬", "Southeast Asia"),
    "uae": ("united-arab-emirates", "United Arab Emirates", "🇦🇪", "Middle East"),
}


def _fmt_money(v):
    if v is None:
        return "—"
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    return f"${v/1000:.0f}K"


def _fmt_pct(v, dp=1):
    if v is None:
        return "—"
    return f"{'+' if v >= 0 else ''}{float(v):.{dp}f}%"


def _sparkline(revs, w=132, h=34, pad=3):
    pts = [float(r) for r in revs if r is not None]
    if len(pts) < 2:
        return {"line": "", "last": None}
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    n = len(pts)
    def x(i): return round(pad + i * (w - 2 * pad) / (n - 1), 1)
    def y(v): return round(h - pad - (v - lo) * (h - 2 * pad) / span, 1)
    line = "M" + " L".join(f"{x(i)} {y(v)}" for i, v in enumerate(pts))
    return {"line": line, "last": {"cx": x(n - 1), "cy": y(pts[-1])}, "w": w, "h": h}


def compute_topline(snap: dict) -> dict:
    h = snap["market_summary"]["headlines"]
    wh = h.get("week_header", {}) or {}
    tr = wh.get("trend", {}) or {}
    weekly = snap["market_summary"].get("weekly", []) or []
    revs = [r.get("revenue") for r in weekly]
    return {
        "rev": h.get("revenue_w0"),
        "wow_pct": h.get("wow_pct"),
        "yoy_pct": h.get("yoy_pct"),
        "roi_pct": h.get("roi1_w0_pct"),
        "week_type": wh.get("week_type") or "—",
        "dual": wh.get("dual_clock_label") or "",
        "n_drops": len(tr.get("top_droppers", [])),
        "n_gains": len(tr.get("top_gainers", [])),
        "spark": _sparkline(revs),
    }


def load_state(deploy: Path) -> dict:
    p = deploy / "weekly_state.json"
    if p.exists():
        return json.loads(p.read_text())
    return {"edition": {}, "markets": []}


def save_state(deploy: Path, state: dict) -> None:
    (deploy / "weekly_state.json").write_text(json.dumps(state, indent=2, ensure_ascii=False))


def upsert(state: dict, entry: dict) -> None:
    for i, m in enumerate(state["markets"]):
        if m["slug"] == entry["slug"]:
            state["markets"][i] = entry
            return
    state["markets"].append(entry)


def publish_market(slug: str, week: str, deploy: Path, spotlight: str | None) -> dict | None:
    meta = MARKET_META.get(slug)
    if not meta:
        print(f"  ! no ledger metadata for '{slug}' — skipping")
        return None
    ledger_slug, name, flag, region = meta
    snap_p = CACHE_DIR / f"snapshot_{slug}_{week}.json"
    rep_p = REPORT_DIR / f"report_{slug}_{week}.html"
    if not snap_p.exists() or not rep_p.exists():
        print(f"  ! missing snapshot or report for {slug} {week} — run the producer first")
        return None
    # copy the rendered report into the deploy dir
    dest = deploy / f"weekly-report-{ledger_slug}.html"
    shutil.copyfile(rep_p, dest)
    tl = compute_topline(json.loads(snap_p.read_text()))
    entry = {
        "slug": ledger_slug, "name": name, "flag": flag, "region": region,
        "report_path": dest.name, "live": True,
        "spotlight": (spotlight == slug or spotlight == ledger_slug),
        "toplines": tl,
    }
    print(f"  ✓ {name}: {_fmt_money(tl['rev'])} · WoW {_fmt_pct(tl['wow_pct'])} · "
          f"ROI {tl['roi_pct']:.0f}% · {tl['week_type']}  → {dest.name}")
    return entry


# --------------------------------------------------------------------------- #
# render weekly.html
# --------------------------------------------------------------------------- #
def _card(m: dict) -> str:
    t = m["toplines"]
    up = (t["wow_pct"] or 0) >= 0
    arrow = "▲" if up else "▼"
    col = "#12A150" if up else "#E5384F"
    sp = t["spark"]
    spark = ""
    if sp.get("line"):
        dot = (f'<circle cx="{sp["last"]["cx"]}" cy="{sp["last"]["cy"]}" r="2.5" fill="#8000FF"/>'
               if sp.get("last") else "")
        spark = (f'<svg width="{sp["w"]}" height="{sp["h"]}" viewBox="0 0 {sp["w"]} {sp["h"]}">'
                 f'<path d="{sp["line"]}" fill="none" stroke="#8000FF" stroke-width="1.6"/>{dot}</svg>')
    return f"""
    <a class="card card-live" href="{m['report_path']}">
      <div style="display:flex;align-items:baseline;justify-content:space-between;gap:10px">
        <div><span style="font-size:20px">{m['flag']}</span>
          <span style="font:800 17px 'Figtree';margin-left:6px">{m['name']}</span></div>
        <span class="chip">{t['week_type']}</span>
      </div>
      <div style="color:#8A82A0;font:600 11px 'Hanken Grotesk';letter-spacing:.04em;text-transform:uppercase;margin-top:2px">{m['region']}</div>
      <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:12px;margin-top:14px">
        <div>
          <div style="font:800 26px 'Figtree'">{_fmt_money(t['rev'])}</div>
          <div style="font:700 13px 'Hanken Grotesk';color:{col}">{arrow} {_fmt_pct(t['wow_pct'])} WoW
            <span style="color:#6E6680;font-weight:600"> · {_fmt_pct(t['yoy_pct'],0)} YoY</span></div>
        </div>
        <div style="text-align:right">{spark}</div>
      </div>
      <div style="display:flex;gap:16px;margin-top:12px;padding-top:11px;border-top:1px solid #EEE9F8;
        font:600 12px 'Hanken Grotesk';color:#6E6680">
        <span>ROI <b style="color:#1C1726">{t['roi_pct']:.0f}%</b></span>
        <span style="color:#E5384F">▼ {t['n_drops']} drops</span>
        <span style="color:#12A150">▲ {t['n_gains']} gains</span>
        <span style="margin-left:auto;color:#8000FF;font-weight:700">Open report →</span>
      </div>
    </a>"""


def render_index(state: dict, week: str) -> str:
    cards = "\n".join(_card(m) for m in state["markets"] if m.get("live"))
    n = len([m for m in state["markets"] if m.get("live")])
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Weekly Ledger · Market Weekly</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800;900&family=Hanken+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *{{box-sizing:border-box}} body{{margin:0;font-family:'Hanken Grotesk',system-ui,sans-serif;background:#F3F0F9;color:#1C1726;-webkit-font-smoothing:antialiased}}
  a{{color:inherit;text-decoration:none}}
  .wrap{{max-width:1320px;margin:0 auto;padding:0 40px}}
  .toggle a{{font:700 13px 'Hanken Grotesk';padding:6px 15px;border-radius:999px;color:#6E6680}}
  .toggle a.on{{background:#8000FF;color:#fff}}
  .mktgrid{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin-top:26px}}
  .card{{background:#fff;border:1px solid #EBE5F6;border-radius:18px;padding:18px 20px;box-shadow:0 2px 12px rgba(88,0,170,.05)}}
  .card-live{{transition:transform .18s,box-shadow .18s;display:block}}
  .card-live:hover{{transform:translateY(-3px);box-shadow:0 18px 40px rgba(128,0,255,0.16)}}
  .chip{{font:700 10px 'Hanken Grotesk';letter-spacing:.04em;text-transform:uppercase;background:#F1E8FF;color:#8000FF;padding:3px 9px;border-radius:99px;white-space:nowrap}}
  @media (max-width:960px){{.mktgrid{{grid-template-columns:repeat(2,1fr)}}}}
  @media (max-width:640px){{.wrap{{padding:0 20px}}.mktgrid{{grid-template-columns:1fr}}}}
</style></head><body>

<div style="position:sticky;top:0;z-index:40;backdrop-filter:blur(12px);background:rgba(243,240,249,0.84);border-bottom:1px solid #E7E1F1">
  <div class="wrap" style="padding:13px 40px;display:flex;align-items:center;justify-content:space-between;gap:18px">
    <div style="display:flex;align-items:center;gap:11px">
      <span style="flex:none;width:26px;height:26px;border-radius:50% 50% 50% 4px;background:#8000FF"></span>
      <span style="font:800 16px 'Figtree'">Market Weekly</span>
      <span style="color:#6E6680;font-size:13px">· The Ledger</span>
    </div>
    <div class="toggle" style="display:flex;gap:4px;background:#fff;border:1px solid #E7E1F1;border-radius:999px;padding:3px">
      <a href="/">Monthly</a><a class="on" href="/weekly">Weekly</a>
    </div>
  </div>
</div>

<div class="wrap" style="padding:36px 40px 100px">
  <div style="font:700 12px 'Hanken Grotesk';letter-spacing:.2em;text-transform:uppercase;color:#8000FF">Market Weekly Review · Growth Intelligence</div>
  <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:flex-end;gap:20px;margin-top:12px">
    <h1 style="font:800 54px/1 'Figtree';letter-spacing:-.03em;margin:0">The Weekly <span style="font-style:italic;font-weight:900;color:#8000FF">Ledger</span></h1>
    <div style="text-align:right;font:600 12px 'Hanken Grotesk';letter-spacing:.08em;text-transform:uppercase;color:#9A92AC;line-height:1.7">
      <div style="color:#6E6680">Week of {week}</div>
      <div>{n} market{'s' if n != 1 else ''} live</div>
    </div>
  </div>
  <div class="mktgrid">
    {cards}
  </div>
</div>
</body></html>"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("market", help="market slug or 'all'")
    ap.add_argument("--week", required=True, help="W0 Monday YYYY-MM-DD")
    ap.add_argument("--spotlight", default=None)
    args = ap.parse_args(argv)

    deploy = notebook_dir()
    if not deploy.exists():
        sys.exit(f"notebook dir not found: {deploy} (set MMR_NOTEBOOK_DIR)")

    targets = list(config.MARKETS) if args.market == "all" else [args.market]
    print(f"Weekly Ledger publish · week {args.week} · markets: {targets}")
    print(f"  deploy dir: {deploy}")

    state = load_state(deploy)
    state["edition"] = {"week": args.week}
    n = 0
    for slug in targets:
        entry = publish_market(slug, args.week, deploy, args.spotlight)
        if entry:
            upsert(state, entry)
            n += 1
    if not n:
        sys.exit("nothing published — generate reports first with weekly_market_report.py")

    save_state(deploy, state)
    (deploy / "weekly.html").write_text(render_index(state, args.week))
    print(f"\n  wrote {deploy/'weekly.html'} + weekly_state.json ({n} market(s))")
    print("\nNext:")
    print(f"  open {deploy/'weekly.html'}                         # local preview")
    print("  vercel deploy --prod --cwd market-notebook-v2       # from ~/analytics — USER runs")


if __name__ == "__main__":
    main()
