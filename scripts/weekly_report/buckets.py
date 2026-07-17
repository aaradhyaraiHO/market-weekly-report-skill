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
RECOVER_CM2_IMPROVE_PCT = 50.0   # bleed halved vs prior-3wk avg → "Recovering" (2026-07-17; tunable to 100)
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
ITER_TAKEOFF_CLK4 = 100                             # Iteration "waiting for takeoff": <100 clicks / 4wk (≈ monthly floor)

# Band helpers — prefer the canonical bands.py; fall back to inline Pro threshold.
try:
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.expanduser("~/analytics"))
    from scripts.ce_buckets.bands import (band_for as _band_for, is_pro_plus as _is_pro_plus,
                                          band_rank as _band_rank)
except Exception:  # not importable from the worktree → replicate Pro gate inline
    _LADDER = ["Does Not Exist", "Long Tail", "Seed", "Pro", "2x Pro", "Hero", "2x Hero", "5x Hero"]
    def _band_for(revenue, window="monthly"):
        v = revenue or 0
        if v <= 0: return "Does Not Exist"
        for name, thr in [("5x Hero", 83333), ("2x Hero", 33333), ("Hero", 16667),
                          ("2x Pro", 6667), ("Pro", 3333), ("Seed", 667)]:
            if v >= thr: return name
        return "Long Tail"
    def _is_pro_plus(band):
        return band in {"Pro", "2x Pro", "Hero", "2x Hero", "5x Hero"}
    def _band_rank(band):
        return _LADDER.index(band) if band in _LADDER else 0


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
def _new_existing(ce):
    """New vs Existing (2026-07-17): metadata.new_vs_existing=='New' → New; everything else
    (Existing / Unknown) defaults to Existing. Drives the split pause-ROI guideline."""
    return "New" if ((ce.get("metadata") or {}).get("new_vs_existing") == "New") else "Existing"
def _median(v):
    v = sorted(x for x in v if x is not None)
    if not v: return None
    n = len(v); m = n // 2
    return v[m] if n % 2 else (v[m - 1] + v[m]) / 2
def _mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None
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
    """DEFEND · unified CM2-bleed table. b1 = {ce_id: movement} from bucket_b1.

    Funded CEs (spend_4w > $1k) are classified IN ORDER:
      FULL WASTE   — ad_conversions_4w == 0 (spend, zero paid conversions = total loss)
      PAUSED       — spend_wk == 0 (was funded across the 4wk window, stopped this week;
                     ROI reads null because spend is 0 → confirm the pause was intentional)
      TRACKING GAP — roi is None with spend_wk > 0 (current-week CM1 feed gap; verify, NOT waste)
      BLEEDER      — roi < 100 AND cm2_bleed_4w <= -$200 (material bleed; the -$200/4w floor
                     removes near-breakeven noise rows)
    Sub-$1k funded CEs that bleed roll up into burn_line (names carried for the hover).

    Every Δ4w is vs the PRIOR 4 weeks (wk[-5:-1], current week EXCLUDED); nulls skipped —
    consistent across roi/rpc/cpc/clicks/tr (locked 2026-07-16 review). Spend renders as the
    Δ4w % only (no 4-week $ total — CM2 bleed already carries the dollars burned).
    """
    bleeders, recovered, full_waste, paused, tracking_gap = [], [], [], [], []
    burn = {"count": 0, "bleed": 0.0, "items": []}
    # Google-Search-only decision basis (2026-07-17) when the split columns are present; falls
    # back to the Google+Bing business metrics on pre-split (cached) snapshots.
    has_g = any("spend_g" in (w or {}) for ce in ces for w in (ce.get("weekly") or []))
    SPK, CMK, RK, CPK = ("spend_g", "cm1_g", "roi_g", "cpc_g") if has_g else ("spend", "cm1", "roi_pct", "cpc")
    for ce in ces:
        wk = ce.get("weekly") or []
        if len(wk) < 4: continue
        w0 = wk[-1]; roi = w0.get(RK)
        sp4 = sum((w.get(SPK) or 0) for w in wk[-4:]); spw = w0.get(SPK) or 0
        series = [w.get(RK) for w in wk]
        # long-tail burn: bleeding but under the $1k gate → aggregate line. The ≥3-active-weeks
        # noise gate applies HERE only; for funded CEs the $1k/4wk spend gate is the activity filter
        # (a CE that dumped >$1k in 2 weeks with 0 conversions is a real full-waste, not noise).
        if sp4 <= BLEED_SPEND4W:
            if _active(ce) and roi is not None and roi < BLEED_ROI and spw > 0:
                burn["count"] += 1; burn["bleed"] += spw * (roi / 100 - 1)
                burn["items"].append((ce["ce_name"], spw * (roi / 100 - 1)))
            continue
        # --- funded CE: shared 4-week aggregates + full metric bundle (all Δ4w vs prior-4) ---
        prior = wk[-5:-1]                                  # base for every Δ4w (current excluded)
        cm2_series = [((w.get(CMK) or 0) - (w.get(SPK) or 0)) for w in wk]   # Google-search CM2
        cm2_4w = sum(cm2_series[-4:])
        adconv4 = sum((w.get("ad_conversions") or 0) for w in wk[-4:])
        orders4 = sum((w.get("orders") or 0) for w in wk[-4:])
        def vsp(key, pp=False):                            # value vs prior-4 mean (nulls skipped)
            now = w0.get(key); base = _mean([x.get(key) for x in prior])
            if now is None or base is None: return None
            return round(now - base) if pp else (round((now / base - 1) * 100) if base else None)
        spend_base = _mean([x.get(SPK) for x in prior])
        rpc_hist = [x.get("rpc") for x in prior if x.get("rpc")]
        cat = cat_rpc.get((ce.get("metadata") or {}).get("category"))
        # one metric bundle, shared by full_waste + bleeders (so both render the same columns).
        # CM2/wk = current (cm1 − spend) directly — same definition as the 4w sum (no roi round-trip).
        feat = {
            "roi": (round(roi) if roi is not None else None),
            "roi_dpp": (round(roi - wk[-2].get(RK))
                        if (len(wk) > 1 and roi is not None and wk[-2].get(RK) is not None) else None),
            "roi_v4": vsp(RK, pp=True),
            "cm2_bleed_wk": round((w0.get(CMK) or 0) - (w0.get(SPK) or 0)),
            "spend_wk": round(spw),
            "spend_dvs4": (round((spw / spend_base - 1) * 100) if (spw and spend_base) else None),
            "spend_wow": (round((spw / (wk[-2].get(SPK) or 0) - 1) * 100)
                          if (len(wk) > 1 and spw and wk[-2].get(SPK)) else None),
            "clicks": w0.get("clicks"), "clicks_v4": vsp("clicks"),
            "rpc": w0.get("rpc"), "rpc_v4": vsp("rpc"),
            "rpc_vs_4w": (round((w0["rpc"] / (sum(rpc_hist) / len(rpc_hist)) - 1) * 100)
                          if (w0.get("rpc") and len(rpc_hist) >= 2) else None),
            "cpc": w0.get(CPK), "cpc_v4": vsp(CPK),
            "tr_pct": w0.get("tr_pct"), "tr_v4": vsp("tr_pct", pp=True),
            "rpc_vs_cat": _vs_cat(w0.get("rpc"), cat),
            "rpc_upside": (round((cat - w0["rpc"]) * (w0.get("clicks") or 0))
                           if (w0.get("rpc") and cat and w0["rpc"] < cat) else None),
        }
        # Recovering (2026-07-17): still bleeding but the weekly CM2 loss is shrinking fast vs
        # the prior-3wk average. improve% = (now − prior3avg)/|prior3avg| → +50% = bled halved,
        # +100% = breakeven. Only meaningful when the prior window was actually bleeding.
        cm2_now = cm2_series[-1]
        cm2_prior3 = cm2_series[-4:-1]
        cm2_prior3avg = (sum(cm2_prior3) / len(cm2_prior3)) if cm2_prior3 else None
        cm2_improve_pct = (round((cm2_now - cm2_prior3avg) / abs(cm2_prior3avg) * 100)
                           if (cm2_prior3avg is not None and cm2_prior3avg < 0) else None)
        recovering = (cm2_improve_pct is not None and cm2_improve_pct >= RECOVER_CM2_IMPROVE_PCT)
        base_row = {"ce_id": ce["ce_id"], "ce_name": ce["ce_name"], "spend_4w": round(sp4),
                    "cm2_bleed_4w": round(cm2_4w), "orders_4w": round(orders4), "adconv_4w": round(adconv4),
                    "cm2_series": cm2_series[-12:], "cm2_weeks": [w.get("week") for w in wk][-12:],
                    "tier": _tier(ce), "new_existing": _new_existing(ce), "movement_b1": b1.get(ce["ce_id"]),
                    "cm2_improve_pct": cm2_improve_pct, "recovering": recovering}
        if adconv4 == 0:                                   # spend, zero paid conversions = FULL WASTE
            full_waste.append({**base_row, **feat}); continue
        if spw == 0:                                       # spend stopped this week → PAUSED
            paused.append(base_row); continue
        if roi is None:                                    # spending but ROI didn't compute → feed gap
            tracking_gap.append(base_row); continue
        if roi < BLEED_ROI and cm2_4w <= -200:             # material bleeder
            w = _bleed_streak(series)
            dpp = feat["roi_dpp"]
            status = "NEW" if w == 1 else ("CHRONIC" if w >= 6 else (f"{w}w"))
            if dpp is not None and dpp < -CLIFF_PP: status = "ESCALATING"
            bleeders.append({**base_row, **feat, "status": status, "weeks": w})
        elif roi >= RECOVER_ROI and _bleed_streak(series[:-1]) >= RECOVER_MIN_BLEED:
            recovered.append({"ce_id": ce["ce_id"], "ce_name": ce["ce_name"], "roi": round(roi),
                              "was_bleeding_wks": _bleed_streak(series[:-1])})
    # worst 4-week bled first; Recovering ones pushed to the bottom (2026-07-17)
    bleeders.sort(key=lambda r: (bool(r.get("recovering")), r["cm2_bleed_4w"]))
    full_waste.sort(key=lambda r: -r["spend_4w"])
    paused.sort(key=lambda r: -r["spend_4w"]); tracking_gap.sort(key=lambda r: -r["spend_4w"])
    burn_names = [n for n, _ in sorted(burn["items"], key=lambda x: x[1])]   # worst-first, all names
    return {"bleeders": bleeders, "recovered": recovered, "full_waste": full_waste,
            "paused": paused, "tracking_gap": tracking_gap,
            "burn_line": {"count": burn["count"], "bleed_wk": round(burn["bleed"]), "names": burn_names}}


def seasonality(fluctuations, ces, cat_rpc, cat_cvr):
    """Revenue-quality drops — RPC decomposed into its four multiplicative drivers so the
    reader sees WHICH one moved, not the composite. Qualifiers unchanged (upstream in
    alerts.py: WoW or 3-day daily); this only reshapes the display (2026-07-17 spec).

      RPC = CVR × AOV × CR × TR   (exact identity, with CVR = orders/clicks)

    Per row we surface: the four drivers (value + WoW %Δ, `dominant` = the one explaining the
    move), always-on 28-day spend + pooled 28-day ROI, and clicks as CONTEXT only (traffic is
    never a qualifier — Jul-17). alert_type labels why it fired: WoW vs 3D.

    WoW rows use weekly WoW %Δ; 3D rows use 3-day-vs-28-day %Δ (from alerts.py drivers_3d,
    matching the alert's own window). On pre-split cached snapshots (no drivers_3d) 3D rows
    degrade to the weekly WoW path. CVR is orders/clicks (exact decomposition).
    """
    ce_by = {c["ce_id"]: c for c in ces}
    # 28d ROI + spend are the pause/scale decision metrics → Google-Search only where the split
    # columns exist (2026-07-17); business fallback on pre-split snapshots. Funnel drivers stay
    # total-business (the CVR = orders/clicks decomposition uses business clicks).
    has_g = any("spend_g" in (w or {}) for c in ces for w in (c.get("weekly") or []))
    SPK, CMK = ("spend_g", "cm1_g") if has_g else ("spend", "cm1")
    def pctchg(now, prev):
        return round((now / prev - 1) * 100) if (now is not None and prev) else None
    def cvr_ord(w):                                        # orders/clicks (%) — the exact-decomposition CVR
        o, c = w.get("orders"), w.get("clicks")
        return (100.0 * o / c) if (o is not None and c) else None
    LBL = {"cvr": "CVR", "aov": "AOV", "cr": "Completion", "tr": "Take rate"}
    out = []
    for r in fluctuations:
        ce = ce_by.get(r["ce_id"])
        if not ce or not _active(ce): continue            # existing CEs only
        wk = ce.get("weekly") or []
        w0 = wk[-1] if wk else {}
        wm1 = wk[-2] if len(wk) >= 2 else {}
        d = r.get("direction")
        # always-on context: 28-day spend (Σ) + pooled 28-day ROI (Σcm1/Σspend), Google-search basis,
        # each with a Δ vs the prior 28 days (is it already scaling down / eroding?)
        last4, prev4 = wk[-4:], wk[-8:-4]
        spend_4w = sum((w.get(SPK) or 0) for w in last4)
        cm1_4w = sum((w.get(CMK) or 0) for w in last4)
        roi_4w = round(100 * cm1_4w / spend_4w) if spend_4w else None
        spend_4w_prev = sum((w.get(SPK) or 0) for w in prev4)
        cm1_4w_prev = sum((w.get(CMK) or 0) for w in prev4)
        roi_4w_prev = (100 * cm1_4w_prev / spend_4w_prev) if spend_4w_prev else None
        spend_4w_d = round((spend_4w / spend_4w_prev - 1) * 100) if spend_4w_prev else None
        roi_4w_d = round(roi_4w - roi_4w_prev) if (roi_4w is not None and roi_4w_prev is not None) else None
        alert_type = "3D" if r.get("window") == "sustained_3d" else "WoW"
        d3 = r.get("drivers_3d") if alert_type == "3D" else None
        vals = {}
        if d3:
            # 3-day alert → 3-day value vs 28-day baseline (matches the alert's own window)
            for k, aspct in (("cvr", True), ("aov", False), ("cr", True), ("tr", True)):
                v3 = (d3.get(k) or {}).get("v3")
                vals[k] = (round(v3 * 100, 2) if (v3 is not None and aspct) else (round(v3, 2) if v3 is not None else None))
                vals[k + "_d"] = (d3.get(k) or {}).get("pct")
        else:
            # WoW alert → weekly value + WoW %Δ (all four exact from weekly data)
            mets = {"cvr": (cvr_ord(w0), cvr_ord(wm1)), "aov": (w0.get("aov"), wm1.get("aov")),
                    "cr": (w0.get("cr_pct"), wm1.get("cr_pct")), "tr": (w0.get("tr_pct"), wm1.get("tr_pct"))}
            for k, (now, prev) in mets.items():
                vals[k] = round(now, 2) if now is not None else None
                vals[k + "_d"] = pctchg(now, prev)
        # dominant = the driver whose move best explains the alert direction
        moves = {k: vals[k + "_d"] for k in ("cvr", "aov", "cr", "tr") if vals.get(k + "_d") is not None}
        aligned = {k: v for k, v in moves.items() if v != 0 and (v < 0) == (d == "down")}
        pool = aligned or moves
        dom = max(pool, key=lambda k: abs(pool[k])) if pool else None
        pc = w0.get("paid_contribution_pct")
        cause = r.get("cause_tag")
        roi_now = (w0.get("roi_pct") or 0)
        verdict = ("+ve" if (d == "up" and roi_now > SEAS_UP) else "-ve" if (d == "down" and roi_now < SEAS_DN) else "hold")
        # innocence-cascade-aware recommendation (unchanged): unexplained down = investigate
        if pc is not None and pc < LOW_PAID_PCT:      rec = "review — low paid"
        elif cause == "input-induced":                rec = "verify (bid change)"
        elif cause == "supply-linked":                rec = "route Ops (supply)"
        elif verdict == "+ve":                        rec = "+15%/7d"
        elif verdict == "-ve":                        rec = "investigate" if cause == "unexplained" else "-15%/7d"
        else:                                         rec = "verify/hold"
        out.append({
            "ce_id": r["ce_id"], "ce_name": r["ce_name"],
            "direction": d, "group": ("Compound" if d == "up" else "Defend"),
            "alert_type": alert_type, "swing_pct": r.get("magnitude_pct"),
            "roi_4w": roi_4w, "spend_4w": round(spend_4w) if spend_4w else None,
            "roi_4w_d": roi_4w_d, "spend_4w_d": spend_4w_d,
            "cvr": vals["cvr"], "cvr_d": vals["cvr_d"], "aov": vals["aov"], "aov_d": vals["aov_d"],
            "cr": vals["cr"], "cr_d": vals["cr_d"], "tr": vals["tr"], "tr_d": vals["tr_d"],
            "clicks": w0.get("clicks"), "clicks_d": pctchg(w0.get("clicks"), wm1.get("clicks")),
            "dominant": LBL.get(dom), "dominant_key": dom,
            "verdict": verdict, "cause": cause, "paid_pct": pc, "recommendation": rec,
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


def new_ces(ces, prior_pp=None, launch_map=None):
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
    prior_pp = prior_pp or {}; launch_map = launch_map or {}
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
            "mo_since_launch": launch_map.get(_num_id(ce["ce_id"])),
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


def iteration(ces, mmp_map, cat_cvr, prior_pp=None, week_start=None, launch_map=None):
    """LIFECYCLE · Iteration / Untapped — weekly adaptation of the monthly
    ce_buckets definition (classify.py §6). Both require never-Pro+; split by MMP.

    Base gate: existing CE, NEVER Pro+ (prior-4Q quarterly gate `prior_pp` AND not
    currently Pro+ by run-rate band). Clean complements on MMP recency:

    ITERATION (has_team_input_l6m) — reason CASCADE (what to fix), computed on
      TRAILING-4WK POOLED signals (single-week clicks/CVR are too noisy for these
      low-traffic CEs — see the weekly/monthly cadence note):
        1. "Waiting for takeoff" — 4wk clicks < ITER_TAKEOFF_CLK4 (barely any traffic)
        2. "Needs inputs"        — 4wk pooled CVR < category median (converts poorly)
        3. "Manual check"        — on it, has clicks + OK CVR, still not graduating
    UNTAPPED (no MMP) — dormant complement: ≥ Seed scale, never Pro+, nobody working it.

    new_this_week = MMP handover within 14 days of week_start (freshly handed over) —
    the weekly *change* overlay on an otherwise slow-moving state bucket.
    """
    prior_pp = prior_pp or {}; launch_map = launch_map or {}
    ws = None
    if week_start:
        try:
            import datetime as _dt
            ws = _dt.date.fromisoformat(str(week_start)[:10])
        except Exception:
            ws = None
    out = []
    for ce in ces:
        wk = ce.get("weekly") or []
        if not _active(ce) or len(wk) < 4: continue
        cid = str(ce["ce_id"])
        mmp = mmp_map.get(_num_id(cid)) or {}
        has_mmp = bool(mmp.get("has_team_input_l6m"))
        rr_wk = _run_rate_wk(wk); rr_mo = rr_wk * WEEKS_PER_MONTH
        band = _band_for(rr_mo, "monthly")
        # never Pro+ : not Pro+ in prior 4Q (quarterly gate) AND not currently Pro+
        if _is_pro_plus(band) or prior_pp.get(cid) is True: continue
        rev, clk = _rev_series(wk), _clk_series(wk)
        clk4 = sum((w.get("clicks") or 0) for w in wk[-4:])
        ord4 = sum((w.get("orders") or 0) for w in wk[-4:])
        cvr4 = (100.0 * ord4 / clk4) if clk4 else None
        cat_med = cat_cvr.get((ce.get("metadata") or {}).get("category"))
        new_flag = False
        if ws and mmp.get("mmp_handover_date"):
            try:
                import datetime as _dt
                hd = _dt.date.fromisoformat(str(mmp["mmp_handover_date"])[:10])
                new_flag = 0 <= (ws - hd).days <= 14
            except Exception:
                pass
        if has_mmp:
            if clk4 < ITER_TAKEOFF_CLK4:
                lane, reason = "iteration", "Waiting for takeoff"
            elif cvr4 is not None and cat_med is not None and cvr4 < cat_med:
                lane, reason = "iteration", "Needs inputs"
            else:
                lane, reason = "iteration", "Manual check"
        else:
            if _band_rank(band) < _band_rank("Seed"): continue   # Untapped keeps a ≥Seed floor
            lane, reason = "untapped", "Untapped"
        out.append({
            "ce_id": ce["ce_id"], "ce_name": ce["ce_name"], "lane": lane, "reason": reason,
            "has_mmp": has_mmp, "new_this_week": new_flag,
            "mmp_handover_date": mmp.get("mmp_handover_date"),
            "mmp_iteration_count_l6m": mmp.get("mmp_iteration_count_l6m"),
            "band": band, "run_rate_mo": round(rr_mo),
            "mo_since_launch": launch_map.get(_num_id(cid)),
            "clicks_4w": round(clk4), "cvr_4w": (round(cvr4, 1) if cvr4 is not None else None),
            "cvr_cat_med": (round(cat_med, 1) if cat_med is not None else None),
            "traction": {"rev_wow_pct": _wow_pct(rev), "clicks_wow_pct": _wow_pct(clk)},
        })
    out.sort(key=lambda r: (r["lane"], not r["new_this_week"], -r["run_rate_mo"]))
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


def _launch_map(snap):
    """{numeric_ce_id: months_since_first_ga_click}. Guarded CE-age proxy.

    Months since the CE's FIRST paid Google-Ads click (ads_campaign_stats, Google
    Ads only, earliest report_date with clicks>0). NOT the Headout launch/creation
    date — understates true age for CEs that ran on Bing or grew organically first.
    Matches the monthly notebook's "Mo since launch". Empty map on any failure.
    """
    meta = snap.get("meta") or {}
    week = meta.get("week_start")
    try:
        import os, sys, datetime
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import config
        from bq import query_df
        ids = sorted({_num_id(c["ce_id"]) for c in snap.get("ces", [])})
        ws = datetime.date.fromisoformat(str(week)[:10])
        sql = f"""
        SELECT CAST(campaign_target_combined_entity_id AS STRING) AS ce_id,
               MIN(CASE WHEN count_clicks > 0 THEN report_date END) AS first_click
        FROM `{config.BQ_PROJECT}.{config.BQ_DATASET}.ads_campaign_stats`
        WHERE ad_platform = 'Google Ads'
              AND CAST(campaign_target_combined_entity_id AS STRING) IN UNNEST(@ids)
        GROUP BY 1
        """
        df = query_df(sql, "ce_launch", {"ids": ids})
        out = {}
        for _, r in df.iterrows():
            fc = r["first_click"]
            if fc is None or str(fc) in ("", "None", "NaT"):
                continue
            try:
                d = (fc if (hasattr(fc, "isoformat") and not isinstance(fc, str))
                     else datetime.date.fromisoformat(str(fc)[:10]))
                out[str(r["ce_id"])] = max(0, round((ws - d).days / 30.44))
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"[buckets] WARNING: launch-date fetch failed ({e!r}); "
              f"New CEs 'Mo since launch' will be blank.")
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
    launch = _launch_map(snap)
    return {
        "defend": {"losing_money": losing_money(ces, b1, cat_rpc),
                   "seasonality_down": [s for s in seas if s["direction"] == "down"]},
        "compound": {"scale_up": scale_up(ces, troas, mw, cat_rpc, cat_cvr),
                     "seasonality_up": [s for s in seas if s["direction"] == "up"]},
        "lifecycle": {"new_ces": new_ces(ces, prior_pp, launch),
                      "iteration": iteration(ces, mmp, cat_cvr, prior_pp,
                                             (snap.get("meta") or {}).get("week_start"), launch)},
    }


if __name__ == "__main__":
    import sys, pickle
    snap = pickle.load(open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/na_snap.pkl", "rb"))
    b = build_buckets(snap)
    lm = b["defend"]["losing_money"]
    print("== DEFEND · Losing Money ==")
    print(f"  bleeders {len(lm['bleeders'])} (${sum(x['cm2_bleed_wk'] for x in lm['bleeders']):,}/wk) · "
          f"full-waste {len(lm['full_waste'])} · paused {len(lm['paused'])} · tracking-gap {len(lm['tracking_gap'])} · "
          f"recovered {len(lm['recovered'])} · burn {lm['burn_line']['count']}")
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
    ia = [r for r in it if r["lane"] == "iteration"]; ib = [r for r in it if r["lane"] == "untapped"]
    print(f"== LIFECYCLE · Iteration {len(it)} (iteration {len(ia)} · untapped {len(ib)}) ==")
    for r in (ia[:4] + ib[:2]):
        print(f"    {r['ce_name'][:24]:24s} {r['lane']:9s} {r['reason']:20s} {'NEW' if r['new_this_week'] else '   '} · {r['band']:8s} clk4w {r['clicks_4w']:>5} · CVR4w {r['cvr_4w']}/{r['cvr_cat_med']}cat")
