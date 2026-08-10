#!/usr/bin/env python3
"""Perf action-history sidecar — per-CE timeline of PERF's final actions from the
Weekly Flagged sheet, for the CE-drawer Action log.

Perf records the FINAL action per CE directly in the perf sheet (1sXd…), one
`w/c <week>` tab per week. Those are the decisions of record — the Action log shows
THESE (not GM bucket-actions). The sheet's perf columns drifted across tabs
(07-20: 'Actions Took' / 'Perf Comments'; 07-26: 'Perf action' / 'Perf comment' /
'Final action', + duplicate junk cols), so we locate them BY HEADER NAME, per tab,
first-match wins (real cols beat duplicates).

Writes `.cache/weekly_report/perf_hist_<week>.json` = {cid: [{week, action, comment}]}
newest-first, spanning the report week + the prior N weeks that have a tab. Keyed by CID
(the perf sheet is one tab across ALL markets), so render attaches it per-CE by ce_id.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config  # noqa: E402

PERF_SHEET_ID = "1sXd0m2d2Qc5rg99ctpp_hnN5Jg8mtsRAwds_i2ZuwLo"
OUT = Path(config.__file__).resolve().parents[2] / ".cache" / "weekly_report"

# header priorities (case-insensitive). Roles differ per tab: on the 07-26 export tab the
# decision/tag is "Perf comment" (singular) and the reasoning is "Perf action"; on the 07-20 perf
# tab the decision is "Actions Took" and the reasoning is "Perf Comments" (plural). We scan each
# list for the first NON-EMPTY cell (a header can be present but blank on a given row).
DECISION = ["final action", "actions took", "action taken", "perf comment"]  # decision / short tag
REASON = ["perf action", "perf comments"]                                    # the reasoning / note


def _gws_get(rng: str):
    cmd = ["gws", "sheets", "spreadsheets", "values", "get",
           "--params", json.dumps({"spreadsheetId": PERF_SHEET_ID, "range": rng}),
           "--format", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    t = (r.stdout or "").strip()
    try:
        return json.loads(t[t.index("{"):]).get("values", [])
    except Exception:
        return None


def _find(hdr, names):
    low = [str(h).strip().lower() for h in hdr]
    for n in names:
        if n in low:
            return low.index(n)
    return None


def _header_row(vals):
    """Header row isn't always row 0 — some tabs carry a 'Date Week' title row above it
    (e.g. w/c 2026-07-20 puts headers on row 2). Find the first row that contains 'CID'."""
    for i, row in enumerate(vals[:6]):
        if any(str(c).strip().lower() == "cid" for c in row):
            return i
    return 0


def _list_week_tabs():
    """The perf sheet's `w/c <date>` tabs, parsed + sorted newest-first. Tab dates mix
    conventions (07-20 is a Monday, 07-26/08-02 are Sundays), so we ENUMERATE actual tabs
    rather than guess names off a fixed 7-day stride."""
    cmd = ["gws", "sheets", "spreadsheets", "get",
           "--params", json.dumps({"spreadsheetId": PERF_SHEET_ID,
                                    "fields": "sheets(properties(title))"}),
           "--format", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return []
    t = (r.stdout or "").strip()
    try:
        sheets = json.loads(t[t.index("{"):]).get("sheets", [])
    except Exception:
        return []
    out = []
    for s in sheets:
        title = s.get("properties", {}).get("title", "")
        if title.startswith("w/c "):
            try:
                out.append((dt.date.fromisoformat(title[4:].strip()), title))
            except Exception:
                continue
    out.sort(reverse=True)
    return out


def build_sidecar(week: str, n_weeks: int = 6, skip_if_fresh: bool = False) -> dict:
    """Return {cid: [{week, action, comment}]} newest-first and write the sidecar.
    skip_if_fresh: if the sidecar exists and was written today, reuse it (so a 17-market
    run only reads the perf sheet once)."""
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"perf_hist_{week}.json"
    if skip_if_fresh and dest.exists():
        try:
            if dt.date.fromtimestamp(dest.stat().st_mtime) == dt.date.today():
                return json.loads(dest.read_text())
        except Exception:
            pass

    w0 = dt.date.fromisoformat(week)
    hist: dict[str, list] = {}
    tabs = [(d, t) for d, t in _list_week_tabs() if d <= w0][:n_weeks]
    for d, title in tabs:
        wk = d.isoformat()
        vals = _gws_get(f"'{title}'!A1:BA400")
        if not vals or len(vals) < 2:
            continue
        hr = _header_row(vals)
        hdr = vals[hr]
        ci = _find(hdr, ["cid"]) or 0
        low = [str(h).strip().lower() for h in hdr]
        di_cols = [low.index(n) for n in DECISION if n in low]   # priority-ordered
        ri_cols = [low.index(n) for n in REASON if n in low]
        # A CID can appear on MULTIPLE rows in one tab (per-campaign variants) — collapse to ONE
        # entry per CID per week, preferring the row that carries an actual decision (action).
        by_cid: dict[str, tuple] = {}
        for row in vals[hr + 1:]:
            def cell(idx):
                return (str(row[idx]).strip() if idx is not None and idx < len(row) else "")
            cid = cell(ci)
            if not cid:
                continue
            # first NON-EMPTY cell in each list (a header can be present but blank on a row)
            action = next((v for v in (cell(i) for i in di_cols) if v), "")
            comment = next((v for v in (cell(i) for i in ri_cols) if v), "")
            # drop stray header-word junk that leaked into cells
            if action.lower() in ("perf action", "final action", "actions took", "perf comment"):
                action = ""
            if comment == action:
                comment = ""
            if not (action or comment):
                continue
            prev = by_cid.get(cid)
            if prev is None or (action and not prev[0]):   # prefer a row with a decision
                by_cid[cid] = (action, comment)
        for cid, (action, comment) in by_cid.items():
            hist.setdefault(cid, []).append({"week": wk, "action": action, "comment": comment})

    for c in hist:
        hist[c].sort(key=lambda e: e["week"], reverse=True)
    dest.write_text(json.dumps(hist))
    return hist


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default=config.iso(config.latest_complete_week()))
    args = ap.parse_args()
    h = build_sidecar(args.week)
    aw = sum(len(v) for v in h.values())
    print(f"perf_hist_{args.week}.json: {len(h)} CIDs · {aw} action-weeks "
          f"· CIDs w/ >=2 wks: {sum(1 for v in h.values() if len(v) >= 2)}")


if __name__ == "__main__":
    main()
