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

# header priorities (case-insensitive, first present wins)
DECISION = ["final action", "actions took", "action taken"]   # the decision of record
REASON = ["perf action", "perf comments", "perf comment", "comment"]  # the reasoning/tag


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
    for i in range(n_weeks):
        wk = (w0 - dt.timedelta(days=7 * i)).isoformat()
        vals = _gws_get(f"'w/c {wk}'!A1:BA400")
        if not vals or len(vals) < 2:
            continue
        hdr = vals[0]
        ci = _find(hdr, ["cid"]) or 0
        di, ri = _find(hdr, DECISION), _find(hdr, REASON)
        for row in vals[1:]:
            def cell(idx):
                return (str(row[idx]).strip() if idx is not None and idx < len(row) else "")
            cid = cell(ci)
            if not cid:
                continue
            action, comment = cell(di), cell(ri)
            if comment == action:
                comment = ""
            # drop stray header-word junk that leaked into cells
            if action.lower() in ("perf action", "final action", "actions took"):
                action = ""
            if not (action or comment):
                continue
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
