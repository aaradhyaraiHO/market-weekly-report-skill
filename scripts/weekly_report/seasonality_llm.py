"""Explore layer — LLM CE seasonality assessment (high / shoulder / low season).

Classifies each CE's season FOR THE REPORT WEEK from its identity (name, category,
subcategory, city) + the week's date, using an LLM's domain knowledge (alpine peaks
in summer, ski resorts & Christmas markets in winter, museums roughly year-round,
etc.), optionally grounded by the CE's TY-vs-LY revenue shape. The result is attached
as `ce["season"] = {"state": "high"|"shoulder"|"low", "reason": "<=10 words"}` and
rendered as an info tag on the CE.

Design — cache-first + guarded (mirrors the other enrichment lookups):
  cache = .cache/weekly_report/seasonality_<slug>_<YYYY-MM>.json  (month-keyed; weekly runs within a month reuse it)→ {ce_id: {state, reason}}
  attach(snap):
    1. load the cache; set ce["season"] for every CE found there.
    2. for CEs missing from cache AND if ANTHROPIC_API_KEY is set, classify via the
       Anthropic API in batches, update the cache, and tag them.
    3. no key + not cached  -> deterministic DATA HEURISTIC (_classify_heuristic) tags it
       from the monthly curve, so a tag is ALWAYS produced (no external dependency).
This keeps LLM cost off the weekly hot path while guaranteeing tags on every run, key or not.
A key-less env can also be seeded out-of-band (e.g. a subagent writes the cache).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

MODEL = os.environ.get("SEASONALITY_LLM_MODEL", "claude-haiku-4-5-20251001")
BATCH = 40                     # CEs per LLM call
STATES = {"high", "shoulder", "low"}

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache" / "weekly_report"


def cache_path(snap) -> Path:
    meta = snap.get("meta", {}) or {}
    slug = meta.get("market_slug") or "market"
    month = (meta.get("week_start") or "0000-00")[:7]   # seasonality is a MONTHLY property → key by month
    return _CACHE_DIR / f"seasonality_{slug}_{month}.json"


def _load_cache(snap) -> dict:
    p = cache_path(snap)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(snap, data: dict) -> None:
    p = cache_path(snap)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2))


def _monthly_revenue(snap) -> dict:
    """{ce_id: {"YYYY-MM": revenue}} — ~15 months of monthly predicted revenue per CE.

    Grounds the seasonality call in the CE's OWN history (combined_entity_stats,
    same predicted-revenue basis as the report). combined_entity_id matches the
    snapshot ce_id directly. Guarded → {} on any failure.
    """
    meta = snap.get("meta", {}) or {}
    week = meta.get("week_start")
    slug = meta.get("market_slug")
    try:
        import os, sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import config
        from bq import query_df
        market = config.MARKETS.get(slug) or meta.get("market")
        sql = f"""
        SELECT combined_entity_id                       AS ce_id,
               FORMAT_DATE('%Y-%m', report_date)        AS ym,
               ROUND(SUM({config.REVENUE_COL}))         AS rev
        FROM {config.CE_STATS}
        WHERE business_market = @market
              AND report_date >= DATE_SUB(DATE_TRUNC(DATE(@week), MONTH), INTERVAL 14 MONTH)
              AND report_date <  DATE_TRUNC(DATE_ADD(DATE(@week), INTERVAL 1 MONTH), MONTH)
        GROUP BY 1, 2
        """
        df = query_df(sql, "ce_monthly_rev", {"market": market, "week": week})
        out = {}
        for _, r in df.iterrows():
            out.setdefault(str(r["ce_id"]), {})[str(r["ym"])] = float(r["rev"] or 0)
        return out
    except Exception as e:
        print(f"[seasonality_llm] monthly-revenue fetch failed ({e!r}); "
              f"falling back to identity-only classification.")
        return {}


def _ce_brief(ce, monthly) -> dict:
    """Identity + the CE's ~15-month monthly revenue curve (the primary seasonality signal)."""
    md = ce.get("metadata") or {}
    ser = monthly.get(str(ce["ce_id"])) or {}
    months = sorted(ser)[-15:]
    return {
        "ce_id": ce["ce_id"],
        "name": ce.get("ce_name"),
        "category": md.get("category"),
        "subcategory": md.get("subcategory"),
        "city": md.get("city"),
        "monthly_rev": {m: round(ser[m]) for m in months},   # {YYYY-MM: revenue}
    }


_PROMPT = (
    "You assess travel-experience seasonality from ACTUAL monthly revenue history and give a "
    "FORWARD-LOOKING tag. Each Combined Entity (CE) has identity (name/category/city) and "
    "monthly_rev = predicted revenue by calendar month (last ~15 months, keyed YYYY-MM). The "
    "REPORT MONTH is the month of {week}.\n"
    "For each CE:\n"
    "1. Find its PEAK calendar month(s) from monthly_rev. SEPARATE GROWTH FROM SEASONALITY — a "
    "series rising almost every month is growth, NOT a peak; compare the SAME month year-over-"
    "year and the repeating within-year shape (Southern-Hemisphere markets invert).\n"
    "2. Say where the report month sits in the cycle.\n"
    "Fields per CE: state (high|shoulder|low for the report month); peak (e.g. 'Aug' or "
    "'Jul-Sep'); phase (pre|peak|post|off); note (<=8-word forward-looking phrase, e.g. 'Builds "
    "to Aug peak, 2mo out' / 'In peak now' / 'Winding down, peaked May' / 'Off-season, Dec peak "
    "5mo out'). Thin/new history → phase 'unknown', note 'new/thin — no read'.\n\n"
    "Return ONLY a JSON array, one object per CE, same order:\n"
    '  {{"ce_id":"<id>","state":"high|shoulder|low","peak":"<mon>","phase":"pre|peak|post|off","note":"<phrase>"}}\n\n'
    "CEs:\n{ces}"
)


def _classify_via_api(briefs, week):
    """Call the Anthropic API in batches → {ce_id: {state, reason}}. [] on any failure."""
    try:
        import anthropic
    except Exception:
        return {}
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {}
    client = anthropic.Anthropic()
    out = {}
    for i in range(0, len(briefs), BATCH):
        chunk = briefs[i:i + BATCH]
        prompt = _PROMPT.format(week=week, ces=json.dumps(chunk, ensure_ascii=False))
        try:
            msg = client.messages.create(
                model=MODEL, max_tokens=4000,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            arr = json.loads(text[text.index("["):text.rindex("]") + 1])
            for r in arr:
                st = str(r.get("state", "")).lower()
                if st in STATES:
                    out[str(r["ce_id"])] = {"state": st, "phase": r.get("phase", "unknown"),
                                            "peak": r.get("peak"), "note": r.get("note", "")}
        except Exception as e:
            print(f"[seasonality_llm] batch {i // BATCH} failed ({e!r}); skipping.")
    return out


_MON = {"01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
        "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec"}


def _profile(ser):
    """Growth-detrended seasonal index per calendar month: value / trailing-12mo mean,
    averaged across years. Returns {mm: index}."""
    allm = sorted(ser)
    by_cal = {}
    for i, m in enumerate(allm):
        v = ser.get(m) or 0
        if v <= 0:
            continue
        window = [ser.get(x) or 0 for x in allm[max(0, i - 11):i + 1]]
        base = (sum(window) / len(window)) if window else 0
        if base > 0:
            by_cal.setdefault(m[-2:], []).append(v / base)
    return {c: sum(vs) / len(vs) for c, vs in by_cal.items()}


def _phrase(rm, profile):
    """Turn a seasonal profile into a FORWARD-LOOKING tag relative to report month `rm`.
    Returns {state, phase, peak, note}. phase ∈ pre|peak|post|off."""
    peak_mm = max(profile, key=profile.get)
    peak = _MON[peak_mm]
    mtp = (int(peak_mm) - int(rm)) % 12            # months until the peak
    cur = profile.get(rm, 1.0)
    state = "high" if cur >= 1.15 else "low" if cur <= 0.85 else "shoulder"
    if mtp == 0 or (state == "high" and mtp >= 9):
        phase, note = "peak", "In peak season (~%s)" % peak
    elif 1 <= mtp <= 4:
        phase, note = "pre", "Builds to %s peak · %dmo" % (peak, mtp)
    elif 9 <= mtp <= 11:
        phase, note = "post", "Winding down · peaked %s" % peak
    else:                                          # 5–8 months out — deep off-season
        phase, note = "off", "Off-season · %s peak %dmo out" % (peak, mtp)
    return {"state": state, "phase": phase, "peak": peak, "note": note}


def _classify_heuristic(briefs, report_ym) -> dict:
    """Deterministic, no-LLM fallback so a FORWARD-LOOKING season tag exists on EVERY run.

    Builds a growth-detrended seasonal profile from the monthly curve, finds the CE's
    peak month, and expresses where the report month sits in the cycle (builds-to-peak /
    in-peak / winding-down / off-season). Thin history (<8 revenue months) → no read.
    """
    rm = str(report_ym)[-2:]
    out = {}
    for b in briefs:
        cid = str(b["ce_id"])
        ser = b.get("monthly_rev") or {}
        if sum(1 for m in ser if (ser.get(m) or 0) > 0) < 8:
            out[cid] = {"state": "shoulder", "phase": "unknown", "peak": None,
                        "note": "New / thin history — no seasonal read"}
            continue
        prof = _profile(ser)
        out[cid] = _phrase(rm, prof) if prof else {
            "state": "shoulder", "phase": "unknown", "peak": None, "note": "flat / no seasonal read"}
    return out


def attach(snap) -> int:
    """Attach ce['season'] to every CE. Runs on EVERY report build.

    Cache-first (month-keyed). For CEs missing from cache: classify via the Anthropic
    API when ANTHROPIC_API_KEY is set (richer), else via the deterministic data
    heuristic — so a tag is always produced. Fresh results are cached. Returns count.
    """
    meta = snap.get("meta", {}) or {}
    week = meta.get("week_start")
    ym = (week or "")[:7]
    cache = _load_cache(snap)
    ces = snap.get("ces", [])
    missing = [c for c in ces if str(c["ce_id"]) not in cache]
    if missing:
        monthly = _monthly_revenue(snap)
        briefs = [_ce_brief(c, monthly) for c in missing]
        fresh = _classify_via_api(briefs, week) if os.environ.get("ANTHROPIC_API_KEY") else {}
        remaining = [b for b in briefs if str(b["ce_id"]) not in fresh]
        fresh.update(_classify_heuristic(remaining, ym))   # guarantees coverage every run
        if fresh:
            cache.update(fresh)
            _save_cache(snap, cache)
    n = 0
    for c in ces:
        tag = cache.get(str(c["ce_id"]))
        if tag and tag.get("state") in STATES:
            c["season"] = {"state": tag["state"], "phase": tag.get("phase", "unknown"),
                           "peak": tag.get("peak"), "note": tag.get("note") or tag.get("reason", "")}
            n += 1
    return n


if __name__ == "__main__":
    import sys, pickle
    snap = pickle.load(open(sys.argv[1] if len(sys.argv) > 1 else "/tmp/na_snap.pkl", "rb"))
    print(f"cache: {cache_path(snap)}")
    print(f"tagged {attach(snap)} / {len(snap.get('ces', []))} CEs")
    for c in snap["ces"][:8]:
        s = c.get("season")
        if s:
            print(f"  {c['ce_name'][:30]:30s} {s['state']:8s} — {s['reason']}")
