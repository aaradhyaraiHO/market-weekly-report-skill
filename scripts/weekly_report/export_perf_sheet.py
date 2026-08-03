#!/usr/bin/env python3
"""Task 2 — Weekly Flagged export → perf's spreadsheet (1sXd0m…), NEW TAB per week.

Emits one row per flagged Losing-Money CE (existing + new). Approved clean layout (2026-08-03):

  CID · CID Name · Category · Market                                        (identity)
  W0 block (Cost·Clicks·CPC·Conv·CVR·CM1·ROI·CM2) · W-1 · W-2 · W-3         (4 weekly blocks)
  New/Exist · Tier · CM2 -ve 2wk · ROI Change(W0/W-1−1) · Clicks Change     (flags)
  GM action · GM comment                          (export owns — from the report store)
  Perf action · Perf comment · Final action       (PERF fills in the sheet — export never writes)

Metric representation matches the live sheet: CVR & ROI as FRACTIONS (0–1), Cost/CPC/CM1/CM2
in $, Clicks/Conversion as counts. Weekly metrics come from the snapshot losing_money rows'
`weeks` blocks (Conversion derived = CVR × Clicks; the store doesn't carry a raw count).

Dry-run prints the rows. The live-sheet WRITE is a separate, main-only step (not wired here) —
GUARD: never write the shared sheet from a worktree build.

Usage:
    python3 export_perf_sheet.py --snapshot <snapshot.json> --dry-run     # single (fixture) file
    python3 export_perf_sheet.py --week YYYY-MM-DD --dry-run               # all markets in .cache
"""
from __future__ import annotations
import argparse, glob, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config  # noqa: E402
CACHE = Path(config.__file__).resolve().parents[2] / ".cache" / "weekly_report"
PERF_SHEET_ID = "1sXd0m2d2Qc5rg99ctpp_hnN5Jg8mtsRAwds_i2ZuwLo"   # perf's Weekly Flagged spreadsheet


def _colname(i):
    s = ""; i += 1
    while i > 0:
        i, r = divmod(i - 1, 26); s = chr(65 + r) + s
    return s

# Column order = the live `Final Loosing money` header (A → AU).
WEEK_METRICS = ["Cost", "Clicks", "CPC", "Conversion", "CVR", "CM1", "ROI", "CM2"]
HEADER = (["CID", "CID Name", "Category", "Market"]
          + [f"W{w} {m}" for w in range(4) for m in WEEK_METRICS]      # 4 weekly blocks W0..W3
          + ["New/Exist", "Tier", "CM2 -ve 2wk", "ROI Change", "Clicks Change",
             "GM action", "GM comment",                                # export owns (from store)
             "Perf action", "Perf comment", "Final action"])           # PERF fills — export never writes

GM_ACT_LBL = {"negative_seasonality": "Negative seasonality", "roas_change": "ROAS target change",
              "scale_down": "Scale down", "pause": "Pause", "pause_review": "Pause & review",
              "no_change": "No change", "skip": "Skip"}


def _week_cells(w: dict | None) -> list:
    """The 8 sheet metrics for one week block, matching the live sheet's units."""
    if not w:
        return [""] * 8
    spend = w.get("spend"); clicks = w.get("clicks"); cpc = w.get("cpc")
    cvr_pct = w.get("cvr"); cm1 = w.get("cm1"); roi_pct = w.get("roi"); cm2 = w.get("cm2")
    conv = round(cvr_pct / 100.0 * clicks) if (cvr_pct is not None and clicks) else ""   # CVR = 100·conv/clk
    return [spend if spend is not None else "",
            clicks if clicks is not None else "",
            cpc if cpc is not None else "",
            conv,
            round(cvr_pct / 100.0, 4) if cvr_pct is not None else "",      # fraction (0–1)
            cm1 if cm1 is not None else "",
            round(roi_pct / 100.0, 4) if roi_pct is not None else "",      # fraction
            cm2 if cm2 is not None else ""]


def rows_for_snapshot(snap: dict, gm_actions: dict[str, dict]) -> list[list]:
    meta = snap.get("meta", {})
    market = meta.get("market", "")
    lm = (((snap.get("buckets_final") or {}).get("defend") or {}).get("losing_money") or {})
    flagged = (lm.get("existing") or []) + (lm.get("new") or [])
    # category lookup from the CE list (losing_money rows don't carry it)
    cat = {}
    for c in snap.get("ces", []) or []:
        cat[str(c.get("ce_id"))] = ((c.get("metadata") or {}).get("category") or "")
    out = []
    for r in flagged:
        cid = str(r.get("ce_id"))
        wk = r.get("weeks") or []
        w = {i: (wk[i] if i < len(wk) else None) for i in range(4)}
        blocks = []
        for i in range(4):
            blocks += _week_cells(w[i])
        cm2_0 = (w[0] or {}).get("cm2"); cm2_1 = (w[1] or {}).get("cm2")
        roi0 = (w[0] or {}).get("roi"); roi1 = (w[1] or {}).get("roi")
        clk0 = (w[0] or {}).get("clicks"); clk1 = (w[1] or {}).get("clicks")
        neg2 = "True" if (cm2_0 is not None and cm2_1 is not None and cm2_0 < 0 and cm2_1 < 0) else "False"
        roi_chg = round(roi0 / roi1 - 1, 4) if (roi0 and roi1) else ""
        clk_chg = round(clk0 / clk1 - 1, 4) if (clk0 and clk1) else ""
        gm = gm_actions.get(cid, {})
        gm_act = GM_ACT_LBL.get(gm.get("status", ""), gm.get("status", ""))
        out.append([cid, r.get("ce_name", ""), cat.get(cid, ""), market]
                   + blocks
                   + [r.get("new_existing", ""), r.get("tier", ""), neg2, roi_chg, clk_chg,
                      gm_act, gm.get("note", ""),
                      "", "", ""])             # Perf action / comment / final — perf fills in the sheet
    return out


def _fetch_gm_actions(market_slug: str, week: str, attempts: int = 4) -> dict[str, dict]:
    """GM action layer (bucket=losing_money) for the market-week, from the store.

    RETRIES on transient failure: the Apps Script endpoint throttles under the rapid
    13-market batch, and the old silent `except: return {}` turned a throttle timeout
    into blank GM columns — i.e. it CLOBBERED real GM comments in the sheet (seen
    2026-08-03: Italy's Colosseum/Ferrari comments dropped on a publish-all). On total
    failure we RAISE, never return {} — callers must skip the write rather than blank
    the columns. A genuinely comment-less market returns {} normally (no exception)."""
    import time, urllib.parse, urllib.request
    base = os.environ.get("WR_NOTES_SCRIPT_URL") or config.NOTES_SCRIPT_URL
    if not base:
        return {}
    q = urllib.parse.urlencode({"action": "action_list", "market": market_slug, "week": week})
    last = None
    for i in range(attempts):
        try:
            with urllib.request.urlopen(base + "?" + q, timeout=25) as r:
                data = json.loads(r.read().decode())
            return {str(a["ce_id"]): a for a in data.get("actions", [])
                    if a.get("bucket") == "losing_money" and a.get("ce_id")}
        except Exception as e:
            last = e
            if i < attempts - 1:
                time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GM action fetch failed for {market_slug} {week} after {attempts} tries: {last}")


def _gws(sub, params, body=None):
    """Run a gws sheets call. Returns (ok, text)."""
    cmd = ["gws", "sheets"] + sub + ["--params", json.dumps(params), "--format", "json"]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode == 0, (r.stdout or r.stderr).strip()


def _on_main():
    r = subprocess.run(["git", "-C", str(HERE), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() == "main"


def write_weekly_tab(rows, week, spreadsheet_id=PERF_SHEET_ID):
    """Create/populate the `w/c <week>` tab: the FULL header row (incl. the 3 perf column titles)
    + one data row per flagged CE, all markets. Data rows are written only through the GM columns
    (the last 3 = Perf action/comment/final) so a re-run NEVER clobbers perf's edits. Header row
    carries no perf values, so writing it in full is safe on refresh too."""
    tab = f"w/c {week}"
    last = _colname(len(HEADER) - 1)
    keep = len(HEADER) - 3                        # data rows stop before the 3 perf columns
    dcol = _colname(keep - 1)
    # 1. ensure the tab exists (addSheet; a duplicate-title error just means it's already there)
    _gws(["spreadsheets", "batchUpdate"], {"spreadsheetId": spreadsheet_id},
         {"requests": [{"addSheet": {"properties": {"title": tab}}}]})
    # 2. full header row (A1:{last}1) — all 46 columns incl. the perf titles
    _gws(["spreadsheets", "values", "update"],
         {"spreadsheetId": spreadsheet_id, "range": f"'{tab}'!A1:{last}1", "valueInputOption": "USER_ENTERED"},
         {"values": [HEADER]})
    # 3. data rows through the GM columns only (A2:{dcol}{n+1}) — perf columns untouched
    data = [r[:keep] for r in rows]
    ok, txt = _gws(["spreadsheets", "values", "update"],
                   {"spreadsheetId": spreadsheet_id,
                    "range": f"'{tab}'!A2:{dcol}{len(data) + 1}", "valueInputOption": "USER_ENTERED"},
                   {"values": data})
    return ok, tab, txt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", help="single snapshot json (fixture/dry-run)")
    ap.add_argument("--week", default=config.iso(config.latest_complete_week()))
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--write", dest="dry_run", action="store_false",
                    help="write the weekly tab to the perf sheet (MAIN checkout only)")
    args = ap.parse_args()

    paths = [args.snapshot] if args.snapshot else sorted(glob.glob(str(CACHE / f"snapshot_*_{args.week}.json")))
    if not paths:
        raise SystemExit("no snapshot(s) found")

    all_rows = []
    for p in paths:
        snap = json.load(open(p))
        meta = snap.get("meta", {})
        if meta.get("market_slug") == "headout":
            continue
        gm = _fetch_gm_actions(meta.get("market_slug", ""), args.week)
        all_rows += rows_for_snapshot(snap, gm)

    if args.dry_run:
        print(f"{len(all_rows)} flagged rows · {len(HEADER)} columns (A..{_colname(len(HEADER)-1)})\n")
        print(" | ".join(f"{_colname(i)}:{h}" for i, h in enumerate(HEADER)))
        print("-" * 100)
        for row in all_rows:
            show = row[:12] + ["…"] + row[36:]     # identity + W0 block + tail (skip W1..W3 for width)
            print(" | ".join(str(x) for x in show))
        return
    # live write — publish-only-from-main (writing the shared perf sheet)
    if not _on_main() and os.environ.get("WR_ALLOW_WORKTREE_WRITE") != "1":
        sys.exit("REFUSING to write the perf sheet from a non-main checkout (publish-only-from-main). "
                 "Run from main, or set WR_ALLOW_WORKTREE_WRITE=1 for a test.")
    ok, tab, txt = write_weekly_tab(all_rows, args.week)
    print(f"{'✓' if ok else '✗'} wrote {len(all_rows)} rows → tab '{tab}'" + ("" if ok else f"\n{txt}"))


if __name__ == "__main__":
    main()
