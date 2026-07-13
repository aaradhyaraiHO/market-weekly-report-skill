"""
Weekly buckets — FINAL production engine (locked 2026-07-13).

Defend/Compound over the existing B1/B2/B4 detection engines, reorganized:
  DEFEND  = Losing Money (CM2 bleed, state + movement column)  +  Seasonality ↓
  COMPOUND = Scale-Up (ROI≥155% ≥3-of-4 wk, not cliffed)        +  Seasonality ↑

Seasonality is ONE Fluctuations table (CM1/conv detects, RPC = evidence), split by
direction. Consumes a market snapshot (build_snapshot.build_market output). Pure logic.
Stress-tested NA+IT+OC → 0 anomalies.
"""
from __future__ import annotations

# ---- locked constants ----
BLEED_ROI, BLEED_SPEND4W = 100.0, 1000.0
SEAS_UP, SEAS_DN = 140.0, 120.0
SCALE_ROI, SCALE_MIN_OF_4 = 155.0, 3
CLIFF_PP = 30.0
MIN_ACTIVE = 3
RECOVER_ROI, RECOVER_MIN_BLEED = 105.0, 2
GAIN_FLOOR_ABS, GAIN_FLOOR_PCT = 500.0, 0.005
LOW_PAID_PCT = 30.0
SIG = {"cm1_per_conv": "CM1/conv", "rpc": "RPC", "cvr": "CVR"}

# ---- lifecycle constants (New CEs + Iteration) ----
# Pro band = $3,333/mo run-rate (monthly band; bands.PRO_PLUS gate). Weekly Pro
# floor = monthly / 4.345 ≈ $767/wk. WEEKS_PER_MONTH converts weekly means to a
# monthly run-rate for band mapping. On-pace lane needs ≥70% of the weekly floor.
PRO_MONTHLY = 3333.0
WEEKS_PER_MONTH = 4.345
PRO_WEEKLY = PRO_MONTHLY / WEEKS_PER_MONTH          # ≈ $767/wk
ONPACE_FRAC = 0.70                                  # Lane B: ≥70% of Pro-weekly
RUNRATE_WKS = 4                                      # trailing-4wk run-rate

# Band helpers — prefer the canonical bands.py; fall back to inline Pro threshold.
try:
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.expanduser("~/analytics"))
    from scripts.ce_buckets.bands import band_for as _band_for, is_pro_plus as _is_pro_plus
except Exception:  # not importable from the worktree → replicate Pro gate inline
    def _band_for(revenue, window="monthly"):
        v = revenue or 0
        if v <= 0: return "Does Not Exist"
        for name, thr in [("5x Hero", 83333), ("2x Hero", 33333), ("Hero", 16667),
                          ("2x Pro", 6667), ("Pro", 3333), ("Seed", 667)]:
            if v >= thr: return name
        return "Long Tail"
    def _is_pro_plus(band):
        return band in {"Pro", "2x Pro", "Hero", "2x Hero", "5x Hero"}


def _rows(o): return (o.get("rows") if isinstance(o, dict) else o) or []
def _active(ce):
    wk = ce.get("weekly") or []
    return sum(1 for w in wk[-4:] if (w.get("revenue") or 0) > 0 or (w.get("spend") or 0) > 0) >= MIN_ACTIVE
def _bleed_streak(seq):
    s = 0
    for r in reversed(seq):
        if r is not None and r < BLEED_ROI: s += 1
        else: break
    return s
def _roi_series(wk): return [w.get("roi_pct") for w in wk]
def _rev_series(wk): return [(w.get("revenue") or 0) for w in wk]
def _clk_series(wk): return [(w.get("clicks") or 0) for w in wk]
def _run_rate_wk(wk, n=RUNRATE_WKS):
    """Mean weekly revenue over the last n weeks."""
    seq = _rev_series(wk)[-n:]
    return sum(seq) / len(seq) if seq else 0.0
def _rising(seq, of_last=3, need=2):
    """True if the value rose WoW in ≥`need` of the last `of_last` steps."""
    tail = seq[-(of_last + 1):]
    ups = sum(1 for a, b in zip(tail, tail[1:]) if b > a)
    return ups >= need
def _rising_consec(seq, need=2):
    """True if the last `need` WoW steps are all strictly rising."""
    if len(seq) < need + 1: return False
    tail = seq[-(need + 1):]
    return all(b > a for a, b in zip(tail, tail[1:]))
def _num_id(ce_id):
    """Match a snapshot ce_id ('1515' or '10 - Hawaii') to the MMP map's numeric key."""
    return str(ce_id).split(" - ")[0].strip()
def _wow_pct(seq):
    """Latest week-over-week % change (None if prior week is 0/missing)."""
    if len(seq) < 2 or not seq[-2]: return None
    return round((seq[-1] / seq[-2] - 1) * 100)
def _tier(ce):
    """Hero/Pro/Seed/Longtail from metadata.tier (e.g. '1. Hero 2025' -> 'Hero')."""
    t = ((ce.get("metadata") or {}).get("tier") or "")
    for w in ("Hero", "Pro", "Seed", "Longtail", "Long Tail"):
        if w.lower() in t.lower(): return "Longtail" if "long" in w.lower() else w
    return None
def _median(v):
    v = sorted(x for x in v if x is not None)
    if not v: return None
    n = len(v); m = n // 2
    return v[m] if n % 2 else (v[m - 1] + v[m]) / 2
def _cat_benchmarks(ces):
    """Median RPC / CVR per category (active CEs, >=3 per cat) — intra-market snapshot benchmark."""
    from collections import defaultdict
    rpc, cvr = defaultdict(list), defaultdict(list)
    for ce in ces:
        if not _active(ce): continue
        cat = (ce.get("metadata") or {}).get("category")
        if not cat: continue
        w0 = (ce.get("weekly") or [{}])[-1]
        if w0.get("rpc"): rpc[cat].append(w0["rpc"])
        if w0.get("cvr_pct"): cvr[cat].append(w0["cvr_pct"])
    return ({c: _median(v) for c, v in rpc.items() if len(v) >= 3},
            {c: _median(v) for c, v in cvr.items() if len(v) >= 3})
def _vs_cat(val, med): return round((val / med - 1) * 100) if (val and med) else None


def losing_money(ces, b1, cat_rpc):
    """DEFEND · unified CM2-bleed table. b1 = {ce_id: movement} from bucket_b1."""
    bleeders, recovered, suppressed, burn = [], [], [], {"count": 0, "bleed": 0.0}
    for ce in ces:
        wk = ce.get("weekly") or []
        if not _active(ce) or len(wk) < 4: continue
        w0 = wk[-1]; roi = w0.get("roi_pct")
        sp4 = sum((w.get("spend") or 0) for w in wk[-4:]); spw = w0.get("spend") or 0
        series = _roi_series(wk)
        # long-tail burn: bleeding but under the $1k gate → aggregate line
        if sp4 <= BLEED_SPEND4W:
            if roi is not None and roi < BLEED_ROI and spw > 0:
                burn["count"] += 1; burn["bleed"] += spw * (roi / 100 - 1)
            continue
        if roi is None:                                    # funded, ROI unpopulated → suppressed
            suppressed.append({"ce_id": ce["ce_id"], "ce_name": ce["ce_name"], "spend_4w": round(sp4)})
            continue
        if roi < BLEED_ROI:
            w = _bleed_streak(series); dpp = (roi - (wk[-2].get("roi_pct") or roi))
            status = "NEW" if w == 1 else ("CHRONIC" if w >= 6 else (f"{w}w"))
            if dpp < -CLIFF_PP: status = "ESCALATING"
            # bleed diagnosis: RPC vs own prior-4wk avg (yield decay, cliff/gradual) + CPC (cost side of ROI)
            rpc_hist = [x.get("rpc") for x in wk[-5:-1] if x.get("rpc")]
            rpc_vs_4w = (round((w0["rpc"] / (sum(rpc_hist)/len(rpc_hist)) - 1) * 100)
                         if (w0.get("rpc") and len(rpc_hist) >= 2) else None)
            bleeders.append({
                "ce_id": ce["ce_id"], "ce_name": ce["ce_name"], "status": status,
                "roi": round(roi), "roi_dpp": round(dpp), "weeks": w,
                "cm2_bleed_wk": round(spw * (roi / 100 - 1)), "spend_wk": round(spw), "spend_4w": round(sp4),
                "clicks": w0.get("clicks"), "rpc": w0.get("rpc"), "rpc_vs_4w": rpc_vs_4w, "cpc": w0.get("cpc"),
                "tr_pct": w0.get("tr_pct"),
                "movement_b1": b1.get(ce["ce_id"]), "tier": _tier(ce), "yoy": w0.get("yoy_pct"),
                "rpc_vs_cat": _vs_cat(w0.get("rpc"), cat_rpc.get((ce.get("metadata") or {}).get("category"))),
                "rpc_upside": (round((cat_rpc[(ce.get("metadata") or {}).get("category")] - w0["rpc"]) * (w0.get("clicks") or 0))
                              if (w0.get("rpc") and cat_rpc.get((ce.get("metadata") or {}).get("category")) and w0["rpc"] < cat_rpc[(ce.get("metadata") or {}).get("category")]) else None),
            })
        elif roi >= RECOVER_ROI and _bleed_streak(series[:-1]) >= RECOVER_MIN_BLEED:
            recovered.append({"ce_id": ce["ce_id"], "ce_name": ce["ce_name"], "roi": round(roi),
                              "was_bleeding_wks": _bleed_streak(series[:-1])})
    bleeders.sort(key=lambda r: r["cm2_bleed_wk"])       # biggest bleed first
    return {"bleeders": bleeders, "recovered": recovered, "suppressed": suppressed,
            "burn_line": {"count": burn["count"], "bleed_wk": round(burn["bleed"])}}


def seasonality(fluctuations, ces, cat_rpc, cat_cvr):
    """One Fluctuations table (CM1/conv·RPC·CVR), direction+ROI-gate → +ve/−ve/hold. Existing only."""
    ce_by = {c["ce_id"]: c for c in ces}
    out = []
    for r in fluctuations:
        ce = ce_by.get(r["ce_id"])
        if not ce or not _active(ce): continue           # existing CEs only (Aditya)
        wk = ce.get("weekly") or []; roi = (wk[-1].get("roi_pct") if wk else None) or 0
        rpc = wk[-1].get("rpc") if wk else None; rpc_wm1 = wk[-2].get("rpc") if len(wk)>=2 else None
        rpc_wow = round((rpc/rpc_wm1-1)*100) if (rpc and rpc_wm1) else None
        # Δrevenue driver: top factor of the WoW revenue swing (traffic × CVR × AOV × CR × TR),
        # direction-aligned (offsetting factors are a flag, not the reason). $ = revenue impact.
        shap = ce.get("shapley_wow") or {}
        d = r.get("direction")
        delta_rev = shap.get("net_delta")
        allf = {k: shap.get(k) for k in ("traffic", "cvr", "aov", "cr", "tr") if shap.get(k) is not None}
        same = {k: v for k, v in allf.items() if v != 0 and (v < 0) == (d == "down")}
        pool = same or allf
        dk = max(pool, key=lambda k: abs(pool[k])) if pool else None
        lbl = {"traffic": "Traffic", "cvr": "CVR", "aov": "AOV", "cr": "CR", "tr": "TR"}
        def _m(x): return ("$%.1fk" % (abs(x)/1000)) if abs(x) >= 1000 else ("$%d" % abs(x))
        delta_rev_driver = (("↓ " if pool[dk] < 0 else "↑ ") + lbl[dk] + " " + _m(pool[dk])) if dk else None
        # full signed decomposition of the WoW revenue swing — one $ per factor, sorted by
        # magnitude; renderer bolds `dominant` (the direction-aligned lead driver above).
        factor_deltas = sorted(({"label": lbl[k], "usd": round(v)} for k, v in allf.items()),
                               key=lambda x: -abs(x["usd"]))
        dominant = lbl[dk] if dk else None
        w0d = wk[-1] if wk else {}
        r2 = [w.get("roi_pct") for w in wk[-2:] if w.get("roi_pct") is not None]
        verdict = ("+ve" if (d == "up" and roi > SEAS_UP) else "-ve" if (d == "down" and roi < SEAS_DN) else "hold")
        pc = wk[-1].get("paid_contribution_pct") if wk else None
        cause = r.get("cause_tag")
        # (b) innocence-cascade-aware recommendation: unexplained down = investigate, not an auto-cut
        if pc is not None and pc < LOW_PAID_PCT:      rec = "review — low paid"
        elif cause == "input-induced":                rec = "verify (bid change)"
        elif cause == "supply-linked":                rec = "route Ops (supply)"
        elif verdict == "+ve":                        rec = "+15%/7d"
        elif verdict == "-ve":                        rec = "investigate" if cause == "unexplained" else "-15%/7d"
        else:                                         rec = "verify/hold"
        out.append({
            "ce_id": r["ce_id"], "ce_name": r["ce_name"], "signal": SIG.get(r.get("signal"), r.get("signal")),
            "direction": d, "group": ("Compound" if d == "up" else "Defend"),
            "swing_pct": r.get("magnitude_pct"), "window": r.get("window"),
            "roi": round(roi) if roi else None, "roi_2wk": round(sum(r2)/len(r2)) if r2 else None,
            "rpc": rpc, "rpc_wow": rpc_wow, "delta_rev": delta_rev, "delta_rev_driver": delta_rev_driver,
            "factor_deltas": factor_deltas, "dominant": dominant,
            "cvr_pct": w0d.get("cvr_pct"), "cr_pct": w0d.get("cr_pct"), "aov": w0d.get("aov"), "tr_pct": w0d.get("tr_pct"),
            "spend_wk": round(w0d.get("spend")) if w0d.get("spend") is not None else None,
            "verdict": verdict, "cause": r.get("cause_tag"), "paid_pct": pc, "recommendation": rec,
            "tier": _tier(ce), "yoy": w0d.get("yoy_pct"),
            "rpc_vs_cat": _vs_cat(rpc, cat_rpc.get((ce.get("metadata") or {}).get("category"))),
            "cvr_vs_cat": _vs_cat(w0d.get("cvr_pct"), cat_cvr.get((ce.get("metadata") or {}).get("category"))),
        })
    out.sort(key=lambda r: -abs(r.get("swing_pct") or 0))
    return out


def scale_up(ces, troas, market_weekly, cat_rpc, cat_cvr):
    """COMPOUND · ROI≥155% in ≥3 of last 4 wks, not cliffed. Rank by est incremental $/wk."""
    recent = [(w.get("revenue") or 0) for w in market_weekly[-4:]]
    gain_floor = max(GAIN_FLOOR_ABS, GAIN_FLOOR_PCT * (sum(recent) / len(recent) if recent else 0))
    out = []
    for ce in ces:
        wk = ce.get("weekly") or []
        if not _active(ce) or len(wk) < 4: continue
        r4 = [w.get("roi_pct") for w in wk[-4:]]
        n_hi = sum(1 for x in r4 if x is not None and x >= SCALE_ROI)
        w0, wm1 = wk[-1], wk[-2]
        cliffed = (wm1.get("roi_pct") is not None and w0.get("roi_pct") is not None
                   and (wm1["roi_pct"] - w0["roi_pct"]) > CLIFF_PP)
        if n_hi >= SCALE_MIN_OF_4 and not cliffed:
            agg = sum(x for x in r4 if x is not None) / sum(1 for x in r4 if x is not None)
            tro = troas.get(ce["ce_id"]) or 145.0
            if not (80 <= tro <= 400): tro = 145.0  # tROAS sanity bound (bad source values)
            est_incr = (w0.get("revenue") or 0) * 0.15
            out.append({
                "ce_id": ce["ce_id"], "ce_name": ce["ce_name"], "roi_agg4": round(agg),
                "wks_ge_155": n_hi, "troas": round(tro), "pp_vs_troas": round(agg - tro),
                "seasonality_flag": (agg - tro) > 20, "est_incremental_wk": round(est_incr),
                "spend_4w": round(sum((w.get("spend") or 0) for w in wk[-4:])),
                "rpc": w0.get("rpc"), "cvr_pct": w0.get("cvr_pct"),
                "tier": _tier(ce), "yoy": w0.get("yoy_pct"),
                "rpc_vs_cat": _vs_cat(w0.get("rpc"), cat_rpc.get((ce.get("metadata") or {}).get("category"))),
                "cvr_vs_cat": _vs_cat(w0.get("cvr_pct"), cat_cvr.get((ce.get("metadata") or {}).get("category"))),
            })
    out.sort(key=lambda r: -r["est_incremental_wk"])
    return out


def new_ces(ces, prior_pp=None):
    """LIFECYCLE · New CEs — graduation-focused, two lanes.

    Canonical OKR definition: New Pro+ = a CE's FIRST Pro+ period with no Pro+ in
    the prior 4 quarters. Pro threshold = $3,333/mo run-rate ≈ $767/wk.

    Lane A — Graduated (New Pro+): trailing-4wk run-rate maps to Pro+ AND the CE
      was NOT Pro+ in any of the prior 4 calendar quarters.
      · TRUE gate (`prior_pp` supplied by _prior_proplus_map): quarterly band
        history from combined_entity_stats — a CE Pro+ in any prior quarter is
        excluded (established, not newly graduated).
      · PROXY fallback (prior_pp missing/absent for a CE): "was below Pro earlier
        in the 12-week window". Over-flags established CEs that merely dipped —
        `gate` field records which path fired.
    Lane B — On run-rate to Pro: NOT Pro+ yet, weekly run-rate ≥70% of Pro-weekly
      ($767) AND rising (revenue up in ≥2 of last 3 weeks).
    """
    prior_pp = prior_pp or {}
    out = []
    for ce in ces:
        wk = ce.get("weekly") or []
        if not _active(ce) or len(wk) < 4: continue
        rr_wk = _run_rate_wk(wk)                      # mean weekly revenue, last 4wk
        rr_mo = rr_wk * WEEKS_PER_MONTH               # monthly run-rate for band map
        band = _band_for(rr_mo, "monthly")
        rev = _rev_series(wk); clk = _clk_series(wk)
        traj = "rising" if _rising(rev) else "flat"
        w0 = wk[-1]
        row = {
            "ce_id": ce["ce_id"], "ce_name": ce["ce_name"],
            "band": band, "run_rate_mo": round(rr_mo),
            "dollars_to_pro": round(max(0.0, PRO_MONTHLY - rr_mo)),
            "weeks_active": sum(1 for w in wk[-4:]
                                if (w.get("revenue") or 0) > 0 or (w.get("spend") or 0) > 0),
            "trajectory": traj,
            # supporting metrics (is it graduating profitably, and still climbing?)
            "roi": (round(w0["roi_pct"]) if w0.get("roi_pct") is not None else None),
            "rpc": w0.get("rpc"), "cvr_pct": w0.get("cvr_pct"),
            "clicks": w0.get("clicks"),
            "spend_wk": (round(w0["spend"]) if w0.get("spend") is not None else None),
            "yoy": w0.get("yoy_pct"),
            "rev_wow_pct": _wow_pct(rev), "clicks_wow_pct": _wow_pct(clk),
        }
        if _is_pro_plus(band):
            cid = str(ce["ce_id"])
            if cid in prior_pp:
                is_new, gate = (not prior_pp[cid]), "4q"     # true 4-quarter gate
            else:
                earlier_mo = [(r * WEEKS_PER_MONTH) for r in rev[:-RUNRATE_WKS]]
                is_new = any(not _is_pro_plus(_band_for(m, "monthly")) for m in earlier_mo)
                gate = "proxy"
            if is_new:
                out.append({**row, "lane": "A_graduated", "gate": gate})
        else:
            # Lane B: ≥70% of Pro-weekly and rising.
            if rr_wk >= ONPACE_FRAC * PRO_WEEKLY and _rising(rev):
                out.append({**row, "lane": "B_on_pace"})
    out.sort(key=lambda r: (r["lane"], -r["run_rate_mo"]))
    return out


def iteration(ces, mmp_map):
    """LIFECYCLE · Iteration — MMP-execution-focused, two lanes.

    mmp_map = {numeric_ce_id: {has_team_input_l6m, mmp_handover_date,
      first_mmp_handover_date, mmp_iteration_count_l6m}} from fetch_mmp_sheet.
    CEs absent from the map are treated as has_team_input_l6m == False.

    Lane A — MMP, no traction: has_team_input_l6m AND rev/clicks flat-or-down over
      last 4wk (mean(last 2wk) ≤ mean(prior 2wk) on revenue).
    Lane B — Traction, no MMP: NOT has_team_input_l6m AND never Pro (run-rate < Pro)
      AND revenue OR clicks rising ≥2 consecutive weeks.
    """
    out = []
    for ce in ces:
        wk = ce.get("weekly") or []
        if not _active(ce) or len(wk) < 4: continue
        mmp = mmp_map.get(_num_id(ce["ce_id"])) or {}
        has_mmp = bool(mmp.get("has_team_input_l6m"))
        rev, clk = _rev_series(wk), _clk_series(wk)
        rr_wk = _run_rate_wk(wk); rr_mo = rr_wk * WEEKS_PER_MONTH
        band = _band_for(rr_mo, "monthly")
        last2, prior2 = rev[-2:], rev[-4:-2]
        flat_or_down = (sum(last2) / len(last2)) <= (sum(prior2) / len(prior2)) if prior2 else False
        lane = None
        if has_mmp and flat_or_down:
            lane = "A_mmp_no_traction"
        elif (not has_mmp) and (not _is_pro_plus(band)) and \
                (_rising_consec(rev) or _rising_consec(clk)):
            lane = "B_traction_no_mmp"
        if lane is None: continue
        out.append({
            "ce_id": ce["ce_id"], "ce_name": ce["ce_name"], "lane": lane,
            "has_mmp": has_mmp, "mmp_handover_date": mmp.get("mmp_handover_date"),
            "mmp_iteration_count_l6m": mmp.get("mmp_iteration_count_l6m"),
            "traction": {"rev_wow_pct": _wow_pct(rev), "clicks_wow_pct": _wow_pct(clk)},
            "band": band, "run_rate_mo": round(rr_mo),
        })
    out.sort(key=lambda r: (r["lane"], -r["run_rate_mo"]))
    return out


def _prior_proplus_map(snap):
    """{ce_id: was_pro_plus in ANY of the prior 4 calendar quarters}. Guarded.

    The canonical 'New Pro+' gate: a CE is newly graduated only if it was NOT
    Pro+ in any of the 4 calendar quarters BEFORE the current week's quarter.
    Bands each prior quarter's predicted revenue (config.REVENUE_COL) via
    bands.band_for(window='quarterly') — quarterly Pro = $10k — matching the
    band-explorer / OKR definition. A CE Pro+ in any prior quarter → not new.

    One small market-scoped query on combined_entity_stats. Returns {} on any
    auth/network/import failure, so New CEs Lane A degrades to the 12-week proxy.
    """
    meta = snap.get("meta") or {}
    week = meta.get("week_start")
    slug = meta.get("market_slug")
    try:
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import config
        from bq import query_df
        market = config.MARKETS.get(slug) or meta.get("market")
        if not (week and market):
            return {}
        sql = f"""
        SELECT combined_entity_id                 AS ce_id,
               DATE_TRUNC(report_date, QUARTER)   AS q,
               SUM({config.REVENUE_COL})          AS rev
        FROM {config.CE_STATS}
        WHERE business_market = @market
              AND report_date >= DATE_TRUNC(DATE_SUB(DATE(@week), INTERVAL 4 QUARTER), QUARTER)
              AND report_date <  DATE_TRUNC(DATE(@week), QUARTER)
        GROUP BY 1, 2
        """
        df = query_df(sql, "prior_4q_bands", {"market": market, "week": week})
        best = {}                                  # max quarterly rev per CE (0 if all quarters empty)
        for _, r in df.iterrows():
            cid, rev = str(r["ce_id"]), float(r["rev"] or 0)
            best[cid] = max(best.get(cid, float("-inf")), rev)
        # every CE with prior-4Q rows is classified — max rev ≤ 0 → "Does Not Exist" → not Pro+
        return {cid: _is_pro_plus(_band_for(rev, "quarterly")) for cid, rev in best.items()}
    except Exception as e:
        print(f"[buckets] WARNING: prior-4Q band fetch failed ({e!r}); "
              f"New CEs Lane A falls back to the 12-week proxy.")
        return {}


def _mmp_map(snap):
    """Build the MMP status map via the monthly pipeline loader (guarded).

    Falls back to an empty map (and prints a warning) on any auth/network/import
    failure so New CEs still builds.
    """
    import datetime
    week = (snap.get("meta") or {}).get("week_start")
    try:
        y, m, _ = (week or "2026-06-01").split("-")
        month = datetime.date(int(y), int(m), 1)
    except Exception:
        month = datetime.date(2026, 6, 1)
    try:
        import os, sys
        sys.path.insert(0, os.path.expanduser("~/analytics"))
        from scripts.ce_buckets.sources import fetch_mmp_sheet
        return fetch_mmp_sheet(month=month, cache_dir=".cache/ce-buckets", refresh=True)
    except Exception as e:
        print(f"[buckets] WARNING: fetch_mmp_sheet failed ({e!r}); "
              f"falling back to empty MMP map — Iteration Lane A will be empty.")
        return {}


def build_buckets(snap):
    ces = snap["ces"]
    b1 = {r["ce_id"]: r.get("movement") for r in _rows(snap.get("bucket_b1"))}
    troas = {r["ce_id"]: r.get("troas_target_pct") for r in _rows(snap.get("bucket_b1"))}
    fl = _rows(snap.get("bucket1_fluctuations"))
    mw = snap.get("market_summary", {}).get("weekly", [])
    cat_rpc, cat_cvr = _cat_benchmarks(ces)
    seas = seasonality(fl, ces, cat_rpc, cat_cvr)
    mmp = _mmp_map(snap)
    prior_pp = _prior_proplus_map(snap)
    return {
        "defend": {"losing_money": losing_money(ces, b1, cat_rpc),
                   "seasonality_down": [s for s in seas if s["direction"] == "down"]},
        "compound": {"scale_up": scale_up(ces, troas, mw, cat_rpc, cat_cvr),
                     "seasonality_up": [s for s in seas if s["direction"] == "up"]},
        "lifecycle": {"new_ces": new_ces(ces, prior_pp),
                      "iteration": iteration(ces, mmp)},
    }


if __name__ == "__main__":
    import sys, pickle
    snap = pickle.load(open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/na_snap.pkl", "rb"))
    b = build_buckets(snap)
    lm = b["defend"]["losing_money"]
    print("== DEFEND · Losing Money ==")
    print(f"  bleeders {len(lm['bleeders'])} (${sum(x['cm2_bleed_wk'] for x in lm['bleeders']):,}/wk) · "
          f"recovered {len(lm['recovered'])} · suppressed {len(lm['suppressed'])} · burn {lm['burn_line']}")
    for r in lm["bleeders"][:5]:
        print(f"    {r['ce_name'][:24]:24s} {r['status']:11s} ROI {r['roi']:>3} · ${r['cm2_bleed_wk']:>6}/wk · clk {r['clicks']}")
    print(f"== DEFEND · Seasonality↓ {len(b['defend']['seasonality_down'])} == COMPOUND · Seasonality↑ {len(b['compound']['seasonality_up'])} ==")
    print(f"== COMPOUND · Scale-Up {len(b['compound']['scale_up'])} ==")
    for r in b["compound"]["scale_up"]:
        print(f"    {r['ce_name'][:24]:24s} ROI4 {r['roi_agg4']} ({r['wks_ge_155']}/4≥155) · pp {r['pp_vs_troas']:+} · est +${r['est_incremental_wk']}/wk")
    nc = b["lifecycle"]["new_ces"]; it = b["lifecycle"]["iteration"]
    la = [r for r in nc if r["lane"] == "A_graduated"]; lb = [r for r in nc if r["lane"] == "B_on_pace"]
    print(f"== LIFECYCLE · New CEs {len(nc)} (A graduated {len(la)} · B on-pace {len(lb)}) ==")
    for r in (la[:3] + lb[:3]):
        print(f"    {r['ce_name'][:24]:24s} {r['lane']:12s} {r['band']:8s} rr ${r['run_rate_mo']:>6}/mo · to-pro ${r['dollars_to_pro']:>5} · {r['trajectory']}")
    ia = [r for r in it if r["lane"] == "A_mmp_no_traction"]; ib = [r for r in it if r["lane"] == "B_traction_no_mmp"]
    print(f"== LIFECYCLE · Iteration {len(it)} (A MMP/no-traction {len(ia)} · B traction/no-MMP {len(ib)}) ==")
    for r in (ia[:3] + ib[:3]):
        t = r["traction"]
        print(f"    {r['ce_name'][:24]:24s} {r['lane']:18s} mmp {str(r['has_mmp']):5s} · {r['band']:8s} rr ${r['run_rate_mo']:>6}/mo · rev {t['rev_wow_pct']}% clk {t['clicks_wow_pct']}%")
