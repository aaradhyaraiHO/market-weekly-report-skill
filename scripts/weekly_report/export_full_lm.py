#!/usr/bin/env python3
"""Export the COMPLETE ungated Losing Money view to the Weekly Flagged spreadsheet.

The report applies a $1k/4wk materiality gate (buckets.LM_SPEND_GATE); this export runs
the SAME engine with spend_gate=0 so perf's verification ("every losing CE is listed
somewhere") always passes against the sheet. One tab per week, perf's column layout
(weekly blocks W0..W3) + v3 fields (criteria, streak, tROAS, launch, driver).

Usage:
    python3 scripts/weekly_report/export_full_lm.py --week 2026-08-02
    # snapshots must already exist in .cache/weekly_report/ (run after the Monday build)

GUARD: writes a shared Google Sheet — run from the MAIN checkout's publish flow only
(publish-only-from-main rule), never from a worktree build.
"""
import argparse, glob, json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import buckets  # noqa: E402

SHEET_ID = os.environ.get("WR_LM_EXPORT_SHEET_ID", "1sXd0m2d2Qc5rg99ctpp_hnN5Jg8mtsRAwds_i2ZuwLo")
CRIT_LBL = {"C1": "0conv", "C2": "WoW", "C3": "3wk", "C4": "90d", "C5": "W0 loss"}


def gws(*args, body=None):
    cmd = ["gws"] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True)
    out = r.stdout
    try:
        return json.loads(out[out.index("{"):])
    except Exception:
        return {"_raw": out, "_err": r.stderr}


def build_rows(week: str, cache_dir: str = ".cache/weekly_report"):
    hdr = (["Market", "CID", "CE Name", "Table", "Label", "Criteria", "Streak wks", "Sort Δ",
            "WoW Δ", "vs3wk Δ", "90d CM2", "In report (gated)"]
           + [f"{w} {m}" for w in ("W0", "W1", "W2", "W3")
              for m in ("Cost", "Clicks", "CPC", "Conv", "CVR", "CM1", "ROI", "CM2", "tROAS")]
           + ["tROAS L4W", "tROAS now", "Launched", "Days since launch", "Tier", "Driver", "Driver $"])
    rows = [hdr]
    for path in sorted(glob.glob(f"{cache_dir}/snapshot_*_{week}.json")):
        slug = path.split("snapshot_")[1].rsplit("_", 1)[0]
        if slug == "headout":
            continue
        snap = json.load(open(path))
        prior_pp = buckets._prior_proplus_map(snap)
        troas = buckets._troas_now_map(snap)
        launch = buckets._launch_map(snap)
        full = buckets.losing_money(snap["ces"], troas, launch, prior_pp, spend_gate=0)
        gated = buckets.losing_money(snap["ces"], troas, launch, prior_pp)  # report view
        in_report = {str(r["ce_id"]) for r in gated["existing"] + gated["new"]}
        for r in full["existing"] + full["new"]:
            wkb = {w["label"]: w for w in (r.get("weeks") or [])}
            cells = [slug, str(r["ce_id"]), r["ce_name"], r["new_existing"], r["label"],
                     "+".join(CRIT_LBL.get(c, c) for c in r["criteria"]),
                     r.get("flag_streak"), r.get("sort_delta"),
                     r.get("delta_wow"), r.get("delta_3w"), r.get("cm2_90d"),
                     ("Yes" if str(r["ce_id"]) in in_report else "No — sub-$1k gate")]
            for lbl in ("w0", "w1", "w2", "w3"):
                w = wkb.get(lbl) or {}
                conv = (round(w["clicks"] * w["cvr"] / 100)
                        if (w.get("clicks") and w.get("cvr") is not None) else None)
                cells += [w.get("spend"), w.get("clicks"), w.get("cpc"), conv, w.get("cvr"),
                          w.get("cm1"), w.get("roi"), w.get("cm2"), w.get("troas")]
            cells += [r.get("troas_l4w"), r.get("troas_now"), r.get("launch_date"),
                      r.get("days_since_launch"), r.get("tier"), r.get("driver"),
                      (r.get("drivers") or {}).get(r.get("driver"))]
            rows.append(["" if c is None else c for c in cells])
        print(f"  {slug}: {len(full['existing']) + len(full['new'])} rows "
              f"({len(gated['existing']) + len(gated['new'])} in gated report)")
    return rows


def write_tab(week: str, rows):
    tab = f"LM full (no gate) w-c {week}"
    meta = gws("sheets", "spreadsheets", "get", "--params",
               json.dumps({"spreadsheetId": SHEET_ID, "fields": "sheets.properties(sheetId,title)"}))
    old = [s["properties"]["sheetId"] for s in meta.get("sheets", []) if s["properties"]["title"] == tab]
    reqs = ([{"deleteSheet": {"sheetId": old[0]}}] if old else []) + \
           [{"addSheet": {"properties": {"title": tab, "gridProperties":
              {"rowCount": len(rows) + 10, "columnCount": len(rows[0]) + 2,
               "frozenRowCount": 1, "frozenColumnCount": 3}}}}]
    gws("sheets", "spreadsheets", "batchUpdate", "--params", json.dumps({"spreadsheetId": SHEET_ID}),
        "--json", json.dumps({"requests": reqs}))
    res = gws("sheets", "spreadsheets", "values", "update", "--params",
              json.dumps({"spreadsheetId": SHEET_ID, "range": f"'{tab}'!A1", "valueInputOption": "RAW"}),
              "--json", json.dumps({"values": rows}))
    print(f"wrote '{tab}': {res.get('updatedCells')} cells")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", required=True, help="W0 week start (Sunday) YYYY-MM-DD")
    ap.add_argument("--cache", default=".cache/weekly_report")
    args = ap.parse_args()
    write_tab(args.week, build_rows(args.week, args.cache))
