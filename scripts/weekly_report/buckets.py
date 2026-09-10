"""
Weekly buckets — current production table engine.

Current table families:
  DEFEND  = Losing Money v2 (C1-C5 criteria, Existing/New tables)  +  Seasonality ↓
  COMPOUND = Scale-Up (ROI≥155% ≥3-of-4 wk, not cliffed)        +  Seasonality ↑

Seasonality is ONE Fluctuations table (CM1/conv and RPC detect), split by
direction. Consumes a market snapshot (build_snapshot.build_market output). Pure logic.
Stress-tested NA+IT+OC → 0 anomalies.
"""
from __future__ import annotations

# ---- locked constants ----
# Losing Money materiality gate for the REPORT view (2026-08-08 Aaradhya): CEs under $1k
# Google-Search spend / 4wk aggregate into the burn-line footnote instead of rows. The
# COMPLETE ungated list ships to the Weekly Flagged sheet via export_full_lm (spend_gate=0)
# so perf's verification always has full coverage. Pass spend_gate=0 to losing_money for
# the ungated view. (BLEED_ROI removed — C5 supersedes the old ROI<100 bleeder rule.)
LM_SPEND_GATE = 1000.0
# Losing Money v2 flag thresholds (criteria locked 2026-07-30 meeting; see losing_money docstring)
LM_DELTA_HARD = 500.0          # CM2 drop ($) that flags unconditionally (C2 WoW · C3 vs 3wk avg)
LM_DELTA_SOFT = 200.0          # CM2 drop ($) that flags only when W0 Paid ROI < LM_ROI_GATE
LM_ROI_GATE = 140.0            # W0 Paid-ROI gate for the soft band
LM_NEW_90D_LOSS = 500.0        # C4 (New CEs only): cumulative CM2 over trailing ~90d ≤ −$500
LM_LOSS_FLOOR = 0.0            # C5: W0 CM2 < 0 flags — FLOORLESS (Aaradhya 2026-08-04: "W0 CM2
                               # −ve OR ROI<100 → flag"; the ROI clause is redundant since
                               # ROI<100 ⟺ CM2<0 with spend). Restores the transcript's base
                               # "current week status" check the finalized notes dropped. Losing
                               # CEs enter the report only above the materiality gate.
                               # Raise this if the table gets too noisy to review.
LM_RECOVER_IMPROVE_PCT = 50.0  # W0 loss ≥50% smaller than W1 loss → "recovering" tag
SEAS_UP, SEAS_DN = 140.0, 120.0   # Fluctuations verdict bands: +ve if ROI>140 · -ve if ROI<120
SCALE_ROI, SCALE_MIN_OF_4 = 155.0, 3
CLIFF_PP = 30.0
MIN_ACTIVE = 3
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


def _lm_fired(wkseq, ne, SPK, CMK, RK, CVK):
    """Evaluate C1-C5 with wkseq[-1] as the current week. Returns
    (fired, d_wow, d_3w, cm2_90d, c1). Shared by the main pass (full series) and
    the flagged-last-week recheck (series truncated by one) so the two can't drift."""
    w0 = wkseq[-1]
    spw = w0.get(SPK) or 0
    cm2s = [((w.get(CMK) or 0) - (w.get(SPK) or 0)) for w in wkseq]
    roi = w0.get(RK)
    c1 = (not w0.get(CVK)) and (w0.get(CMK) or 0) <= 0 and spw > 0
    d_wow = (cm2s[-1] - cm2s[-2]) if len(cm2s) >= 2 else None
    p3 = cm2s[-4:-1]
    d_3w = (cm2s[-1] - sum(p3) / len(p3)) if len(p3) == 3 else None
    def _f(d):
        if d is None: return False
        return d <= -LM_DELTA_HARD or (d <= -LM_DELTA_SOFT and roi is not None and roi < LM_ROI_GATE)
    cm2_90d = round(sum(cm2s[-13:]))                      # 12wk window ≈ 90d
    fired = ((["C1"] if c1 else []) + (["C2"] if _f(d_wow) else [])
             + (["C3"] if _f(d_3w) else [])
             + (["C4"] if (ne == "New" and cm2_90d <= -LM_NEW_90D_LOSS) else [])
             + (["C5"] if (cm2s[-1] < 0 and cm2s[-1] <= -LM_LOSS_FLOOR) else []))  # W0 in the red
    return fired, d_wow, d_3w, cm2_90d, c1


def losing_money(ces, troas_now=None, launch=None, prior_pp=None, spend_gate=LM_SPEND_GATE):
    """DEFEND · Losing Money v2 — five flagging criteria (locked 2026-07-30 meeting),
    evaluated per funded CE (> $1k Google-search spend / 4wk). Existing and New CEs
    flag into SEPARATE tables. New = never Pro+ in the prior 4 calendar quarters
    (`prior_pp` from _prior_proplus_map; 2026-08-03 decision — metadata fallback
    only when that fetch fails). Rows carry flagged_lw (same criteria re-run with
    the series truncated one week → "new this wk" vs "repeat" in the report):

      C1  FULL WASTE  — W0 spend > 0, zero conversions AND CM1 <= 0. Current week only,
                        no prior-week comparison. The CM1 guard keeps composite
                        city-suffixed CEs (attribution gap, positive paid CM1) out of
                        the waste label — see 2026-07-27.
      C2  WoW drop    — ΔCM2 = W0 − W1 ≤ −LM_DELTA_HARD flags always; a drop inside
                        (−HARD, −SOFT] flags only when W0 Paid ROI < LM_ROI_GATE
                        (keeps small high-ROI wobbles out, catches the 180→140 slides).
      C3  vs 3wk avg  — ΔCM2 = W0 − mean(W1..W3), same thresholds/ROI gate as C2.
      C4  New only    — cumulative CM2 over the trailing ~90d (the 12wk series)
                        ≤ −LM_NEW_90D_LOSS: chronic slow bleed on a scaling CE.
      C5  W0 in red   — W0 CM2 < 0, floorless (LM_LOSS_FLOOR=0), regardless of deltas
                        or ROI. The transcript's base "current week status" check
                        (2026-08-04).

    Labels are TAGS, not groupings (sort is label-agnostic):
      full_waste (C1) · bleeding (W0 CM2 < 0) · recovering (W0 CM2 still < 0 but the
      loss shrank ≥ LM_RECOVER_IMPROVE_PCT% vs W1) · eroding (W0 CM2 ≥ 0, flagged on
      the drop). Sort = most negative Δ among the fired criteria, biggest drop first.

    Each row carries raw W0..W3 weekly blocks (cm2 · cm1(=revenue) · clicks · cvr ·
    cpc · roi, NEWEST FIRST) so the reader sees weeks, not decoded deltas. `driver` =
    argmin of the clicks-anchored CM2 contributions vs the pooled W1..W3 baseline
    (clicks · cvr · valconv · cpc; 3-factor clicks/rpc/cpc fallback) — bolded in the
    report. All rows carry troas_l4w (avg L4W target ROAS, spend-weighted); New-CE
    rows add launch_date / days_since_launch (`launch` map), troas_now (target ROAS
    as of run date) and cm2_90d. tROAS values from the `troas_now` map.

    Scope (2026-08-08): every CE spending this week is evaluated by the 5 criteria; the
    REPORT view applies a $1k/4wk materiality gate (`spend_gate`) — sub-gate CEs that
    are losing this week aggregate into the burn_line footnote instead of rows. The
    COMPLETE ungated view (spend_gate=0) ships to the Weekly Flagged sheet via
    export_full_lm so perf verification always sees full coverage. Two data-validity
    guards (not criteria): paused (spend=0 after recent spend) and tracking_gap (CM1
    missing from the feed — CM2 unknowable). No history minimum; no subthreshold
    footnote (C5 makes it empty by definition).
    """
    troas_now = troas_now or {}; launch = launch or {}
    existing, new_rows, paused, tracking_gap = [], [], [], []
    burn = {"count": 0, "bleed": 0.0, "items": []}   # sub-gate CEs losing this week (report view)
    def _route(ce):
        # New = never Pro+ in the prior 4 calendar quarters (combined_entity_stats
        # quarterly bands via _prior_proplus_map) — 2026-08-03 decision. Replaces the
        # sparse metadata.new_vs_existing (Unknown/NULL silently defaulted to Existing
        # — the San Siro case). CEs with NO prior-4Q revenue rows at all → New.
        # Metadata fallback only when the 4Q fetch failed (prior_pp empty).
        if prior_pp:
            v = prior_pp.get(str(ce["ce_id"]))
            if v is None: v = prior_pp.get(_num_id(ce["ce_id"]))
            if v is None: return "New"
            return "Existing" if v else "New"
        return _new_existing(ce)
    # Google-Search-only decision basis (2026-07-17) when the split columns are present; falls
    # back to the Google+Bing business metrics on pre-split (cached) snapshots.
    has_g = any("spend_g" in (w or {}) for ce in ces for w in (ce.get("weekly") or []))
    SPK, CMK, RK, CPK = ("spend_g", "cm1_g", "roi_g", "cpc_g") if has_g else ("spend", "cm1", "roi_pct", "cpc")
    CLK = "paid_clicks_g" if has_g else "clicks"          # Google-search clicks for the driver split
    CVK = "conversions_g" if has_g else "ad_conversions"  # Google-search conversions (CVR)
    for ce in ces:
        wk = ce.get("weekly") or []
        if not wk: continue
        w0 = wk[-1]; roi = w0.get(RK)
        spw = w0.get(SPK) or 0
        sp4 = sum((w.get(SPK) or 0) for w in wk[-4:])
        ne = _route(ce)
        ident = {"ce_id": ce["ce_id"], "ce_name": ce["ce_name"], "tier": _tier(ce),
                 "new_existing": ne, "spend_4w": round(sp4),
                 "orders_4w": round(sum((w.get("orders") or 0) for w in wk[-4:]))}
        # Evaluate spending CEs subject to the report materiality gate below.
        # Paused CEs and missing CM1 are data-validity cases, not flag criteria.
        if spw <= 0:
            if sp4 > 0: paused.append(ident)              # spent recently, stopped this week
            continue
        cm2s = [((w.get(CMK) or 0) - (w.get(SPK) or 0)) for w in wk]   # Google-search CM2
        # $1k/4wk materiality gate — REPORT VIEW ONLY (2026-08-08): sub-gate CEs that are
        # losing this week aggregate into the burn line; the ungated complete list is the
        # sheet export's job (spend_gate=0). Criteria semantics are unchanged either way.
        if spend_gate and sp4 <= spend_gate:
            if cm2s[-1] < 0:
                burn["count"] += 1; burn["bleed"] += cm2s[-1]
                burn["items"].append((ce["ce_name"], cm2s[-1]))
            continue
        cm2_w0 = cm2s[-1]; conv_w0 = w0.get(CVK)
        fired, d_wow, d_3w, cm2_90d, c1 = _lm_fired(wk, ne, SPK, CMK, RK, CVK)
        # tracking gap = CM1 genuinely missing (feed didn't populate) — NOT tiny-spend CEs
        # whose ROI is merely un-computed (< $50/wk floor); those evaluate with ROI shown "—"
        # so floorless C5 coverage is complete (2026-08-04).
        if not c1 and roi is None and w0.get(CMK) is None:
            tracking_gap.append(ident); continue
        if not fired: continue
        # label — a tag, not a grouping
        if c1:
            label = "full_waste"
        elif cm2_w0 < 0:
            w1_cm2 = cm2s[-2]
            improve = (100 * (cm2_w0 - w1_cm2) / abs(w1_cm2)) if w1_cm2 < 0 else None
            label = "recovering" if (improve is not None and improve >= LM_RECOVER_IMPROVE_PCT) else "bleeding"
        else:
            label = "eroding"
        # sort key: worst fired delta (C1 → the whole week's CM2 is the loss;
        # C4-only rows fall back to this week's CM2)
        cand = ([cm2_w0] if c1 else []) \
             + ([d_wow] if "C2" in fired else []) \
             + ([d_3w] if "C3" in fired else [])
        sort_delta = min(cand) if cand else cm2_w0
        # consecutive weeks flagged (this week = 1): re-run the criteria on progressively
        # truncated series; a week must have spend to count (criteria scope). Powers the
        # chronicity chip ("new this wk" / "Nth wk"). Capped at 8.
        streak = 1
        for back in range(1, min(8, len(wk))):
            seq = wk[:-back]
            if not seq or (seq[-1].get(SPK) or 0) <= 0: break
            if not _lm_fired(seq, ne, SPK, CMK, RK, CVK)[0]: break
            streak += 1
        flagged_lw = streak >= 2
        # raw weekly blocks W0..W3, NEWEST FIRST (rendered left→right in the report)
        ti = troas_now.get(_num_id(ce["ce_id"])) or {}
        troas_wk = ti.get("wk") or {}
        weeks = []
        for i in range(min(4, len(wk))):
            w = wk[-1 - i]
            clk = w.get(CLK); conv = w.get(CVK); sp = w.get(SPK) or 0; cm1 = w.get(CMK) or 0
            r = w.get(RK)
            weeks.append({"label": f"w{i}", "week": w.get("week"),
                          "cm2": round(cm1 - sp), "cm1": round(cm1), "spend": round(sp),
                          "clicks": clk,
                          "cvr": (round(100 * conv / clk, 2) if (conv is not None and clk) else None),
                          "cm1conv": (round(cm1 / conv, 2) if conv else None),  # avg CM1 (= value/conv)
                          "cpc": w.get(CPK),
                          "troas": troas_wk.get(str(w.get("week"))[:10]),  # spend-wtd target that week
                          "roi": (round(r) if r is not None else None)})
        # driver — reconciling CM2 decomposition vs the pooled W1..W3 baseline.
        # 4-factor when conversions are present: CM2 = clicks × (CVR × Val/conv − CPC);
        # else 3-factor Clicks · RPC · CPC (RPC = cm1/clicks). argmin of adverse moves.
        prior = wk[-4:-1]
        clk_w0 = w0.get(CLK)
        clk_pr = sum((x.get(CLK) or 0) for x in prior)
        conv_pr = sum((x.get(CVK) or 0) for x in prior)
        cm1_pr = sum((x.get(CMK) or 0) for x in prior)
        sp_pr = sum((x.get(SPK) or 0) for x in prior)
        clk_b = (clk_pr / len(prior)) if prior else None
        cpc_b = (sp_pr / clk_pr) if clk_pr else None
        cpc_c = (spw / clk_w0) if clk_w0 else None
        drivers, driver = {}, None
        if clk_b and clk_w0 and conv_pr and conv_w0 and cpc_b is not None and cpc_c is not None:
            cvr_b, cvr_c = conv_pr / clk_pr, conv_w0 / clk_w0            # conversions / click
            vpc_b, vpc_c = cm1_pr / conv_pr, (w0.get(CMK) or 0) / conv_w0  # cm1 per conversion
            _d = {"clicks":  (clk_w0 - clk_b) * (cvr_b * vpc_b - cpc_b),
                  "cvr":     clk_w0 * vpc_b * (cvr_c - cvr_b),
                  "valconv": clk_w0 * cvr_c * (vpc_c - vpc_b),
                  "cpc":    -clk_w0 * (cpc_c - cpc_b)}
        else:
            rpc_b = (cm1_pr / clk_pr) if clk_pr else None
            rpc_c = ((w0.get(CMK) or 0) / clk_w0) if clk_w0 else None
            _d = ({"clicks": (clk_w0 - clk_b) * (rpc_b - cpc_b),
                   "rpc":    clk_w0 * (rpc_c - rpc_b),
                   "cpc":   -clk_w0 * (cpc_c - cpc_b)}
                  if (clk_b and clk_w0 and rpc_b is not None and rpc_c is not None
                      and cpc_b is not None and cpc_c is not None) else None)
        if _d:
            drivers = {k: round(v) for k, v in _d.items()}
            _adv = {k: v for k, v in _d.items() if v < 0}
            driver = min(_adv, key=_adv.get) if _adv else None
        row = {**ident,
               "label": label, "criteria": fired,
               "flagged_lw": flagged_lw, "flag_streak": streak,
               "delta_wow": round(d_wow),
               "delta_3w": (round(d_3w) if d_3w is not None else None),
               "sort_delta": round(sort_delta),
               "cm2_wk": round(cm2_w0),
               "roi_wk": (round(roi) if roi is not None else None),
               "spend_wk": round(spw),
               "weeks": weeks,
               "cm2_series": [round(x) for x in cm2s[-12:]],
               "cm2_weeks": [w.get("week") for w in wk][-12:],
               "driver": driver, "drivers": drivers,
               "cm2_90d": cm2_90d}
        row["troas_l4w"] = ti.get("l4w")          # L4W avg (New-table sub-line; weekly in `weeks`)
        if ne == "New":
            li = launch.get(_num_id(ce["ce_id"])) or {}
            row["launch_date"] = li.get("date")
            row["days_since_launch"] = li.get("days")
            row["troas_now"] = ti.get("now")      # New column: target ROAS as of run date
        (new_rows if ne == "New" else existing).append(row)
    existing.sort(key=lambda r: r["sort_delta"])          # biggest drop first, label-agnostic
    new_rows.sort(key=lambda r: r["sort_delta"])
    paused.sort(key=lambda r: -r["spend_4w"]); tracking_gap.sort(key=lambda r: -r["spend_4w"])
    burn_names = [f"{n} ({round(v)})" for n, v in sorted(burn["items"], key=lambda x: x[1])]
    return {"existing": existing, "new": new_rows,
            "paused": paused, "tracking_gap": tracking_gap,
            "burn_line": {"count": burn["count"], "bleed_wk": round(burn["bleed"]), "names": burn_names}}


def seasonality(fluctuations, ces, cat_rpc, cat_cvr, flux_w0=None, lm_ce_ids=None):
    """Revenue-quality swings — RPC decomposed into its four multiplicative drivers so the
    reader sees WHICH one moved, not the composite.

      RPC = CVR × AOV × CR × TR   (exact identity, with CVR = orders/clicks)

    Qualifiers are upstream in alerts.py: both signals (CM1/conv + RPC) fire on the L3W-vs-W0
    pooled ratio (>=35%). Every row is L3W (the WoW side-paths were removed 2026-08-08), so
    `alert_type` is always "L3W" and all driver %Δ come from the l3w window.

    ROI gate (2026-08-03), on the W0 Google-Search ROI shown in each row's ROI cell:
    ROI is a graded READ, never a filter: `verdict` needs ROI > SEAS_UP (140) to print
    "+ve" (and < SEAS_DN (120) for "-ve"), so an unprofitable CE can never collect a
    "+15%, lean in" recommendation. An explicit ROI gate was tried and removed 2026-08-08 —
    it filtered 0-1 rows across 5 markets because a >=35% swing already moves ROI.

    Per row we surface: the four drivers (value + %Δ, `dominant` = the one explaining the
    move), always-on 28-day spend + pooled 28-day ROI, clicks as CONTEXT only (traffic is
    never a qualifier — Jul-17), and `weeks` = raw W0..W3 weekly blocks (spend · ROI · clicks ·
    CVR · CM1/conv · CPC, newest first) for the expanded Losing-Money-style display.
    """
    ce_by = {c["ce_id"]: c for c in ces}
    # 28d ROI + spend are the pause/scale decision metrics → Google-Search only where the split
    # columns exist (2026-07-17); business fallback on pre-split snapshots. Funnel drivers stay
    # total-business (the CVR = orders/clicks decomposition uses business clicks).
    has_g = any("spend_g" in (w or {}) for c in ces for w in (c.get("weekly") or []))
    # SPK/CMK feed the always-on 28-day ROI/spend context only; the per-week display blocks
    # come from alerts._week_blocks (daily-sourced, weekday-aligned).
    SPK, CMK = ("spend_g", "cm1_g") if has_g else ("spend", "cm1")
    def pctchg(now, prev):
        return round((now / prev - 1) * 100) if (now is not None and prev) else None
    LBL = {"cvr": "CVR", "aov": "AOV", "cr": "Completion", "tr": "Take rate"}   # paid RPC = CVR×AOV×CR×TR
    out = []
    for r in fluctuations:
        ce = ce_by.get(r["ce_id"])
        # No _active() check: measured across 3 markets it removed ZERO rows — the volume
        # floors upstream (W0 >= 10 · baseline >= 30 over 21d) already guarantee an active CE.
        if not ce: continue
        wk = ce.get("weekly") or []
        # Maturity lag: analyze the bucket on the matured week — drop any weekly entries after
        # flux_w0 so w0/wm1 and the 28d windows end on settled data (2026-07-20). No-op when
        # flux_w0 == report week (nothing to drop).
        if flux_w0:
            wk = [w for w in wk if (w.get("week") or "") <= flux_w0]
        w0 = wk[-1] if wk else {}
        wm1 = wk[-2] if len(wk) >= 2 else {}
        d = r.get("direction")
        # Early-warning dedup: a DOWN-swing already flagged by Losing Money is a cash loss
        # that has landed — not an early signal — so it belongs in that table, not here. Up
        # is untouched (Losing Money has no upside lane). Reads the LM output ce-id set.
        if d == "down" and lm_ce_ids and str(r["ce_id"]) in lm_ce_ids:
            continue
        # W0..W-3 blocks come from alerts._week_blocks — built off the daily series on
        # weekday-aligned, equal-length spans anchored to the ANALYSIS window, so the four
        # cells are comparable and W0 is the same window the swing was measured on.
        weeks = r.get("weeks") or []
        # Dollar floor: enough spend on the CE this week for a recommendation to be worth a
        # reader's time. The order floor upstream (>=10) lets $79-CEs through; "+15%/7d" on
        # $79 is noise. Guards against the small-spend tail (~8-12% of rows). Set 0 to disable.
        import config
        _min_sp = getattr(config, "FLUCTUATION_MIN_SPEND_W0", 0)
        if _min_sp and ((weeks[0].get("spend") if weeks else 0) or 0) < _min_sp:
            continue
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
        # Every row qualifies on the L3W window, so the driver %Δ are read from there.
        alert_type = "L3W"
        drv = (r.get("drivers") or {}).get("l3w") or {}
        vals = {}
        for k, aspct in (("cvr", True), ("aov", False), ("cr", True), ("tr", True)):  # CVR/CR/TR as %, AOV as $
            v = (drv.get(k) or {}).get("v")
            vals[k] = (round(v * 100, 2) if (v is not None and aspct) else (round(v, 2) if v is not None else None))
            vals[k + "_d"] = (drv.get(k) or {}).get("pct")
        # dominant = the driver whose move best explains the alert direction
        moves = {k: vals[k + "_d"] for k in ("cvr", "aov", "cr", "tr") if vals.get(k + "_d") is not None}
        aligned = {k: v for k, v in moves.items() if v != 0 and (v < 0) == (d == "down")}
        pool = aligned or moves
        dom = max(pool, key=lambda k: abs(pool[k])) if pool else None
        # NOTE: the Step-3 driver gate was REMOVED (2026-08-10). It dropped ~0.5 rows/market-week
        # and, on inspection, those weren't noise — they were BROAD-BASED moves (all four drivers
        # aligned, none individually ≥30% but compounding to a 35-52% RPC swing, e.g. Sydney Whale
        # Watching +52%). The gate assumed a real move concentrates in one driver and killed the
        # distributed ones, which are the cleanest signals. Redundant anyway: RPC = CVR×AOV×CR×TR,
        # so a 35% RPC move already guarantees the drivers moved. `dominant` is still surfaced.
        pc = w0.get("paid_contribution_pct")
        cause = r.get("cause_tag")
        # ROI gate — the W0 Google-Search ROI over the ANALYSIS window, i.e. exactly the
        # number rendered in the row's ROI cell, so the gate is auditable from the table.
        # Only falls back to the report-week series when the aligned blocks are ABSENT
        # (pre-split cached snapshot); a present-but-null ROI is a deliberate validity
        # gate (spend under the floor / out-of-range) and must stay null.
        if weeks:
            roi_w0 = weeks[0].get("roi")
        else:
            roi_w0 = w0.get("roi_g") if has_g else w0.get("roi_pct")
        # No ROI *gate*. Measured across 5 markets it removed 0-1 rows: a >=35% drop
        # mechanically pulls current-week ROI down, so "dropped hard AND still >180%" is
        # very nearly an empty set (same story at 100% on the up side). The protection it
        # was meant to give — never say "+15%, lean in" on an unprofitable CE — is already
        # delivered by the VERDICT below, which needs ROI > SEAS_UP (140) to print "+ve".
        # ROI stays a graded read, not a filter.
        if d == "down":
            verdict = "-ve" if (roi_w0 is not None and roi_w0 < SEAS_DN) else "watch"
        else:
            verdict = "+ve" if (roi_w0 is not None and roi_w0 > SEAS_UP) else "watch"
        # innocence-cascade-aware recommendation: unexplained down = investigate
        if pc is not None and pc < LOW_PAID_PCT:      rec = "review — low paid"
        elif cause == "input-induced":                rec = "verify (bid change)"
        elif cause == "supply-linked":                rec = "route Ops (supply)"
        elif verdict == "+ve":                        rec = "+15%/7d"
        elif verdict == "-ve":                        rec = "investigate"   # every -ve reaching here is unexplained
        else:                                         rec = "monitor"
        out.append({
            "ce_id": r["ce_id"], "ce_name": r["ce_name"],
            "signal": r.get("signal"),
            "sustained": r.get("sustained", False),   # True = 2nd week running (confirmed trend chip)
            "direction": d, "group": ("Compound" if d == "up" else "Defend"),
            "alert_type": alert_type, "swing_pct": r.get("magnitude_pct"),
            "roi_4w": roi_4w, "spend_4w": round(spend_4w) if spend_4w else None,
            "roi_4w_d": roi_4w_d, "spend_4w_d": spend_4w_d,
            "cvr": vals["cvr"], "cvr_d": vals["cvr_d"], "aov": vals["aov"], "aov_d": vals["aov_d"],
            "cr": vals["cr"], "cr_d": vals["cr_d"], "tr": vals["tr"], "tr_d": vals["tr_d"],
            "clicks": w0.get("paid_clicks_g", w0.get("clicks")),
            "clicks_d": pctchg(w0.get("paid_clicks_g", w0.get("clicks")), wm1.get("paid_clicks_g", wm1.get("clicks"))),
            "dominant": LBL.get(dom), "dominant_key": dom,
            "verdict": verdict, "cause": cause, "paid_pct": pc, "recommendation": rec,
            "roi_w0": roi_w0,          # the gated value (Google-Search W0 ROI)
            "weeks": weeks,
        })
    # Sort by W0 Google spend, biggest bets first. The swing % is no longer rendered, so
    # sorting on it would order the table by an invisible field; spend is in the table.
    out.sort(key=lambda r: -((r.get("weeks") or [{}])[0].get("spend") or 0))
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
            "mo_since_launch": (launch_map.get(_num_id(ce["ce_id"])) or {}).get("months"),
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
            "mo_since_launch": (launch_map.get(_num_id(cid)) or {}).get("months"),
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
    """{numeric_ce_id: {"date": iso, "days": n, "months": n}}. Guarded CE-age proxy.

    First paid Google-Ads click (ads_campaign_stats, Google Ads only, earliest
    report_date with clicks>0) = the oldest campaign launch date per CE. NOT the
    Headout launch/creation date — understates true age for CEs that ran on Bing
    or grew organically first. `months` matches the monthly notebook's "Mo since
    launch"; `date`/`days` feed the Losing Money New-CE columns. {} on any failure.
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
                days = max(0, (ws - d).days)
                out[str(r["ce_id"])] = {"date": d.isoformat(), "days": days,
                                        "months": round(days / 30.44)}
            except Exception:
                continue
        return out
    except Exception as e:
        print(f"[buckets] WARNING: launch-date fetch failed ({e!r}); "
              f"New CEs 'Mo since launch' will be blank.")
        return {}


def _troas_now_map(snap):
    """{numeric_ce_id: {"now": current tROAS %, "l4w": L4W avg %, "wk": {week_iso: %}}}.

    Spend-weighted across the CE's Search campaigns; "wk" is PER REPORT WEEK over the
    L4W window (campaign_target_roas as-of-each-date) so the table can show the target
    week by week — a tROAS step-down in w1 explains a CM2 drop. "now" =
    current_campaign_target_roas (as-of-run value, constant across dates); "l4w" =
    spend-weighted avg of the weekly values. Google Ads Search only. {} on any failure.
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
               DATE_TRUNC(report_date, {config.BQ_WEEK})          AS week,
               SUM(sum_spend)                                      AS spend,
               SAFE_DIVIDE(SUM(campaign_target_roas * sum_spend),
                           SUM(IF(campaign_target_roas IS NOT NULL, sum_spend, NULL))) AS troas_wk,
               SAFE_DIVIDE(SUM(current_campaign_target_roas * sum_spend),
                           SUM(IF(current_campaign_target_roas IS NOT NULL, sum_spend, NULL))) AS troas_now
        FROM {config.ADS_STATS}
        WHERE ad_platform = 'Google Ads'
              AND campaign_advertising_channel_type = 'SEARCH'
              AND report_date BETWEEN DATE_SUB(DATE(@week), INTERVAL 21 DAY)
                                  AND DATE_ADD(DATE(@week), INTERVAL 6 DAY)
              AND CAST(campaign_target_combined_entity_id AS STRING) IN UNNEST(@ids)
        GROUP BY 1, 2
        """
        df = query_df(sql, "troas_now", {"week": config.iso(ws), "ids": ids})
        def _v(x): return round(float(x), 1) if (x is not None and float(x) > 0) else None
        out = {}
        for _, r in df.iterrows():
            cid = str(r["ce_id"])
            d = out.setdefault(cid, {"now": None, "l4w": None, "wk": {}, "_w": []})
            v = _v(r["troas_wk"]); sp = float(r["spend"] or 0)
            d["wk"][str(r["week"])[:10]] = v
            if v is not None and sp > 0: d["_w"].append((v, sp))
            n = _v(r["troas_now"])
            if n is not None: d["now"] = n
        for d in out.values():
            tot = sum(sp for _, sp in d["_w"])
            d["l4w"] = round(sum(v * sp for v, sp in d["_w"]) / tot, 1) if tot else None
            del d["_w"]
        return out
    except Exception as e:
        print(f"[buckets] WARNING: tROAS fetch failed ({e!r}); "
              f"Losing Money tROAS columns will be blank.")
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
    troas = {r["ce_id"]: r.get("troas_target_pct") for r in _rows(snap.get("bucket_b1"))}
    fl = _rows(snap.get("bucket1_fluctuations"))
    mw = snap.get("market_summary", {}).get("weekly", [])
    cat_rpc, cat_cvr = _cat_benchmarks(ces)
    # Fluctuations drivers/qualifiers run on the matured PORTION of the report week (upstream in
    # alerts.py). The 28d ROI/spend CONTEXT columns here use the last full matured week so they
    # aren't contaminated by the unsettled current week (2026-07-20).
    # Anchor the weekly-context columns (paid-contribution %, 28d ROI/spend) on the week the
    # bucket actually ANALYSED, so they describe the same week as every metric beside them.
    # Previously this passed fluctuation_context_week (the last fully-settled week), which
    # after the full-week switch resolved to W-1 — the low-paid branch was reading last week.
    flux_win = ((snap.get("meta") or {}).get("fluctuation_window_start")
                or (snap.get("meta") or {}).get("week_start"))
    mmp = _mmp_map(snap)
    prior_pp = _prior_proplus_map(snap)
    launch = _launch_map(snap)
    troas_now = _troas_now_map(snap)
    # Losing Money first, so its flagged set can suppress duplicate down-swings in Fluctuations.
    # A CE already in the cash bucket isn't an EARLY warning — it's the same finding, later.
    # We read the OUTPUT ce-ids (existing + new), never the criteria, so this is agnostic to
    # future changes to Losing Money criteria.
    lm = losing_money(ces, troas_now, launch, prior_pp)
    lm_flagged = {str(r["ce_id"]) for r in (lm.get("existing") or []) + (lm.get("new") or [])}
    seas = seasonality(fl, ces, cat_rpc, cat_cvr, flux_w0=flux_win, lm_ce_ids=lm_flagged)
    return {
        "defend": {"losing_money": lm,
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
    print("== DEFEND · Losing Money v2 ==")
    print(f"  existing {len(lm['existing'])} · new {len(lm['new'])} · "
          f"paused {len(lm['paused'])} · tracking-gap {len(lm['tracking_gap'])}")
    for r in (lm["existing"][:6] + lm["new"][:4]):
        print(f"    {r['ce_name'][:24]:24s} {r['new_existing'][:3]:3s} {r['label']:10s} "
              f"{'+'.join(r['criteria']):9s} Δ${r['sort_delta']:>6} · CM2 ${r['cm2_wk']:>6} · "
              f"ROI {r['roi_wk'] if r['roi_wk'] is not None else '—':>4} · drv {r['driver'] or '—'}")
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
