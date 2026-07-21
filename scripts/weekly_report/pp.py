"""PP tracking bucket — sourced ENTIRELY from fct_pp_tickets (the per-ticket "FDT"
truth: experience_date, expiring_at, is_sold, validity_type, loss_liability,
booking_created_at, combined_entity_id) + the CE weekly funnel for CVR/Net-ROI.
Metrics only, no verdict.

Checklist (2026-07-17), all from fct_pp_tickets ticket grain:
  1 dated (DATE_TIME) vs open (OPEN); liability = DATED unsold only
  2 weekly run-rate: last-wk sold (booking_created_at) vs needed/wk (remaining ÷ wks-to-expiry)
  3 unsold tickets EXPIRING this calendar month (the real loss)
  4 Net ROI = (CM1 − dated loss-liability) / cost
  5 STR on current + next 2 weeks (experience_date window)
  6/7 dropped last-upload + PP-%-of-orders
"""
from __future__ import annotations
import math, datetime
import config
from bq import query_df

NEAR_TERM_DAYS = 20   # current + next 2 weeks

PP_SQL = """
WITH t AS (
  SELECT combined_entity_id,
         combined_entity_name,
         validity_type, is_sold, ticket_status,
         DATE(experience_timestamp) exp_date,
         DATE(expiring_at) expiry,
         DATE(booking_created_at) booked,
         loss_liability
  FROM `{proj}.{ds}.fct_pp_tickets`
  WHERE ticket_status != 'Invalid'
        AND ( validity_type = 'OPEN'
              OR DATE(experience_timestamp) >= DATE(@week)
              OR DATE_TRUNC(DATE(expiring_at), MONTH) = DATE_TRUNC(DATE(@week), MONTH) )
),
agg AS (
  SELECT combined_entity_id,
    ANY_VALUE(combined_entity_name) ce,
    COUNTIF(validity_type='DATE_TIME') dated,
    COUNTIF(validity_type='OPEN') open_ct,
    ROUND(SUM(IF(validity_type='DATE_TIME' AND NOT is_sold, loss_liability, 0)),0) loss_liab_dated,
    COUNTIF(exp_date BETWEEN DATE(@week) AND DATE_ADD(DATE(@week), INTERVAL {ntd} DAY)) nt_total,
    COUNTIF(exp_date BETWEEN DATE(@week) AND DATE_ADD(DATE(@week), INTERVAL {ntd} DAY) AND is_sold) nt_sold,
    COUNTIF(validity_type='DATE_TIME' AND DATE_TRUNC(expiry, MONTH)=DATE_TRUNC(DATE(@week), MONTH) AND NOT is_sold) expiring_unsold,
    ROUND(SUM(IF(validity_type='DATE_TIME' AND DATE_TRUNC(expiry, MONTH)=DATE_TRUNC(DATE(@week), MONTH) AND NOT is_sold, loss_liability, 0)),0) expiring_loss,
    COUNTIF(validity_type='DATE_TIME' AND NOT is_sold AND exp_date >= DATE(@week)) remaining_dated,
    MAX(IF(validity_type='DATE_TIME' AND NOT is_sold, exp_date, NULL)) max_exp,
    COUNTIF(is_sold AND booked BETWEEN DATE_SUB(DATE(@week), INTERVAL 7 DAY) AND DATE_SUB(DATE(@week), INTERVAL 1 DAY)) sold_last_wk,
    COUNT(*) total, COUNTIF(is_sold) sold
  FROM t GROUP BY 1
),
cem AS (SELECT combined_entity_id, ANY_VALUE(business_market) market
        FROM `{proj}.{ds}.dim_experiences` GROUP BY 1)
SELECT cem.market, a.combined_entity_id AS ce_id, a.ce,
       a.dated, a.open_ct, a.loss_liab_dated, a.nt_total, a.nt_sold,
       a.expiring_unsold, a.expiring_loss, a.remaining_dated, a.max_exp, a.sold_last_wk, a.total, a.sold
FROM agg a JOIN cem ON cem.combined_entity_id = a.combined_entity_id
WHERE cem.market IN ({markets}) AND (a.dated + a.open_ct) > 0
""".format(proj=config.BQ_PROJECT, ds=config.BQ_DATASET, ntd=NEAR_TERM_DAYS,
           markets=", ".join("'" + m.replace("'", "\\'") + "'" for m in config.MARKETS.values()))


def _i(v):
    try:
        f = float(v); return 0 if math.isnan(f) else int(f)
    except (TypeError, ValueError):
        return 0


def _f(v):
    try:
        f = float(v); return 0.0 if math.isnan(f) else f
    except (TypeError, ValueError):
        return 0.0


_PP_CACHE = {}


def pp_by_ce(week):
    if week in _PP_CACHE:
        return _PP_CACHE[week]
    df = query_df(PP_SQL, "pp_tickets", {"week": week})
    res = {}
    for _, r in df.iterrows():
        mx = r["max_exp"]
        mx = None if (mx is None or (isinstance(mx, float) and math.isnan(mx))) else str(mx)[:10]
        res[str(r["ce_id"])] = {
            "market": r["market"], "ce": r["ce"], "dated": _i(r["dated"]), "open_ct": _i(r["open_ct"]),
            "loss_liab_dated": _f(r["loss_liab_dated"]), "nt_total": _i(r["nt_total"]), "nt_sold": _i(r["nt_sold"]),
            "expiring_unsold": _i(r["expiring_unsold"]), "expiring_loss": _f(r["expiring_loss"]),
            "remaining_dated": _i(r["remaining_dated"]),
            "max_exp": mx, "sold_last_wk": _i(r["sold_last_wk"]), "total": _i(r["total"]), "sold": _i(r["sold"])}
    _PP_CACHE[week] = res
    return res


def _sum(wk, key, a, b=None):
    s = wk[a:b] if b is not None else wk[a:]
    return sum((w.get(key) or 0) for w in s)


def pp_row(ce, ppd, week):
    wk = (ce.get("weekly") or []) if ce else []
    w0 = wk[-1] if wk else {}
    wm1 = wk[-2] if len(wk) > 1 else {}
    # near-term (current + next 2wk) STR; fall back to overall for all-open CEs
    str_nt = (round(ppd["nt_sold"] / ppd["nt_total"] * 100) if ppd["nt_total"]
              else (round(ppd["sold"] / ppd["total"] * 100) if ppd["total"] else None))
    # needed/wk to clear remaining dated before expiry
    needed_wk = None
    if ppd["remaining_dated"] and ppd["max_exp"]:
        try:
            wsd = datetime.date.fromisoformat(str(week)[:10])
            wks = max((datetime.date.fromisoformat(ppd["max_exp"]) - wsd).days / 7.0, 1.0)
            needed_wk = round(ppd["remaining_dated"] / wks)
        except Exception:
            pass
    # Net ROI = (CM1 − REALIZED inventory loss) / cost. Realized loss = loss_liability of
    # tickets EXPIRING unsold this period (dimensionally a periodic cost), NOT the full
    # at-risk stock (which would dwarf a 4-wk CM1 flow and produce nonsense negatives).
    cm1_4w = _sum(wk, "cm1", -4); cost_4w = _sum(wk, "spend", -4)
    net_roi = round((cm1_4w - ppd["expiring_loss"]) / cost_4w * 100) if cost_4w else None
    cvr = w0.get("cvr_pct"); cvr_wow = ((cvr / wm1.get("cvr_pct") - 1) * 100
                                        if (cvr and wm1.get("cvr_pct")) else None)
    return {"market": ppd["market"], "ce": ppd["ce"], "ce_id": str(ppd.get("ce_id", "")),
            "dated": ppd["dated"], "open_ct": ppd["open_ct"], "str_nt": str_nt,
            "loss_liab_dated": ppd["loss_liab_dated"], "expiring_unsold": ppd["expiring_unsold"],
            "remaining_dated": ppd["remaining_dated"], "sold_last_wk": ppd["sold_last_wk"],
            "needed_wk": needed_wk, "net_roi": net_roi, "cvr": cvr, "cvr_wow": cvr_wow}


def build_pp(snap):
    """Report-engine entry: PP rows for THIS snapshot's market. Returns [] on failure."""
    meta = snap.get("meta") or {}
    market = meta.get("market"); week = meta.get("week_start")
    ces = {str(c.get("ce_id")): c for c in snap.get("ces", [])}
    try:
        ppmap = pp_by_ce(week)
    except Exception:
        return []
    rows = []
    for cid, ppd in ppmap.items():
        if ppd["market"] != market:
            continue
        ppd["ce_id"] = cid
        r = pp_row(ces.get(cid), ppd, week)
        r["ce_id"] = cid
        rows.append(r)
    # rank by dated at-risk $ first, then expiring-unsold (the real loss exposure)
    rows.sort(key=lambda x: (-(x["loss_liab_dated"] or 0), -(x["expiring_unsold"] or 0)))
    return rows
