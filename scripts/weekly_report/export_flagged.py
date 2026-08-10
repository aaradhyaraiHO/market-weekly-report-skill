#!/usr/bin/env python3
"""
Export bucket-flagged CEs across markets to TWO faithful datasets, each with the
bucket's NATIVE columns (matching the report tables 1:1):

  * Losing Money  — bleeders + eroding + full_waste + paused + tracking_gap
  * Fluctuations  — CM1/RPC Fluctuations ↓ (seasonality_down) + ↑ (seasonality_up)

Writes two CSVs next to the repo root. Use push_flagged_sheet.sh to load them
into the two tabs of the Google Sheet.

Usage: python3 export_flagged.py [--week YYYY-MM-DD]
"""
from __future__ import annotations
import argparse, csv, glob, json
from pathlib import Path
from collections import Counter

import config

HERE = Path(__file__).resolve().parent
CACHE = HERE.parents[1] / ".cache" / "weekly_report"
ROOT = HERE.parents[1]

# ── Losing Money: native columns mirror lmHead/lmRow in the report ──
# (out_col, snapshot_field)
LM_COLS = [
    ("ce_id", "ce_id"), ("ce_name", "ce_name"),
    ("new_existing", "new_existing"), ("tier", "tier"),
    ("status", "status"),
    ("roi", "roi"), ("roi_wow_dpp", "roi_dpp"), ("roi_d4w", "roi_v4"),
    ("cm2_lost_wk", "lost_wk"), ("cm2_bleed_wk", "cm2_bleed_wk"), ("cm2_bleed_4w", "cm2_bleed_4w"),
    ("spend_wk", "spend_wk"), ("spend_d4w_pct", "spend_dvs4"), ("spend_wow_pct", "spend_wow"),
    ("rpc_g", "rpc_g"), ("rpc_g_d4w_pct", "rpc_g_v4"),
    ("cvr_g", "cvr_g"), ("cvr_g_d4w_pct", "cvr_g_v4"),
    ("cpc", "cpc"), ("cpc_d4w_pct", "cpc_v4"),
    ("clicks_g", "clicks_g"), ("clicks_g_d4w_pct", "clicks_g_v4"),
    ("tr_g", "tr_g"), ("tr_g_d4w_pp", "tr_g_v4"),
    ("dominant_driver", "dominant_driver"),
    ("spend_4w", "spend_4w"), ("orders_4w", "orders_4w"),
]
# losing_money sub-lists → status_bucket label + whether the report shows it as a row
LM_SUBS = [
    ("bleeders",     "Bleeding",     "row"),
    ("eroding",      "Eroding",      "row"),
    ("full_waste",   "Full waste",   "row"),
    ("paused",       "Paused",       "footnote"),
    ("tracking_gap", "Tracking gap", "footnote"),
]

# ── Fluctuations: native columns mirror the report's fluctuation table ──
FX_COLS = [
    ("ce_id", "ce_id"), ("ce_name", "ce_name"),
    ("alert_type", "alert_type"), ("swing_pct", "swing_pct"),
    ("roi_4w", "roi_4w"), ("roi_4w_d", "roi_4w_d"),
    ("spend_4w", "spend_4w"), ("spend_4w_d", "spend_4w_d"),
    ("cvr", "cvr"), ("cvr_d", "cvr_d"),
    ("aov", "aov"), ("aov_d", "aov_d"),
    ("cr", "cr"), ("cr_d", "cr_d"),
    ("tr", "tr"), ("tr_d", "tr_d"),
    ("clicks", "clicks"), ("clicks_d", "clicks_d"),
    ("dominant", "dominant"), ("dominant_key", "dominant_key"),
    ("verdict", "verdict"), ("cause", "cause"),
    ("paid_pct", "paid_pct"), ("recommendation", "recommendation"),
]


def _v(x):
    return "" if x is None else x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", default=config.iso(config.latest_complete_week()))
    args = ap.parse_args()
    week = args.week

    snaps = sorted(glob.glob(str(CACHE / f"snapshot_*_{week}.json")))
    if not snaps:
        raise SystemExit(f"No snapshots for {week} under {CACHE}")

    lm_rows, fx_rows = [], []
    for p in snaps:
        snap = json.load(open(p))
        meta = snap.get("meta", {})
        market, slug = meta.get("market", "?"), meta.get("market_slug", "?")
        if slug == "headout":
            continue
        bf = snap.get("buckets_final", {})
        lm = (bf.get("defend", {}) or {}).get("losing_money", {}) or {}
        seas_dn = (bf.get("defend", {}) or {}).get("seasonality_down", []) or []
        seas_up = (bf.get("compound", {}) or {}).get("seasonality_up", []) or []

        for key, label, shown in LM_SUBS:
            for ce in lm.get(key, []) or []:
                row = {"market": market, "status_bucket": label, "shown_in_report": shown}
                for out, fld in LM_COLS:
                    row[out] = _v(ce.get(fld))
                lm_rows.append(row)

        for direction, lst in (("down", seas_dn), ("up", seas_up)):
            for ce in lst:
                row = {"market": market, "direction": direction}
                for out, fld in FX_COLS:
                    row[out] = _v(ce.get(fld))
                fx_rows.append(row)

    lm_header = ["market", "status_bucket", "shown_in_report"] + [c for c, _ in LM_COLS]
    fx_header = ["market", "direction"] + [c for c, _ in FX_COLS]

    lm_path = ROOT / f"flagged_losing_money_{week}.csv"
    fx_path = ROOT / f"flagged_fluctuations_{week}.csv"
    for path, header, rows in [(lm_path, lm_header, lm_rows), (fx_path, fx_header, fx_rows)]:
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader(); w.writerows(rows)

    print(f"week {week} · {len(snaps)} snapshots")
    print(f"  Losing Money : {len(lm_rows):3d} rows -> {lm_path.name}")
    for k, v in Counter(r["status_bucket"] for r in lm_rows).most_common():
        print(f"      {v:3d}  {k}")
    print(f"  Fluctuations : {len(fx_rows):3d} rows -> {fx_path.name}")
    for k, v in Counter(r["direction"] for r in fx_rows).most_common():
        print(f"      {v:3d}  {k}")


if __name__ == "__main__":
    main()
