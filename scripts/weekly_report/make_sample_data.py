#!/usr/bin/env python3
"""
Generate a realistic sample_data.json for the Weekly Market Report V1 render.

This produces a multi-market BUNDLE that follows the schema-v1 contract in
thoughts/shared/plans/2026-07-09-weekly-report-v1.md exactly (each element of
`markets` is a per-market snapshot as wt-weekly-data will emit). The render
(`render.py`) accepts either this bundle or a set of individual per-market
snapshot files, so swapping fake data for the real mart is a drop-in.

Numbers are internally consistent (revenue = orders x aov, rpc = revenue /
clicks, roi = cm1 / spend, etc.) and anchored to the NA week 2026-06-29
validation references in the plan (market revenue ~= $615K, no-bid ~= 57
campaigns / ~$21.7K/wk, 5 up-swing CM1/conv alerts). Organic CEs carry real
nulls (no spend / ROI / CVR) so the render exercises the "—, never 0" rule.

Deterministic: seeded RNG, no wall-clock in the data (generated_at is fixed to
the reference run date) so re-running yields a byte-stable file.
"""
import json
import math
import os
import random
from datetime import date, timedelta

REF_WEEK = date(2026, 6, 29)          # W0 (Monday) — the reported week
GENERATED_AT = "2026-07-09T00:00:00Z"  # fixed; contract keeps this in meta
SCHEMA_VERSION = 1
OUT = os.path.join(os.path.dirname(__file__), "sample_data.json")

WEEKS = [(REF_WEEK - timedelta(weeks=(11 - i))).isoformat() for i in range(12)]

CATEGORIES = {
    "Landmarks": ["Observation Decks", "Towers", "Bridges"],
    "Museums": ["Art", "Science", "History"],
    "Cruises": ["Sightseeing", "Dinner", "Whale Watching"],
    "Tours": ["Hop-on Hop-off", "Walking", "Day Trips"],
    "Theme Parks": ["Studios", "Rides", "Water Parks"],
    "Shows": ["Broadway", "Immersive", "Live Music"],
    "Nature": ["Canyons", "Glaciers", "National Parks"],
}
MGMT = ["Managed", "Self-Serve", "Hybrid"]
EVOLUTION = ["Scaling", "Mature", "Emerging", "Declining"]
NEW_EXISTING = ["Existing", "New"]
TIERS = ["Tier 1", "Tier 2", "Tier 3"]


def compact_ok(v):
    return v if v is not None else None


# --- named CEs per market (drawn from the NA alignment references) ---------
NA_CES = [
    ("Kennedy Space Center", "Landmarks", "Towers", "Orlando"),
    ("SUMMIT One Vanderbilt", "Landmarks", "Observation Decks", "New York"),
    ("The High Roller", "Landmarks", "Observation Decks", "Las Vegas"),
    ("Edge NYC", "Landmarks", "Observation Decks", "New York"),
    ("Universal Studios Orlando", "Theme Parks", "Studios", "Orlando"),
    ("Universal Studios Hollywood", "Theme Parks", "Studios", "Los Angeles"),
    ("American Museum of Natural History", "Museums", "Science", "New York"),
    ("Arte Museum", "Museums", "Art", "Las Vegas"),
    ("MoMA", "Museums", "Art", "New York"),
    ("Intrepid Museum", "Museums", "History", "New York"),
    ("9/11 Memorial & Museum", "Museums", "History", "New York"),
    ("Niagara Falls US Tours", "Nature", "National Parks", "Niagara Falls"),
    ("Niagara Falls Canada Tours", "Nature", "National Parks", "Niagara Falls"),
    ("Antelope Canyon Tours", "Nature", "Canyons", "Page"),
    ("Walt Disney World", "Theme Parks", "Rides", "Orlando"),
    ("Disneyland Resort", "Theme Parks", "Rides", "Los Angeles"),
    ("Alcatraz Island", "Landmarks", "Bridges", "San Francisco"),
    ("Chicago Architecture Cruises", "Cruises", "Sightseeing", "Chicago"),
    ("Immersive Theatre LV", "Shows", "Immersive", "Las Vegas"),
    ("Las Vegas Shows", "Shows", "Live Music", "Las Vegas"),
    ("Hawaii Luaus", "Shows", "Live Music", "Honolulu"),
    ("Kualoa Ranch", "Nature", "National Parks", "Honolulu"),
    ("Steamboat Natchez", "Cruises", "Dinner", "New Orleans"),
    ("American Dream", "Theme Parks", "Water Parks", "New York"),
    ("Country Music Hall of Fame", "Museums", "History", "Nashville"),
    ("HOHO Seattle", "Tours", "Hop-on Hop-off", "Seattle"),
    ("HOHO San Francisco", "Tours", "Hop-on Hop-off", "San Francisco"),
    ("HOHO New York", "Tours", "Hop-on Hop-off", "New York"),
    ("LEGOLAND New York", "Theme Parks", "Rides", "New York"),
    ("Vancouver Whale Watching", "Cruises", "Whale Watching", "Vancouver"),
    ("Boston Whale Watching", "Cruises", "Whale Watching", "Boston"),
    ("Mercer Labs", "Museums", "Art", "New York"),
    ("Mendenhall Glacier", "Nature", "Glaciers", "Juneau"),
    ("Empire State Building", "Landmarks", "Observation Decks", "New York"),
    ("Top of the Rock", "Landmarks", "Observation Decks", "New York"),
    ("Statue of Liberty Cruise", "Cruises", "Sightseeing", "New York"),
    ("Grand Canyon Day Trips", "Tours", "Day Trips", "Las Vegas"),
    ("Hoover Dam Tours", "Tours", "Day Trips", "Las Vegas"),
    ("Broadway Shows NYC", "Shows", "Broadway", "New York"),
    ("San Diego Zoo", "Nature", "National Parks", "San Diego"),
]

IT_CES = [
    ("Colosseum Guided Tours", "Landmarks", "Towers", "Rome"),
    ("Vatican Museums & Sistine Chapel", "Museums", "Art", "Rome"),
    ("Uffizi Gallery", "Museums", "Art", "Florence"),
    ("Doge's Palace", "Landmarks", "Bridges", "Venice"),
    ("Leaning Tower of Pisa", "Landmarks", "Towers", "Pisa"),
    ("Pompeii Ruins Tours", "Tours", "Walking", "Naples"),
    ("Venice Gondola Rides", "Cruises", "Sightseeing", "Venice"),
    ("Milan Duomo Rooftop", "Landmarks", "Towers", "Milan"),
    ("Accademia Gallery", "Museums", "Art", "Florence"),
    ("Amalfi Coast Day Trips", "Tours", "Day Trips", "Naples"),
    ("Cinque Terre Tours", "Tours", "Day Trips", "La Spezia"),
    ("Borghese Gallery", "Museums", "Art", "Rome"),
    ("St. Mark's Basilica", "Landmarks", "Towers", "Venice"),
    ("Tuscany Wine Tours", "Tours", "Day Trips", "Florence"),
    ("Lake Como Boat Tours", "Cruises", "Sightseeing", "Como"),
    ("Roman Catacombs", "Tours", "Walking", "Rome"),
    ("Mount Vesuvius Hikes", "Nature", "National Parks", "Naples"),
    ("Capri Island Cruises", "Cruises", "Sightseeing", "Naples"),
    ("Florence Cathedral Dome", "Landmarks", "Towers", "Florence"),
    ("Sicily Etna Tours", "Nature", "National Parks", "Catania"),
    ("Verona Arena Shows", "Shows", "Live Music", "Verona"),
    ("Trevi Underground", "Tours", "Walking", "Rome"),
]

OCE_CES = [
    ("Sydney Opera House Tours", "Landmarks", "Towers", "Sydney"),
    ("Sydney Harbour Bridge Climb", "Landmarks", "Bridges", "Sydney"),
    ("Great Barrier Reef Cruises", "Cruises", "Sightseeing", "Cairns"),
    ("Sydney Harbour Dinner Cruise", "Cruises", "Dinner", "Sydney"),
    ("Melbourne Great Ocean Road", "Tours", "Day Trips", "Melbourne"),
    ("Blue Mountains Day Trips", "Tours", "Day Trips", "Sydney"),
    ("Taronga Zoo", "Nature", "National Parks", "Sydney"),
    ("Auckland Sky Tower", "Landmarks", "Towers", "Auckland"),
    ("Hobbiton Movie Set Tours", "Tours", "Walking", "Matamata"),
    ("Milford Sound Cruises", "Cruises", "Sightseeing", "Queenstown"),
    ("Queenstown Skyline Gondola", "Landmarks", "Observation Decks", "Queenstown"),
    ("Kangaroo Island Tours", "Nature", "National Parks", "Adelaide"),
    ("Whitsundays Sailing", "Cruises", "Sightseeing", "Airlie Beach"),
    ("Uluru Sunset Tours", "Nature", "National Parks", "Uluru"),
    ("Melbourne Aquarium", "Museums", "Science", "Melbourne"),
    ("Rotorua Geothermal Tours", "Nature", "National Parks", "Rotorua"),
]

# scale ~= target market weekly revenue / 1.39 (avg tier multiplier over the
# CE mix); tuned so North America W0 lands near the $615.4K plan reference.
MARKETS = [
    ("North America", "north_america", NA_CES, 442000),
    ("Italy", "italy", IT_CES, 165000),
    ("Oceania", "oceania", OCE_CES, 92000),
]


def seasonal_factor(week_idx, phase):
    """Smooth seasonal ramp across the 12-week window (summer build-up)."""
    return 1.0 + 0.18 * math.sin((week_idx / 11.0) * math.pi + phase)


def build_ce(rng, ce_id, name, category, subcat, city, market_scale, big_move=0.0):
    """Return one CE dict (metadata + 12-wk weekly series)."""
    is_organic = rng.random() < 0.15
    mgmt = rng.choice(MGMT)
    evolution = rng.choices(EVOLUTION, weights=[3, 4, 2, 1])[0]
    new_existing = rng.choices(NEW_EXISTING, weights=[5, 1])[0]
    if new_existing == "New":
        evolution = rng.choice(["Emerging", "Scaling"])
    tier = rng.choices(TIERS, weights=[2, 3, 3])[0]

    # per-CE scale (share of market), heavier tail for Tier 1
    tier_mult = {"Tier 1": rng.uniform(2.2, 4.0), "Tier 2": rng.uniform(0.8, 1.6),
                 "Tier 3": rng.uniform(0.2, 0.7)}[tier]
    base_rev = market_scale / 40.0 * tier_mult
    phase = rng.uniform(-0.6, 0.6)
    aov = rng.uniform(45, 260)
    base_cvr = rng.uniform(2.4, 7.5)          # %
    base_tr = rng.uniform(14, 34)             # take rate %
    base_roi = rng.uniform(95, 320)           # %
    drift = rng.uniform(-0.015, 0.02)         # slow WoW trend
    base_yoy = rng.uniform(-18, 28)           # per-CE YoY% (weekday-aligned)

    weekly = []
    for i, wk in enumerate(WEEKS):
        sf = seasonal_factor(i, phase) * (1 + drift * i)
        noise = rng.uniform(0.9, 1.1)
        rev = base_rev * sf * noise
        # inject a pronounced W0 move for a handful of CEs (top movers)
        if i == 11 and big_move:
            rev *= (1 + big_move)
        aov_i = aov * rng.uniform(0.96, 1.05)
        orders = max(1, round(rev / aov_i))
        rev = round(orders * aov_i, 2)

        if is_organic:
            cvr = None
            clicks = None
            spend = None
            cm1 = None
            roi = None
            tr = None
            rpc = None
            cm1_per_conv = None
            paid_contrib = None
        else:
            cvr = round(base_cvr * rng.uniform(0.9, 1.12), 2)
            if i == 11 and big_move < -0.2:      # a CVR-driven drop
                cvr = round(cvr * 0.6, 2)
            clicks = max(1, round(orders / (cvr / 100.0)))
            rpc = round(rev / clicks, 2)
            tr = round(base_tr * rng.uniform(0.95, 1.08), 2)
            roi = round(base_roi * sf / seasonal_factor(0, phase) * rng.uniform(0.9, 1.1), 1)
            if i == 11 and big_move:
                roi = round(roi * (1 + big_move * 0.5), 1)
            cm1 = round(rev * (tr / 100.0) * rng.uniform(0.7, 1.0), 2)
            spend = round(cm1 / (roi / 100.0), 2) if roi else None
            cm1_per_conv = round(cm1 / orders, 2)
            paid_contrib = round(min(98, max(8, rng.uniform(35, 88))), 1)

        # YoY% (weekday-aligned -364d); a small share of CEs have no LY
        # comparison (new this year) -> null, exercising the "—" render.
        if new_existing == "New" and rng.random() < 0.6:
            yoy = None
        else:
            yoy = round(base_yoy + math.sin(i * 0.7) * 4 + rng.uniform(-3, 3), 1)

        weekly.append({
            "week": wk,
            "revenue": rev,
            "orders": orders,
            "clicks": clicks,
            "cvr_pct": cvr,
            "aov": round(aov_i, 2),
            "tr_pct": tr,
            "spend": spend,
            "cm1": cm1,
            "roi_pct": roi,
            "rpc": rpc,
            "cm1_per_conv": cm1_per_conv,
            "paid_contribution_pct": paid_contrib,
            "yoy_pct": yoy,
        })

    return {
        "ce_id": ce_id,
        "ce_name": name,
        "metadata": {
            "category": category,
            "subcategory": subcat,
            "city": city,
            "management_type": mgmt,
            "evolution": evolution,
            "new_vs_existing": new_existing,
            "tier": tier,
        },
        "weekly": weekly,
    }


def summarize_market(ces):
    """Aggregate CE weekly series into market_summary.weekly."""
    out = []
    for i, wk in enumerate(WEEKS):
        rev = orders = clicks = spend = cm1 = 0.0
        gbv = 0.0
        has_paid = False
        for ce in ces:
            w = ce["weekly"][i]
            rev += w["revenue"] or 0
            orders += w["orders"] or 0
            if w["clicks"]:
                clicks += w["clicks"]
            if w["spend"]:
                spend += w["spend"]
                has_paid = True
            if w["cm1"]:
                cm1 += w["cm1"]
        # GBV ≈ orders × avg AOV (slightly inflated vs revenue due to take rate)
        gbv = round(rev / 0.22, 2) if rev else 0.0  # ~22% take rate
        gbv_comp = round(gbv * 0.94, 2)  # ~94% completion rate
        cvr = round(orders / clicks * 100, 2) if clicks else None
        aov = round(gbv / orders, 2) if orders else None
        roi = round(cm1 / spend * 100, 1) if spend else None
        cr_pct = round(gbv_comp / gbv * 100, 2) if gbv else None
        tr_pct = round(rev / gbv_comp * 100, 2) if gbv_comp else None
        # Paid funnel approximations for sample data
        paid_clicks = int(clicks * 0.65) if clicks else None
        paid_conv = int(orders * 0.6) if orders else None
        paid_cvr = round(paid_conv / paid_clicks * 100, 2) if (paid_clicks and paid_conv) else None
        paid_conv_value = round(gbv * 0.6, 2) if gbv else None
        avg_cm1 = round(cm1 / paid_conv, 2) if (paid_conv and cm1) else None
        roi1 = round(roi * 1.05, 1) if roi else None
        # paid contribution: revenue from CEs that have paid spend / total
        paid_rev = sum((c["weekly"][i]["revenue"] or 0) for c in ces
                       if c["weekly"][i]["spend"])
        paid_contrib = round(paid_rev / rev * 100, 1) if rev else None
        out.append({
            "week": wk,
            "revenue": round(rev, 2),
            "gbv": round(gbv, 2),
            "orders": int(orders),
            "clicks": int(clicks) if clicks else None,
            "spend": round(spend, 2) if has_paid else None,
            "cm1": round(cm1, 2) if has_paid else None,
            "roi_pct": roi,
            "cvr_pct": cvr,
            "aov": aov,
            "cr_pct": cr_pct,
            "tr_pct": tr_pct,
            "roi1_pct": roi1,
            "paid_clicks": paid_clicks,
            "paid_cvr_pct": paid_cvr,
            "paid_conv_value": paid_conv_value,
            "avg_cm1": avg_cm1,
            "paid_contribution_pct": paid_contrib,
        })
    return out


def build_headlines(ces, market_weekly, yoy_pct):
    w0, w1 = market_weekly[-1], market_weekly[-2]
    wow = round((w0["revenue"] - w1["revenue"]) / w1["revenue"] * 100, 1)
    deltas = []
    for ce in ces:
        r0 = ce["weekly"][-1]["revenue"] or 0
        r1 = ce["weekly"][-2]["revenue"] or 0
        deltas.append({"ce_id": ce["ce_id"], "ce_name": ce["ce_name"],
                       "delta_wow": round(r0 - r1, 2)})
    gainers = sorted(deltas, key=lambda d: d["delta_wow"], reverse=True)[:5]
    drops = sorted(deltas, key=lambda d: d["delta_wow"])[:5]

    KEY_METRIC_SPEC = [
        ("revenue", "Revenue", "revenue", "revenue", True),
        ("gbv", "GBV", "gbv", "gbv", False),
        ("orders", "Orders", "orders", None, False),
        ("aov", "AOV", "aov", None, False),
        ("cr_pct", "CR%", "cr_pct", "cr_pct", False),
        ("tr_pct", "TR%", "tr_pct", "tr_pct", False),
        ("paid_clicks", "Paid Clicks", "paid_clicks", "paid_clicks", False),
        ("paid_cvr", "Paid CVR", "paid_cvr_pct", None, False),
        ("paid_conv_value", "Paid Conv Value", "paid_conv_value", None, False),
        ("avg_cm1", "Avg CM1", "avg_cm1", None, False),
        ("paid_roi", "Paid RoI", "roi_pct", None, False),
        ("roi1", "ROI 1", "roi1_pct", "roi1_pct", False),
    ]
    key_metrics = {}
    for key, label, field, ly_field, is_rev in KEY_METRIC_SPEC:
        v0 = w0.get(field)
        v1 = w1.get(field)
        d_abs = round(v0 - v1, 2) if (v0 is not None and v1 is not None) else None
        d_pct = round(100 * (v0 / v1 - 1), 1) if (v0 is not None and v1 not in (None, 0)) else None
        block = {"w0": v0, "wm1": v1, "delta_abs": d_abs, "delta_pct": d_pct,
                 "label": label, "field": field, "has_ly": ly_field is not None,
                 "ly_field": ly_field}
        if is_rev:
            block["yoy_pct"] = yoy_pct
        key_metrics[key] = block

    return {
        "revenue_w0": w0["revenue"],
        "wow_pct": wow,
        "yoy_pct": yoy_pct,
        "roi_w0_pct": w0["roi_pct"],
        "roi1_w0_pct": w0.get("roi1_pct"),
        "key_metrics": key_metrics,
        "top_gainers": gainers,
        "top_drops": drops,
    }


def build_snapshot(rng, market_name, slug, ce_defs, scale):
    # pre-assign pronounced W0 moves to a few CEs so top-movers are meaningful
    big_moves = {}
    idxs = list(range(len(ce_defs)))
    rng.shuffle(idxs)
    for j in idxs[:3]:
        big_moves[j] = rng.uniform(0.35, 0.7)      # big gainers
    for j in idxs[3:6]:
        big_moves[j] = -rng.uniform(0.3, 0.55)     # big drops

    ces = []
    for k, (name, cat, sub, city) in enumerate(ce_defs):
        ce_id = f"{slug[:2].upper()}{1000 + k}"
        ces.append(build_ce(rng, ce_id, name, cat, sub, city, scale,
                             big_move=big_moves.get(k, 0.0)))

    market_weekly = summarize_market(ces)
    yoy = round(rng.uniform(-8, 22), 1)
    headlines = build_headlines(ces, market_weekly, yoy)

    # --- section 2: follow-up (empty for Oceania to exercise empty state) ---
    followup = []
    if slug != "oceania":
        drops = headlines["top_drops"][:2]
        for d in drops:
            followup.append({
                "ce_id": d["ce_id"], "ce_name": d["ce_name"],
                "flagged_week": WEEKS[-2],
                "signal": "CVR drop >30% WoW",
                "status_now": rng.choice(["Recovered ✅", "Still soft", "Worsened"]),
            })

    # --- section 4: bucket 1 fluctuations (NA anchored to the 5 up-swings) --
    bucket1 = []
    if slug == "north_america":
        anchors = [
            ("The High Roller", "cm1_per_conv", "up"),
            ("Edge NYC", "cm1_per_conv", "up"),
            ("Universal Studios Hollywood", "rpc", "up"),
            ("American Museum of Natural History", "cm1_per_conv", "up"),
            ("Arte Museum", "cm1_per_conv", "up"),
        ]
        name_to_ce = {c["ce_name"]: c for c in ces}
        for nm, sig, direction in anchors:
            ce = name_to_ce.get(nm)
            if not ce:
                continue
            w0 = ce["weekly"][-1]
            base = ce["weekly"][-5]["cm1_per_conv"] or w0["cm1_per_conv"]
            val = w0["cm1_per_conv"]
            mag = round((val - base) / base * 100, 1) if base else 22.0
            bucket1.append({
                "ce_id": ce["ce_id"], "ce_name": nm,
                "signal": sig, "direction": direction,
                "magnitude_pct": abs(mag),
                "window": "l3w",
                "evidence": {
                    "value_now": val, "baseline": base,
                    "wow_pct": round(rng.uniform(18, 40), 1),
                },
                "paid_contribution_pct": w0["paid_contribution_pct"],
                "spend_wk": w0["spend"],
                "revenue_wk": w0["revenue"],
                "recommendation": "+15% seasonality adjustment (up-swing)"
                if (w0["paid_contribution_pct"] or 0) >= 30
                else "Review — low paid contribution",
            })
    else:
        # a couple of generic swings for other markets
        for d in headlines["top_drops"][:2]:
            ce = next(c for c in ces if c["ce_id"] == d["ce_id"])
            w0 = ce["weekly"][-1]
            if w0["cvr_pct"] is None:
                continue
            bucket1.append({
                "ce_id": ce["ce_id"], "ce_name": ce["ce_name"],
                "signal": "rpc", "direction": "down",
                "magnitude_pct": round(rng.uniform(36, 52), 1),
                "window": "l3w",
                "evidence": {
                    "value_now": w0["cvr_pct"],
                    "baseline": round(w0["cvr_pct"] * 1.5, 2),
                    "wow_pct": round(-rng.uniform(31, 48), 1),
                },
                "paid_contribution_pct": w0["paid_contribution_pct"],
                "spend_wk": w0["spend"], "revenue_wk": w0["revenue"],
                "recommendation": "−15% seasonality adjustment (down-swing)",
            })

    # --- section 6b: no-bid campaigns (NA anchored 57 / $21.7K) ------------
    if slug == "north_america":
        nb_count, nb_spend = 57, 21700.0
    elif slug == "italy":
        nb_count, nb_spend = 19, 6400.0
    else:
        nb_count, nb_spend = 11, 3100.0
    nb_rows = []
    paid_ces = [c for c in ces if c["weekly"][-1]["spend"]]
    rng.shuffle(paid_ces)
    for c in paid_ces[:min(8, len(paid_ces))]:
        w0 = c["weekly"][-1]
        nb_rows.append({
            "campaign_name": f"{c['ce_name']} · MaxConv (no tROAS)",
            "ce_id": c["ce_id"], "ce_name": c["ce_name"],
            "bidding_strategy": "MAXIMIZE_CONVERSIONS",
            "spend_wk": round(rng.uniform(60, 950), 2),
            "roi_pct": w0["roi_pct"],
            "clicks_wk": rng.randint(120, 2400),
            "new_this_week": rng.random() < 0.3,
        })
    no_bid = {"totals": {"count": nb_count, "spend_total": nb_spend}, "rows": nb_rows}

    # --- section 5: seasonality adjustments -------------------------------
    seasonality = []
    for c in rng.sample(ces, k=min(4, len(ces))):
        direction = rng.choice(["up", "down"])
        pre = round(rng.uniform(8000, 45000), 2)
        inw = round(pre * (rng.uniform(1.05, 1.4) if direction == "up"
                           else rng.uniform(0.6, 0.95)), 2)
        status = rng.choice(["active", "active", "expiring"])
        seasonality.append({
            "ce_id": c["ce_id"], "ce_name": c["ce_name"],
            "direction": direction, "pct": rng.choice([10, 15, 20, 25]),
            "start_date": WEEKS[-4], "end_date": WEEKS[-1],
            "status": status,
            "cm2_pre_4w_avg": pre, "cm2_in_window_avg": inw,
            "revenue_delta_pct": round((inw - pre) / pre * 100, 1),
            "recommendation": "Extend — CM2 sustained" if inw >= pre
            else "Expire — CM2 not holding",
        })

    # --- section 6a: levers -----------------------------------------------
    levers = []
    for c in rng.sample(ces, k=min(3, len(ces))):
        w0 = c["weekly"][-1]
        w1 = c["weekly"][-2]
        wow = round((w0["revenue"] - w1["revenue"]) / w1["revenue"] * 100, 1) \
            if w1["revenue"] else None
        levers.append({
            "ce_id": c["ce_id"], "ce_name": c["ce_name"],
            "lever": rng.choice(["pp", "marketing_budget", "tr_incentive"]),
            "since": WEEKS[-6],
            "weekly_perf_summary": {
                "revenue_wk": w0["revenue"],
                "roi_pct": w0["roi_pct"],
                "wow_pct": wow,
            },
        })

    return {
        "meta": {
            "market": market_name,
            "market_slug": slug,
            "week_start": WEEKS[-1],
            "week_end": (REF_WEEK + timedelta(days=6)).isoformat(),
            "weeks": WEEKS,
            "generated_at": GENERATED_AT,
            "schema_version": SCHEMA_VERSION,
        },
        "market_summary": {"weekly": market_weekly, "headlines": headlines},
        "ces": ces,
        "followup": followup,
        "bucket1_fluctuations": bucket1,
        "no_bid_campaigns": no_bid,
        "seasonality_adjustments": seasonality,
        "levers": levers,
    }


def main():
    rng = random.Random(20260629)
    markets = [build_snapshot(rng, name, slug, defs, scale)
               for (name, slug, defs, scale) in MARKETS]
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": GENERATED_AT,
        "markets": markets,
    }
    with open(OUT, "w") as f:
        json.dump(bundle, f, indent=1)
    na = markets[0]["market_summary"]["weekly"][-1]["revenue"]
    print(f"wrote {OUT}")
    print(f"  markets: {[m['meta']['market'] for m in markets]}")
    print(f"  NA W0 revenue: ${na:,.0f}  (ref ~$615.4K)")
    print(f"  NA CEs: {len(markets[0]['ces'])}  bucket1: "
          f"{len(markets[0]['bucket1_fluctuations'])}  "
          f"no-bid: {markets[0]['no_bid_campaigns']['totals']['count']}")


if __name__ == "__main__":
    main()
