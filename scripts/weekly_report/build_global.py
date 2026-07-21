#!/usr/bin/env python3
"""build_global — Headout-level (all-market aggregate) weekly snapshot.

MERGE, not re-query: loads the per-market snapshots already in .cache for a week
and rolls them into one "Headout" snapshot with the SAME contract, so render.py +
the template work unchanged. No new BigQuery.

Aggregation:
  • ces            — union of all markets' CEs (a CE belongs to one market)
  • market_summary — weekly/weekly_ly summed per week (additive fields), derived
                     metrics recomputed from the sums; ratio metrics that have no
                     clean sum (tr/cr/sis/ctr/contrib) are revenue-weighted
  • headlines      — key_metrics rebuilt from summed W0/W-1; movers + week_header
                     recomputed globally via flows (structural clock degrades to
                     raw WoW — LY-forward per CE isn't in the trailing snapshot)
  • buckets/PP/etc — pooled (concatenated), worst-first re-sorts preserved

Usage:
  python3 build_global.py --week 2026-07-13 [--out <path>]
  then: python3 render.py .cache/weekly_report/snapshot_headout_<week>.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import config          # noqa: E402
import flows           # noqa: E402

CACHE = HERE.parent.parent / ".cache" / "weekly_report"

# weekly fields that sum straight across markets
ADDITIVE = [
    "revenue", "gbv", "orders", "clicks", "cm2", "spend", "cm1",
    "cm1_business", "gross_marketing_cost", "paid_impressions", "paid_clicks",
    "paid_conv_value", "paid_conversions", "paid_revenue", "paid_cm2",
]
# TR% and CR% are exact: reconstruct gbv_completed = gbv × cr%/100 per market, then
# CR% = Σgbv_completed/Σgbv · TR% = Σrevenue/Σgbv_completed (canon).
# SIS% / paid_contribution% have no raw numerator/denominator in the weekly row → revenue-weighted.
WEIGHTED = ["paid_sis_pct", "paid_contribution_pct"]


def _load(week):
    out = {}
    for slug in config.MARKETS:
        p = CACHE / f"snapshot_{slug}_{week}.json"
        if not p.exists():
            print(f"  ! missing {p.name} — skipping {slug}")
            continue
        d = json.loads(p.read_text())
        out[slug] = d.get("markets", [d])[0]
    if not out:
        sys.exit(f"no snapshots found for week {week} in {CACHE}")
    return out


def _num(v):
    return round(v, 4) if isinstance(v, float) else v


def _merge_weekly(series_list):
    """Sum a list of market_weekly arrays by week; recompute derived metrics."""
    by_week = {}
    order = []
    for series in series_list:
        for w in series:
            wk = w["week"]
            if wk not in by_week:
                by_week[wk] = {"week": wk, "_rev_wt": 0.0, "_gbv_completed": 0.0,
                               "_wsum": {k: 0.0 for k in WEIGHTED}}
                order.append(wk)
            acc = by_week[wk]
            for f in ADDITIVE:
                v = w.get(f)
                if v is not None:
                    acc[f] = acc.get(f, 0.0) + v
            # reconstruct gbv_completed from gbv × cr% (market weekly carries both, not gbv_completed)
            gbv, cr = w.get("gbv"), w.get("cr_pct")
            if gbv is not None and cr is not None:
                acc["_gbv_completed"] += gbv * cr / 100.0
            rev = w.get("revenue") or 0.0
            acc["_rev_wt"] += rev
            for f in WEIGHTED:
                v = w.get(f)
                if v is not None:
                    acc["_wsum"][f] += v * rev
    rows = []
    for wk in sorted(order):
        a = by_week[wk]
        rev_wt = a.pop("_rev_wt") or 0.0
        gc = a.pop("_gbv_completed") or 0.0
        wsum = a.pop("_wsum")
        def r(x, y, scale=100.0):
            return _num(scale * a[x] / a[y]) if a.get(y) else None
        a["aov"] = _num(a["gbv"] / a["orders"]) if a.get("orders") else None
        # exact take-rate + completion from summed components
        a["cr_pct"] = _num(100.0 * gc / a["gbv"]) if a.get("gbv") else None
        a["tr_pct"] = _num(100.0 * a["revenue"] / gc) if gc else None
        a["roi_pct"] = r("cm1", "spend")
        a["roi1_pct"] = r("cm1_business", "gross_marketing_cost")
        a["cvr_pct"] = r("paid_conversions", "paid_clicks")
        a["paid_cvr_pct"] = a["cvr_pct"]
        a["cpc"] = _num(a["spend"] / a["paid_clicks"]) if a.get("paid_clicks") else None
        a["paid_rpc"] = _num(a["paid_revenue"] / a["paid_clicks"]) if a.get("paid_clicks") else None
        a["paid_ctr_pct"] = r("paid_clicks", "paid_impressions")
        a["avg_cm1"] = _num(a["cm1"] / a["paid_conversions"]) if a.get("paid_conversions") else None
        a["cm1_per_conv"] = a["avg_cm1"]
        for f in WEIGHTED:               # revenue-weighted average across markets
            a[f] = _num(wsum[f] / rev_wt) if rev_wt else None
        rows.append(a)
    return rows


def _pool(markets, path):
    """Concatenate a list-valued field across markets (path like 'buckets_final.defend.seasonality_down')."""
    out = []
    for m in markets.values():
        node = m
        for seg in path.split("."):
            node = (node or {}).get(seg) if isinstance(node, dict) else None
        if isinstance(node, list):
            out.extend(node)
    return out


def build_global(week: str) -> dict:
    markets = _load(week)
    slugs = list(markets.keys())
    print(f"  merging {len(slugs)} markets: {', '.join(slugs)}")

    # ---- ces: union ----
    ces = []
    for m in markets.values():
        ces.extend(m.get("ces") or [])

    # ---- market_summary: sum weekly + weekly_ly ----
    weekly = _merge_weekly([m["market_summary"]["weekly"] for m in markets.values()])
    weekly_ly = _merge_weekly([m["market_summary"].get("weekly_ly") or [] for m in markets.values()])
    ly_by_week = {w["week"]: w for w in weekly_ly}
    # per-week YoY on the summed series (weekday-aligned LY lives in weekly_ly by week key offset)
    for w in weekly:
        ly = ly_by_week.get(w["week"])
        w["yoy_pct"] = _num(100.0 * (w["revenue"] / ly["revenue"] - 1)) if (ly and ly.get("revenue")) else None

    w0 = config.iso(dt.date.fromisoformat(week))
    weeks_sorted = [w["week"] for w in weekly]
    w0_row = next(w for w in weekly if w["week"] == w0)
    wm1_iso = weeks_sorted[weeks_sorted.index(w0) - 1] if weeks_sorted.index(w0) > 0 else None
    wm1_row = next((w for w in weekly if w["week"] == wm1_iso), None)

    # ---- headlines: key_metrics from summed W0/W-1 ----
    KEY_METRIC_SPEC = [
        ("revenue", "Revenue", "revenue"), ("gbv", "GBV", "gbv"), ("orders", "Orders", "orders"),
        ("aov", "AOV", "aov"), ("cr_pct", "CR%", "cr_pct"), ("tr_pct", "TR%", "tr_pct"),
        ("paid_clicks", "Paid Clicks", "paid_clicks"), ("paid_cvr", "Paid CVR", "paid_cvr_pct"),
        ("paid_conv_value", "Paid Conv Value", "paid_conv_value"), ("avg_cm1", "Avg CM1", "avg_cm1"),
        ("paid_roi", "Paid RoI", "roi_pct"), ("roi1", "ROI 1", "roi1_pct"),
    ]
    key_metrics = {}
    for key, label, field in KEY_METRIC_SPEC:
        w0v, wm1v = w0_row.get(field), (wm1_row.get(field) if wm1_row else None)
        da = _num(w0v - wm1v) if (w0v is not None and wm1v is not None) else None
        dp = _num(100.0 * (w0v / wm1v - 1)) if (w0v is not None and wm1v not in (None, 0)) else None
        km = {"w0": w0v, "wm1": wm1v, "delta_abs": da, "delta_pct": dp,
              "label": label, "field": field, "has_ly": True, "ly_field": field}
        if key == "revenue":
            km["yoy_pct"] = w0_row.get("yoy_pct")
        key_metrics[key] = km

    week_header = flows.build_header(ces, {}, weekly, dt.date.fromisoformat(week), large_threshold=None)
    # Replace build_header's structural (which degrades to raw when LY-forward is absent) with an
    # AGGREGATE, portfolio-blended structural clock — one trailing LY WoW ratio ΣLY(W0)/ΣLY(W-1),
    # no per-CE forward week, no new query.
    _apply_aggregate_structural(week_header, ces, weekly_ly, w0, w0_row.get("revenue") or 0.0)
    headlines = {
        "revenue_w0": w0_row.get("revenue"),
        "wow_pct": key_metrics["revenue"]["delta_pct"],
        "yoy_pct": w0_row.get("yoy_pct"),
        "roi_w0_pct": w0_row.get("roi_pct"),
        "roi1_w0_pct": w0_row.get("roi1_pct"),
        "key_metrics": key_metrics,
        "top_gainers": week_header["trend"]["top_gainers"],
        "top_drops": week_header["trend"]["top_droppers"],
        "shapley_wow": {},          # market-level Shapley not aggregated (per-CE lives in drawers)
        "week_header": week_header,
    }

    # ---- pooled buckets / lists ----
    bf = {
        "defend": {
            "losing_money": {
                "bleeders": sorted(_pool(markets, "buckets_final.defend.losing_money.bleeders"),
                                   key=lambda r: (bool(r.get("recovering")), r.get("cm2_bleed_4w") or 0)),
                "full_waste": _pool(markets, "buckets_final.defend.losing_money.full_waste"),
                "recovered": _pool(markets, "buckets_final.defend.losing_money.recovered"),
                "paused": _pool(markets, "buckets_final.defend.losing_money.paused"),
                "tracking_gap": _pool(markets, "buckets_final.defend.losing_money.tracking_gap"),
                "burn_line": _sum_burn(markets),
            },
            "seasonality_down": sorted(_pool(markets, "buckets_final.defend.seasonality_down"),
                                       key=lambda r: (r.get("swing_pct") or 0)),
        },
        "compound": {
            "seasonality_up": sorted(_pool(markets, "buckets_final.compound.seasonality_up"),
                                     key=lambda r: -(r.get("swing_pct") or 0)),
            "scale_up": _pool(markets, "buckets_final.compound.scale_up"),
        },
        "lifecycle": {
            "new_ces": _pool(markets, "buckets_final.lifecycle.new_ces"),
            "iteration": _pool(markets, "buckets_final.lifecycle.iteration"),
        },
    }

    followup = _pool(markets, "followup")
    fluct = _pool(markets, "bucket1_fluctuations")
    pp = _pool(markets, "prepurchase")
    review = _pool(markets, "market_review_context")

    # ---- §3 CE cap: keep all actionable CEs (buckets/movers/PP/followup/ce-digest) + top-N by W0 revenue.
    # Movers + structural already ran on the FULL set above, so only the browse table is trimmed; every
    # referenced CE stays so its drawer opens.
    CAP = 300
    def _ids(rows):
        return {str(r.get("ce_id")) for r in rows if r.get("ce_id") is not None}
    lm = bf["defend"]["losing_money"]
    ref = set()
    for k in ("bleeders", "full_waste", "recovered", "paused", "tracking_gap"):
        ref |= _ids(lm[k])
    ref |= _ids(bf["defend"]["seasonality_down"]) | _ids(bf["compound"]["seasonality_up"])
    ref |= _ids(bf["compound"]["scale_up"]) | _ids(bf["lifecycle"]["new_ces"]) | _ids(bf["lifecycle"]["iteration"])
    ref |= _ids(week_header["trend"]["top_gainers"]) | _ids(week_header["trend"]["top_droppers"])
    ref |= _ids(fluct) | _ids(pp) | _ids(followup)
    ref |= {str(c.get("ce_id")) for c in review if c.get("scope") == "ce" and c.get("ce_id")}
    ranked = sorted(ces, key=lambda c: -((c.get("weekly") or [{}])[-1].get("revenue") or 0))
    keep = ref | {str(c["ce_id"]) for c in ranked[:CAP]}
    n_full = len(ces)
    ces_capped = [c for c in ces if str(c["ce_id"]) in keep]

    meta0 = dict(next(iter(markets.values()))["meta"])
    meta0.update({"market": "Headout (all markets)", "market_slug": "headout",
                  "n_markets": len(slugs), "markets_included": slugs,
                  "ce_cap": {"shown": len(ces_capped), "total": n_full, "cap": CAP,
                             "note": f"All-CE view: top {CAP} by revenue + all flagged / mover / PP CEs "
                                     f"({len(ces_capped)} of {n_full})"}})

    snap = {
        "meta": meta0,
        "market_summary": {"weekly": weekly, "weekly_ly": weekly_ly, "headlines": headlines},
        "ces": ces_capped,
        "followup": followup,
        "bucket1_fluctuations": fluct,
        "buckets_final": bf,
        "prepurchase": pp,
        "no_bid_campaigns": _merge_no_bid(markets),
        "seasonality_adjustments": _pool(markets, "seasonality_adjustments"),
        "levers": _pool(markets, "levers"),
        "transitions": _pool(markets, "transitions"),
        "market_review_context": review,
        "_diagnostics": {"aggregate_of": slugs, "n_ces_full": n_full, "n_ces_shown": len(ces_capped)},
    }
    return snap


def _apply_aggregate_structural(week_header, ces, weekly_ly, w0_iso, raw_rev):
    """Portfolio-level structural clock: expected W0 = W-1 × R, R = ΣLY(W0)/ΣLY(W-1)
    (trailing LY WoW ratio from the summed LY series — no forward week). Applies R
    uniformly to every CE, so gains/losses/N80 stay a real decomposition but on a
    blended-seasonality basis. Overrides week_header structural + week_type + dual label."""
    ly_weeks = [w["week"] for w in weekly_ly]
    R = None
    if w0_iso in ly_weeks:
        i = ly_weeks.index(w0_iso)
        if i > 0:
            ly0, lym1 = weekly_ly[i].get("revenue"), weekly_ly[i - 1].get("revenue")
            if ly0 and lym1:
                R = ly0 / lym1
    gvals, lvals = [], []
    for ce in ces:
        wk = ce.get("weekly") or []
        if len(wk) < 2:
            continue
        w0r, wm1r = wk[-1].get("revenue"), wk[-2].get("revenue")
        if w0r is None or wm1r is None:
            continue
        expected = wm1r * (R - 1.0) if R is not None else 0.0
        struct = (w0r - wm1r) - expected
        (gvals if struct >= 0 else lvals).append(abs(struct))
    G, L = sum(gvals), sum(lvals)
    week_header["structural"] = {
        "gains_usd": round(G), "losses_usd": round(L), "net_usd": round(G - L),
        "n80_gain": flows._n80(sorted(gvals, reverse=True)),
        "n80_loss": flows._n80(sorted(lvals, reverse=True)),
        "ly_ratio": round(R, 4) if R else None,
        "basis": "aggregate trailing LY ratio (portfolio-blended)",
    }
    floor = max(500.0, 0.005 * raw_rev)
    net = G - L
    week_header["week_type"] = (
        (f"Both large — gains beat by ${net:,.0f}" if net >= 0 else f"Both large — losses beat by ${-net:,.0f}")
        if (G > floor and L > floor) else
        "Mostly gains" if (G > L and G > floor) else
        "Mostly loss" if (L > G and L > floor) else "Mostly stable")
    raw_wow = week_header["raw"].get("wow_pct")
    if raw_wow is not None:
        week_header["dual_clock_label"] = (
            "BEATING SEASONALITY" if (net >= 0 and raw_wow < 0) else
            "UNDER-RAMPING vs LY seasonality" if (net < 0 and raw_wow >= 0) else
            week_header["week_type"])
        week_header["clocks_disagree"] = ((raw_wow >= 0) != (net >= 0))


def _sum_burn(markets):
    tot = {"count": 0, "bleed_wk": 0.0, "names": []}
    for m in markets.values():
        b = (((m.get("buckets_final") or {}).get("defend") or {}).get("losing_money") or {}).get("burn_line") or {}
        tot["count"] += b.get("count") or 0
        tot["bleed_wk"] += b.get("bleed_wk") or 0
        tot["names"].extend(b.get("names") or [])
    tot["bleed_wk"] = round(tot["bleed_wk"])
    return tot


def _merge_no_bid(markets):
    rows, cnt, spend = [], 0, 0.0
    for m in markets.values():
        nb = m.get("no_bid_campaigns") or {}
        rows.extend(nb.get("rows") or [])
        t = nb.get("totals") or {}
        cnt += t.get("count") or 0
        spend += t.get("spend_total") or 0
    return {"totals": {"count": cnt, "spend_total": round(spend)}, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", required=True, help="W0 Monday YYYY-MM-DD")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    snap = build_global(args.week)
    out = Path(args.out) if args.out else CACHE / f"snapshot_headout_{args.week}.json"
    out.write_text(json.dumps(snap, default=str))
    print(f"  wrote {out}  ({len(snap['ces'])} CEs, {out.stat().st_size//1024} KB)")
    print(f"  Headout W0 revenue: {snap['market_summary']['headlines']['revenue_w0']}")


if __name__ == "__main__":
    main()
