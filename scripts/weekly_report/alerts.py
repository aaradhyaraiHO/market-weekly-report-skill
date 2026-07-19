"""
Fluctuation engine (Bucket 1) port.

Reproduces the POF alert engine from the NA validation run:
  * CM1/conv daily swings — 28d baseline (excl. last 3d, >=14 valid days),
    >=20% deviation vs baseline, +-25% same-day-last-week, CV<=0.50,
    >=10 conv/day, >=500 clicks/35d, 3-day persistence >=15%.
  * RPC daily swings — same gates, orders as the volume gate.
  * CVR drop > 30% WoW (>=300 clicks/wk floor).
Plus a bid-change innocence check (historized campaign tROAS diffs) and an
optional availability evidence join.

Hard validation gate: on NA week 2026-06-29 the CM1/conv engine must surface
exactly 5 up-swing CEs (High Roller, Edge NYC, Universal Studios Hollywood,
AMNH, Arte Museum NY) with 0 CV-excluded.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

import config

POF = config.POF


# --------------------------------------------------------------------------- #
# Generic daily POF alert over a ratio series
# --------------------------------------------------------------------------- #
def _ratio_alert(
    daily: pd.DataFrame,
    ce_id: str,
    value_col: str,
    denom_col: str,
    volume_col: str,
    week_days: list[dt.date],
) -> dict | None:
    """
    Evaluate one CE's daily ratio (value_col / denom_col) for a POF swing over
    the W0 week. Returns an alert dict, {"cv_excluded": True}, or None.

    volume_col is the per-day volume gate column (conversions for CM1/conv,
    orders for RPC).
    """
    d = daily[daily["combined_entity_id"] == ce_id].copy()
    if d.empty:
        return None
    d = d.set_index("report_date").sort_index()
    # Reindex to a continuous daily calendar so d-7 / rolling windows are correct.
    full_idx = pd.date_range(d.index.min(), d.index.max(), freq="D").date
    d = d.reindex(full_idx)
    for col in (value_col, denom_col, volume_col, "clicks"):
        if col in d:
            d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0.0)

    ratio = d[value_col] / d[denom_col].replace(0, np.nan)

    cfg = POF
    excl = cfg["baseline_excl_last_days"]
    win = cfg["baseline_window_days"]

    best = None            # strongest qualifying day
    persistence_days = 0
    cv_excluded_any = False

    idx = list(d.index)
    pos = {day: i for i, day in enumerate(idx)}

    for day in week_days:
        if day not in pos:
            continue
        i = pos[day]
        # Baseline window [d-31, d-4] on conversion/volume-positive days.
        base_lo = day - dt.timedelta(days=excl + win)      # d-31
        base_hi = day - dt.timedelta(days=excl + 1)        # d-4
        base_mask = [(x >= base_lo) and (x <= base_hi) for x in idx]
        base_ratio = ratio[base_mask]
        base_ratio = base_ratio[base_ratio.notna()]
        if len(base_ratio) < cfg["baseline_min_valid_days"]:
            continue
        base_mean = float(base_ratio.mean())
        if base_mean == 0:
            continue
        base_std = float(base_ratio.std(ddof=1))
        cv = base_std / base_mean if base_mean else np.inf

        r_now = ratio.iloc[i]
        if pd.isna(r_now):
            continue
        dev = (r_now - base_mean) / base_mean

        # Persistence: count W0 days where |dev vs this-day baseline| >= 15%.
        if abs(dev) >= cfg["persistence_threshold"]:
            persistence_days += 1

        # CV gate — exclude the CE if a would-be-alert day has a noisy baseline.
        cv_ok = cv <= cfg["cv_max"]

        # Same-day-last-week and 7d-rolling WoW.
        r_prev7 = ratio.iloc[i - 7] if i - 7 >= 0 else np.nan
        sdlw = (r_now / r_prev7 - 1) if (pd.notna(r_prev7) and r_prev7) else np.nan
        roll_now = ratio.iloc[max(0, i - 6): i + 1].mean()
        roll_prev = ratio.iloc[max(0, i - 13): i - 6].mean() if i - 6 > 0 else np.nan
        roll_wow = (roll_now / roll_prev - 1) if (pd.notna(roll_prev) and roll_prev) else np.nan

        # Volume gates.
        conv_ok = float(d[volume_col].iloc[i]) >= cfg["min_conv_per_day"]
        clk_lo = day - dt.timedelta(days=34)
        clk_mask = [(x >= clk_lo) and (x <= day) for x in idx]
        clicks35 = float(d["clicks"][clk_mask].sum())
        clicks_ok = clicks35 >= cfg["min_clicks_35d"]

        # 3-day smoothed deviation (persistence): the swing must hold, not spike.
        smoothed = ratio.iloc[max(0, i - 2): i + 1].mean()
        sm_dev = (smoothed - base_mean) / base_mean if base_mean else np.nan
        persist_ok = pd.notna(sm_dev) and abs(sm_dev) >= cfg["persistence_smoothed_dev"] \
            and (sm_dev > 0) == (dev > 0)   # smoothed swing in the same direction

        dev_ok = abs(dev) >= cfg["baseline_dev_threshold"]
        short_ok = (pd.notna(sdlw) and abs(sdlw) >= cfg["sdlw_threshold"]) or (
            pd.notna(roll_wow) and abs(roll_wow) >= cfg["roll7_wow_threshold"]
        )

        qualifies = dev_ok and short_ok and conv_ok and clicks_ok and persist_ok
        if qualifies and not cv_ok:
            cv_excluded_any = True
            continue
        if not qualifies:
            continue

        cand = {
            "day": day,
            "value_now": round(float(r_now), 4),
            "baseline": round(base_mean, 4),
            "dev": round(float(dev), 4),
            "sdlw_pct": None if pd.isna(sdlw) else round(float(sdlw) * 100, 1),
            "wow_pct": None if pd.isna(roll_wow) else round(float(roll_wow) * 100, 1),
            "cv": round(float(cv), 3),
            "clicks_35d": int(clicks35),
        }
        if best is None or abs(cand["dev"]) > abs(best["dev"]):
            best = cand

    if best is None:
        return {"cv_excluded": True} if cv_excluded_any else None

    best["persistence_days"] = persistence_days
    best["direction"] = "up" if best["dev"] > 0 else "down"
    best["magnitude_pct"] = round(best["dev"] * 100, 1)
    return best


# --------------------------------------------------------------------------- #
# Bid-change innocence check
# --------------------------------------------------------------------------- #
def bid_changes(troas: pd.DataFrame, w0_start: dt.date) -> dict[str, dict]:
    """
    Detect campaign-level as-of tROAS changes per CE in the lookback window.
    Returns {ce_id: {"changed": True, "detail": "...", "campaigns": n}}.
    """
    out: dict[str, dict] = {}
    if troas is None or troas.empty:
        return out
    t = troas.copy()
    t["troas"] = pd.to_numeric(t["troas"], errors="coerce")
    lo = w0_start - dt.timedelta(days=config.TROAS_LOOKBACK_DAYS)
    for ce_id, g in t.groupby("combined_entity_id"):
        details = []
        n_campaigns = 0
        for _, cg in g.groupby("campaign_id"):
            cg = cg.dropna(subset=["troas"]).sort_values("report_date")
            cg = cg[(cg["report_date"] >= lo)]
            if cg["troas"].nunique() <= 1:
                continue
            vals = cg["troas"].tolist()
            first, last = vals[0], vals[-1]
            if first == last:
                continue
            # Date of the first change.
            chg_date = None
            prev = vals[0]
            for _, row in cg.iterrows():
                if row["troas"] != prev:
                    chg_date = row["report_date"]
                    break
                prev = row["troas"]
            n_campaigns += 1
            details.append(f"{first:.0f}->{last:.0f}"
                           + (f" {chg_date}" if chg_date is not None else ""))
        if n_campaigns:
            out[str(ce_id)] = {
                "changed": True,
                "campaigns": n_campaigns,
                "detail": "tROAS " + "; ".join(sorted(set(details))[:4]),
            }
    return out


# --------------------------------------------------------------------------- #
# CVR WoW drop signal (weekly)
# --------------------------------------------------------------------------- #
def cvr_drops(ce_paid: pd.DataFrame, w0: dt.date, wm1: dt.date) -> dict[str, dict]:
    """CEs whose GOOGLE-SEARCH PAID CVR fell > 30% WoW with >= 300 Google-search clicks in W0.
    CVR = Google-Search paid conversions ÷ Google-Search paid clicks (2026-07-17: decisions are
    Google-Search only; ad-conversions incl. Bing / business orders are the wrong basis)."""
    out: dict[str, dict] = {}
    w0_rows = ce_paid[ce_paid["week"] == w0].set_index("combined_entity_id")
    wm1_rows = ce_paid[ce_paid["week"] == wm1].set_index("combined_entity_id")
    for ce_id, r in w0_rows.iterrows():
        clicks0 = float(r.get("paid_clicks_g") or 0)
        if clicks0 < config.CVR_MIN_CLICKS_WK:
            continue
        conv0 = float(r.get("conversions_g") or 0)
        cvr0 = conv0 / clicks0 if clicks0 else np.nan
        if ce_id not in wm1_rows.index:
            continue
        rp = wm1_rows.loc[ce_id]
        clicks1 = float(rp.get("paid_clicks_g") or 0)
        conv1 = float(rp.get("conversions_g") or 0)
        cvr1 = conv1 / clicks1 if clicks1 else np.nan
        if not (cvr1 and cvr1 > 0) or pd.isna(cvr0):
            continue
        wow = cvr0 / cvr1 - 1
        if wow <= -config.CVR_WOW_DROP_THRESHOLD:
            out[str(ce_id)] = {
                "value_now": round(cvr0 * 100, 2),
                "baseline": round(cvr1 * 100, 2),
                "wow_pct": round(wow * 100, 1),
                "clicks_wk": int(clicks0),
            }
    return out


def cvr_gray_zone(ce_paid: pd.DataFrame, w0: dt.date, wm1: dt.date) -> int:
    """Near-miss CVR WoW drops (within GRAY_ZONE_PP of the 30% trigger). Google-Search paid CVR,
    same >= 300 Google-search-click floor as cvr_drops."""
    lo = config.CVR_WOW_DROP_THRESHOLD - config.GRAY_ZONE_PP / 100.0
    hi = config.CVR_WOW_DROP_THRESHOLD
    n = 0
    w0_rows = ce_paid[ce_paid["week"] == w0].set_index("combined_entity_id")
    wm1_rows = ce_paid[ce_paid["week"] == wm1].set_index("combined_entity_id")
    for ce_id, r in w0_rows.iterrows():
        clicks0 = float(r.get("paid_clicks_g") or 0)
        if clicks0 < config.CVR_MIN_CLICKS_WK or ce_id not in wm1_rows.index:
            continue
        conv0 = float(r.get("conversions_g") or 0)
        cvr0 = conv0 / clicks0 if clicks0 else np.nan
        rp = wm1_rows.loc[ce_id]
        clicks1 = float(rp.get("paid_clicks_g") or 0)
        conv1 = float(rp.get("conversions_g") or 0)
        cvr1 = conv1 / clicks1 if clicks1 else np.nan
        if not (cvr1 and cvr1 > 0) or pd.isna(cvr0):
            continue
        drop = -(cvr0 / cvr1 - 1)   # positive = a drop
        if lo <= drop < hi:
            n += 1
    return n


# --------------------------------------------------------------------------- #
# B2 column helpers (spec §5 B2 — swing driver + daily spark)
# --------------------------------------------------------------------------- #
_SHAP_LABELS = {"traffic": "Traffic", "cvr": "CVR", "aov": "AOV", "cr": "Completion", "tr": "Take rate"}


def _swing_driver(shap: dict | None) -> dict | None:
    """Top-1 driver of the swing from the per-CE WoW Shapley (mechanical, no LLM
    — the Blue Grotto template). Returns {factor, label, value, share_pct}."""
    if not shap:
        return None
    factors = {k: shap[k] for k in ("traffic", "cvr", "aov", "cr", "tr") if shap.get(k) is not None}
    if not factors:
        return None
    total_abs = sum(abs(v) for v in factors.values()) or 1.0
    top = max(factors, key=lambda k: abs(factors[k]))
    return {
        "factor": top,
        "label": _SHAP_LABELS.get(top, top),
        "value": round(float(factors[top]), 2),
        "share_pct": round(100.0 * abs(factors[top]) / total_abs, 0),
    }


def _driver_windows(df: pd.DataFrame, ce_id: str, week_days: list[dt.date]) -> dict | None:
    """Paid GOOGLE-SEARCH RPC drivers, POOLED (Σ/Σ) so they reconcile to paid RPC exactly:
        RPC = CVR × AOV × Take-rate   (CVR=conv/clicks · AOV=gbv/conv · TR=rev/gbv)
    Completion is dropped — not sane on paid attribution (completed/booked > 100%). Returns
    {'wow': {...}, '3d': {...}}: WoW = W0 week vs prior week; 3D = last 3 days vs 28-day baseline
    (excl last 3). Each metric → {v, pct}. (2026-07-19: all paid Google-Search.)"""
    d = df[df["combined_entity_id"].astype(str) == str(ce_id)].copy()
    if d.empty:
        return None
    d = d.set_index("report_date").sort_index()
    idx = pd.date_range(d.index.min(), d.index.max(), freq="D").date
    d = d.reindex(idx)
    for c in ("revenue", "gbv", "clicks", "conversions"):
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0.0)
    present = set(d.index)
    days = [x for x in week_days if x in present]
    if not days:
        return None
    last = max(days)
    def _sum(col, lo, hi):
        return float(d[col][[(lo <= x <= hi) for x in d.index]].sum()) if col in d else 0.0
    def _drivers(lo, hi):
        clk, conv = _sum("clicks", lo, hi), _sum("conversions", lo, hi)
        gbv, rev = _sum("gbv", lo, hi), _sum("revenue", lo, hi)
        return {"cvr": (conv / clk) if clk else None,
                "aov": (gbv / conv) if conv else None,
                "tr":  (rev / gbv) if gbv else None}
    def _pack(now, prev):
        out = {}
        for k in ("cvr", "aov", "tr"):
            n, p = now.get(k), prev.get(k)
            out[k] = {"v": None if n is None else round(n, 4),
                      "pct": (round((n / p - 1) * 100) if (n is not None and p) else None)}
        return out
    wow = _pack(_drivers(last - dt.timedelta(days=6), last),
                _drivers(last - dt.timedelta(days=13), last - dt.timedelta(days=7)))
    d3 = _pack(_drivers(last - dt.timedelta(days=2), last),
               _drivers(last - dt.timedelta(days=31), last - dt.timedelta(days=4)))
    return {"wow": wow, "3d": d3}


def _daily_spark(df: pd.DataFrame, ce_id: str, num: str, den: str, days: int = 35) -> list:
    """Last `days` of a daily ratio (e.g. CM1/conv) for the B2 sparkline. None on
    zero-denominator days (null = gap, never zero — monthly-v3 convention)."""
    sub = df[df["combined_entity_id"].astype(str) == ce_id].sort_values("report_date").tail(days)
    out = []
    for _, r in sub.iterrows():
        d = float(r.get(den) or 0)
        out.append(round(float(r.get(num) or 0) / d, 4) if d else None)
    return out


# Orchestrator: build bucket1_fluctuations rows
# --------------------------------------------------------------------------- #
def build_bucket1(
    *,
    ce_daily_ads: pd.DataFrame,
    ce_daily_business: pd.DataFrame,
    ce_daily_paid_google: pd.DataFrame | None = None,
    ce_weekly: pd.DataFrame,
    ce_weekly_paid: pd.DataFrame,
    names: dict[str, str],
    paid_contrib: dict[str, float],
    troas: pd.DataFrame,
    w0_start: dt.date,
    wm1_start: dt.date,
    week_days: list[dt.date],
    availability_fetcher=None,
    shapley_by_ce: dict | None = None,
) -> tuple[list[dict], dict]:
    """
    Returns (bucket1_rows, diagnostics). diagnostics carries the CM1/conv alert
    CE names + cv_excluded count for validation.
    """
    ce_ids = sorted(set(ce_daily_ads["combined_entity_id"].dropna().astype(str)))

    cm1_alerts: dict[str, dict] = {}
    rpc_alerts: dict[str, dict] = {}
    cv_excluded: list[str] = []

    for ce_id in ce_ids:
        res = _ratio_alert(ce_daily_ads, ce_id, "cm1", "conversions", "conversions", week_days)
        if res is None:
            pass
        elif res.get("cv_excluded"):
            cv_excluded.append(ce_id)
        else:
            cm1_alerts[ce_id] = res

    # RPC engine — Google-Search PAID daily series (paid revenue ÷ paid clicks), not total
    # business revenue: an RPC drop should be a Google-Search paid problem (2026-07-17).
    rpc_src = ce_daily_paid_google if ce_daily_paid_google is not None else ce_daily_business
    rpc_ids = sorted(set(rpc_src["combined_entity_id"].dropna().astype(str)))
    for ce_id in rpc_ids:
        res = _ratio_alert(rpc_src, ce_id, "revenue", "clicks", "conversions", week_days)
        if res and not res.get("cv_excluded"):
            rpc_alerts[ce_id] = res

    cvr_alerts = cvr_drops(ce_weekly_paid, w0_start, wm1_start)     # Google-Search paid CVR
    cvr_gray = cvr_gray_zone(ce_weekly_paid, w0_start, wm1_start)
    bid = bid_changes(troas, w0_start)

    # Weekly W0 spend/revenue lookups.
    paid_w0 = ce_weekly_paid[ce_weekly_paid["week"] == w0_start].set_index("combined_entity_id")
    biz_w0 = ce_weekly[ce_weekly["week"] == w0_start].set_index("combined_entity_id")

    # Availability enrichment for the union of flagged CEs.
    flagged = set(cm1_alerts) | set(rpc_alerts) | set(cvr_alerts)
    avail_map: dict[str, dict] = {}
    if availability_fetcher and flagged:
        av = availability_fetcher(sorted(flagged))
        if av is not None and not av.empty:
            for _, r in av.iterrows():
                avail_map[str(r["combined_entity_id"])] = {
                    "soldout_w0": None if pd.isna(r["soldout_w0"]) else round(float(r["soldout_w0"]), 3),
                    "soldout_baseline": None if pd.isna(r["soldout_baseline"]) else round(float(r["soldout_baseline"]), 3),
                }

    def _spend(ce_id):
        return round(float(paid_w0.loc[ce_id]["spend"]), 0) if ce_id in paid_w0.index else None

    def _rev(ce_id):
        return round(float(biz_w0.loc[ce_id]["revenue"]), 0) if ce_id in biz_w0.index else None

    def _reco(direction: str, ce_id: str) -> str:
        pc = paid_contrib.get(ce_id)
        if pc is not None and pc < config.PAID_CONTRIB_LOW_PCT:
            return f"review — low paid ({pc:.0f}% paid-contribution)"
        base = ("+" if direction == "up" else "-") + f"{config.SEASONALITY_ADJ_PCT*100:.0f}% / 7d seasonality adjustment"
        if ce_id in bid:
            return f"{base} — but input-induced ({bid[ce_id]['detail']}); verify before adjusting"
        return base

    shapley_by_ce = shapley_by_ce or {}

    def _cause_tag(ce_id, direction):
        """Innocence-check routing (spec §5 B2): each hit re-routes away from the
        UNEXPLAINED tag — the only rows where 'investigate' means nobody knows.
        Order: bid change -> supply break -> (TR/price steps deferred) -> unexplained."""
        if ce_id in bid:
            return "input-induced"
        av = avail_map.get(ce_id)
        if av and av.get("soldout_w0") is not None:
            base = av.get("soldout_baseline")
            # W0 sold-out materially above its baseline => supply-linked, route to Ops
            if av["soldout_w0"] >= 0.20 and (base is None or av["soldout_w0"] > (base or 0) + 0.10):
                return "supply-linked"
        return "unexplained" if direction == "down" else "up-swing"

    rows: list[dict] = []

    def _emit(ce_id, signal, res, window, evidence_extra=None):
        ev = {
            "value_now": res.get("value_now"),
            "baseline": res.get("baseline"),
            "sdlw_pct": res.get("sdlw_pct"),
            "wow_pct": res.get("wow_pct"),
            "persistence_days": res.get("persistence_days"),
            "cv": res.get("cv"),
        }
        if evidence_extra:
            ev.update(evidence_extra)
        if ce_id in bid:
            ev["bid_change"] = bid[ce_id]["detail"]
        if ce_id in avail_map:
            ev["availability"] = avail_map[ce_id]
        # daily CM1/conv spark + 28d baseline band (only the daily bucket gets a daily spark)
        if signal == "cm1_per_conv":
            ev["spark_daily"] = _daily_spark(ce_daily_ads, ce_id, "cm1", "conversions")
            ev["spark_baseline"] = res.get("baseline")
        rows.append({
            "ce_id": ce_id,
            "ce_name": names.get(ce_id, ce_id),
            "signal": signal,
            "direction": res["direction"],
            "magnitude_pct": res["magnitude_pct"],
            "window": window,
            "cause_tag": _cause_tag(ce_id, res["direction"]),
            "swing_driver": _swing_driver(shapley_by_ce.get(ce_id)),
            # paid Google-Search RPC-driver breakdown (CVR·AOV·Take-rate), WoW + 3D windows
            "drivers": (_driver_windows(ce_daily_paid_google, ce_id, week_days)
                        if ce_daily_paid_google is not None else None),
            "evidence": ev,
            "paid_contribution_pct": paid_contrib.get(ce_id),
            "spend_wk": _spend(ce_id),
            "revenue_wk": _rev(ce_id),
            "recommendation": _reco(res["direction"], ce_id),
        })

    for ce_id, res in cm1_alerts.items():
        window = "sustained_3d" if res.get("persistence_days", 0) >= 3 else "sdlw"
        _emit(ce_id, "cm1_per_conv", res, window)
    for ce_id, res in rpc_alerts.items():
        if ce_id in cm1_alerts:
            continue  # CM1/conv is the primary home; avoid double-listing
        window = "sustained_3d" if res.get("persistence_days", 0) >= 3 else "sdlw"
        _emit(ce_id, "rpc", res, window)
    for ce_id, res in cvr_alerts.items():
        if ce_id in cm1_alerts or ce_id in rpc_alerts:
            continue
        synth = {
            "direction": "down",
            "magnitude_pct": res["wow_pct"],
            "value_now": res["value_now"],
            "baseline": res["baseline"],
            "sdlw_pct": None,
            "wow_pct": res["wow_pct"],
            "persistence_days": None,
            "cv": None,
        }
        _emit(ce_id, "cvr", synth, "wow", {"clicks_wk": res["clicks_wk"]})

    # Sort: down-swings first (risk), then by |magnitude| desc.
    rows.sort(key=lambda r: (r["direction"] != "down", -abs(r["magnitude_pct"] or 0)))

    diagnostics = {
        "cm1_conv_alert_ces": sorted(names.get(c, c) for c in cm1_alerts),
        "cm1_conv_alert_count": len(cm1_alerts),
        "cm1_conv_directions": {names.get(c, c): cm1_alerts[c]["direction"] for c in cm1_alerts},
        "rpc_alert_count": len(rpc_alerts),
        "cvr_alert_count": len(cvr_alerts),
        "cv_excluded_count": len(cv_excluded),
        "cv_excluded_ces": sorted(names.get(c, c) for c in cv_excluded),
        "cvr_gray_zone_count": cvr_gray,   # P2.3: near-miss CVR drops (just short of 30%)
    }
    return rows, diagnostics
