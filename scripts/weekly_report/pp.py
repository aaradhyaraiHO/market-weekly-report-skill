"""PP tracking bucket — dim_pp_allotments (STR/liability) joined to the CE weekly
funnel (CVR, CM2, orders). Metrics only, no verdict (reviewer decides).

Scope: the CURRENT prepurchase season (config.PP_SEASON_START), NOT a window
relative to the report week — allotments created months ago can still be selling
or carrying liability now, so a rolling window would wrongly drop live inventory.
"""
from __future__ import annotations
import math
import config
from bq import query_df

PP_SQL = """
WITH pp AS (
  SELECT tour_id,
         SUM(count_uploaded_tickets) uploaded, SUM(count_sold_tickets) sold,
         SUM(loss_liability_usd) loss_liab, MAX(DATE(latest_ticket_uploaded_at)) last_upload
  FROM `{proj}.{ds}.dim_pp_allotments`
  WHERE DATE(allotment_created_at) >= DATE(@season_start) AND count_uploaded_tickets > 0
  GROUP BY 1),
map AS (SELECT DISTINCT tour_id, combined_entity_id
        FROM `{proj}.{ds}.dim_experience_listings` WHERE tour_id IS NOT NULL),
cem AS (SELECT combined_entity_id, ANY_VALUE(business_market) market, ANY_VALUE(combined_entity_name) ce
        FROM `{proj}.{ds}.dim_experiences` GROUP BY 1)
SELECT cem.market, cem.combined_entity_id AS ce_id, cem.ce,
       SUM(pp.uploaded) uploaded, SUM(pp.sold) sold,
       ROUND(SUM(pp.loss_liab),0) loss_liab, MAX(pp.last_upload) last_upload
FROM pp JOIN map USING(tour_id) JOIN cem USING(combined_entity_id)
WHERE cem.market IN ('North America','Italy','Oceania')
GROUP BY 1,2,3 HAVING uploaded > 0
""".format(proj=config.BQ_PROJECT, ds=config.BQ_DATASET)


def _i(v):
    try:
        f = float(v)
        return 0 if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return 0


def _f(v):
    try:
        f = float(v)
        return 0.0 if math.isnan(f) else f
    except (TypeError, ValueError):
        return 0.0


_PP_CACHE = None


def pp_by_ce():
    """All PP allotments this season (NA/IT/OC), keyed by ce_id. Cached per process
    (season-scoped, market-independent). Uses the shared bq.query_df client."""
    global _PP_CACHE
    if _PP_CACHE is not None:
        return _PP_CACHE
    df = query_df(PP_SQL, "pp_allotments", {"season_start": config.PP_SEASON_START})
    res = {}
    for _, r in df.iterrows():
        lu = r["last_upload"]
        lu = None if (lu is None or (isinstance(lu, float) and math.isnan(lu))) else str(lu)[:10]
        res[str(r["ce_id"])] = {"market": r["market"], "ce": r["ce"],
            "uploaded": _i(r["uploaded"]), "sold": _i(r["sold"]),
            "loss_liab": _f(r["loss_liab"]), "last_upload": lu}
    _PP_CACHE = res
    return res


def build_pp(snap):
    """Report-engine entry: PP rows for THIS snapshot's market, joined to CE funnel.
    Returns [] on any failure (guarded — never breaks the report)."""
    market = (snap.get("meta") or {}).get("market")
    ces = {str(c.get("ce_id")): c for c in snap.get("ces", [])}
    try:
        ppmap = pp_by_ce()
    except Exception:
        return []
    rows = []
    for cid, ppd in ppmap.items():
        if ppd["market"] != market:
            continue
        ce = ces.get(cid)
        if ce:
            r = pp_row(ce, ppd)
        else:  # PP CE below the snapshot activity threshold — still show inventory health
            r = {"market": market, "ce": ppd["ce"], "uploaded": ppd["uploaded"], "sold": ppd["sold"],
                 "str_pct": round(ppd["sold"] / ppd["uploaded"] * 100) if ppd["uploaded"] else None,
                 "loss_liab": ppd["loss_liab"], "last_upload": ppd["last_upload"],
                 "pp_pct_orders": None, "cvr": None, "cvr_wow": None, "cm2_4w": None, "cm2_trend": None}
        r["ce_id"] = cid
        rows.append(r)
    rows.sort(key=lambda x: -(x["uploaded"] or 0))
    return rows


def _sum(wk, key, a, b=None):
    s = wk[a:b] if b is not None else wk[a:]
    return sum((w.get(key) or 0) for w in s)


def pp_row(ce, ppd):
    """Attach CE-funnel growth metrics to a PP CE. Returns dict of display metrics."""
    wk = ce.get("weekly") or []
    w0 = wk[-1] if wk else {}
    wm1 = wk[-2] if len(wk) > 1 else {}
    str_pct = round(ppd["sold"] / ppd["uploaded"] * 100) if ppd["uploaded"] else None
    # materiality: PP sold (season-cumulative) vs CE orders (trailing ~12wk in the
    # snapshot). Windows differ by design — a rough "how big is PP vs recent demand"
    # ratio, NOT a same-period share. Labeled as such in the render.
    ce_orders = _sum(wk, "orders", 0)
    pp_pct_orders = round(ppd["sold"] / ce_orders * 100) if ce_orders else None
    # CVR level + WoW
    cvr = w0.get("cvr_pct"); cvr_wow = ((cvr / wm1.get("cvr_pct") - 1) * 100
                                        if (cvr and wm1.get("cvr_pct")) else None)
    # CM2 = CM1 - spend, trailing-4wk + trend vs prior-4wk
    cm2_4w = _sum(wk, "cm1", -4) - _sum(wk, "spend", -4)
    cm2_p4 = (_sum(wk, "cm1", -8, -4) - _sum(wk, "spend", -8, -4)) if len(wk) >= 8 else None
    cm2_trend = ("↑" if (cm2_p4 is not None and cm2_4w > cm2_p4) else
                 "↓" if (cm2_p4 is not None and cm2_4w < cm2_p4) else "·")
    return {"market": ppd["market"], "ce": ppd["ce"], "uploaded": ppd["uploaded"], "sold": ppd["sold"],
            "str_pct": str_pct, "loss_liab": ppd["loss_liab"], "last_upload": ppd["last_upload"],
            "pp_pct_orders": pp_pct_orders, "cvr": cvr, "cvr_wow": cvr_wow,
            "cm2_4w": cm2_4w, "cm2_trend": cm2_trend}
