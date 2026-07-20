"""
Weekly Revenue & CVR Drop Alert — standalone test version (v2)

Format (per market):
    1) Top-level message: market header + scannable CE list with IDs
    2) Threaded reply per CE: full block (drivers + conditional Demand RCA + CVR RCA)

USAGE:
    # Auth once: gcloud auth application-default login
    # Export token:  export REVENUE_ALERT_SLACK_TOKEN="xoxb-..."

    # Dry-run (prints what would post):
    python revenue_drop_alert.py --dry-run

    # Real run, limited to one market with up to 5 firing CEs:
    python revenue_drop_alert.py --market "North America" --max-ces-per-market 5

    # Real run, all markets:
    python revenue_drop_alert.py
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import urllib.parse
from itertools import permutations
from math import factorial
from pathlib import Path

import pandas as pd
import requests
from google.cloud import bigquery


# =============================================================================
# CONFIG
# =============================================================================

PROJECT_ID = "headout-analytics"
SQL_FILE = Path(__file__).parent / "sql" / "ce_revenue_cvr_drop.sql"

TEST_CHANNEL_NAME = "#revenue-alert-testing"
TEST_CHANNEL_ID = "C0B6U94PGJ0"

# =============================================================================
# PER-MARKET ELIGIBILITY FLOORS
# A CE is in-scope only if its Pre-period revenue >= this market's floor.
# Adjust freely — purely hardcoded for simplicity. Markets not listed fall back
# to DEFAULT_MARKET_FLOOR.
# =============================================================================
MARKET_FLOORS: dict[str, float] = {
    # v1 launch: T1+T2 only, $1,000 floor across ALL markets. Defer Mid/Small
    # market relaxation (down to $500/$250 floors) to v2 once T1+T2 is validated.
    "Italy":                      1000,
    "North America":              1000,
    "France":                     1000,
    "Iberia":                     1000,
    "CSEE":                       1000,
    "United Kingdom":             1000,
    "Central Live Entertainment": 1000,
    "East Asia (JPN, SK, HK)":    1000,
    "Oceania":                    1000,
    "SEA (SIN + THA)":            1000,
    "Benelux":                    1000,
    "SEA (MLY + IND + VN)":       1000,
    "United Arab Emirates":       1000,
    "South America":              1000,
    "City Cards":                 1000,
    "Nordics":                    1000,
    "Egypt":                      1000,
    "Mexico & Central America":   1000,
    "Morocco":                    1000,
    "East Asia (CN, TW)":         1000,
    "GCC":                        1000,
}
DEFAULT_MARKET_FLOOR = 1000  # fallback for any market not in the dict above

# Minimum order-count guard — CEs with very few orders are noise-prone (1-2
# orders dropping to 0 looks dramatic but is meaningless). Applied per CE on
# Pre-period order count after the per-market revenue floor check.
MIN_PRE_ORDERS = 10

# Co-primary driver detection — when BOTH Traffic and CVR move significantly
# in the same direction as the revenue delta, we flag both as primary drivers
# AND render both Demand RCA + CVR RCA sub-sections (regardless of Shapley
# top-2 ranking). |raw factor change| threshold.
COPRIMARY_THRESHOLD = 0.30


# Revenue tier thresholds — (tier, min_pre, max_pre, drop_threshold, rise_threshold)
# Rises calibrated MUCH stricter than drops because revenue rises are inherently
# noisier — historical median WoW rise is 18% (T1), 29% (T2), 45% (T3). Setting
# rise thresholds at/below those values floods the alert. Each rise threshold
# below targets ~8–13% trigger rate (vs ~15–20% for drops), since rises are for
# learning (selective) rather than firefighting (high recall).
REVENUE_TIERS = [
    ("T1", 5000,    float("inf"), 0.20, 0.50),  # drops tightened from 15→20%
    ("T2", 1000,    5000,         0.30, 0.75),  # drops tightened from 25→30%
    ("T3", 250,     1000,         0.40, 1.00),  # T3 effectively unused at $1K floor
]

# CVR thresholds bucketed by Pre traffic — (bucket, min_pre_traffic, max_pre_traffic, drop_threshold, rise_threshold)
# Note: Large bucket drop threshold is intentionally tight (10%, just above 8%
# p50 noise) — hero CEs are high-visibility and even small CVR slips drive
# meaningful $ impact. Rise thresholds are bumped slightly above the drop side
# to keep rise alerts to ~8–12% trigger rate.
CVR_BUCKETS = [
    ("Large", 10000, float("inf"), 0.15, 0.20),  # drops tightened from 10→15%
    ("Mid",   2500,  10000,        0.25, 0.30),  # drops tightened from 20→25%
    ("Small", 500,   2500,         0.35, 0.40),  # drops tightened from 30→35%
]
CVR_MIN_TRAFFIC = 500

# Shapley factors
FACTORS = ["traffic", "cvr", "orders_per_converter", "aov", "completion_rate", "take_rate"]
FACTOR_LABELS = {
    "traffic":              "Traffic",
    "cvr":                  "CVR",
    "orders_per_converter": "Orders/User",
    "aov":                  "AOV",
    "completion_rate":      "CR",
    "take_rate":            "TR",
}

# Which factors get an RCA sub-section if they're in the top 2
RCA_FACTORS = {"traffic", "cvr"}

# Weekly (WoW) driver set + labels — the 5 factors shown in the WoW drivers
# table (Orders/User excluded). Labels spell out Completion / Take rate (vs the
# terse CR / TR chips used in the monthly layout).
WEEKLY_FACTORS = ["traffic", "cvr", "aov", "completion_rate", "take_rate"]
WEEKLY_FACTOR_LABELS = {
    "traffic":         "Traffic",
    "cvr":             "CVR",
    "aov":             "AOV",
    "completion_rate": "Completion",
    "take_rate":       "Take rate",
}

# Direction emoji thresholds — applied to signed % change
DIRECTION_DROP_EMOJI    = "🔻"   # change <= -5%
DIRECTION_FLAT_EMOJI    = "➖"   # -5% < change < +5%
DIRECTION_RISE_EMOJI    = "🔺"   # change >= +5%
DIRECTION_THRESHOLD     = 0.05


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("revenue_alert")


# =============================================================================
# NUMBER FORMATTING
# =============================================================================

def fmt_money(value: float) -> str:
    """Compact USD: $1.7K / $5.3K / $12.3M. 1 decimal for K/M, no decimals under $1K."""
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    abs_val = abs(value)
    if abs_val >= 1_000_000:
        return f"{sign}${abs_val/1_000_000:.1f}M"
    if abs_val >= 1_000:
        return f"{sign}${abs_val/1_000:.1f}K"
    return f"{sign}${abs_val:,.0f}"


def fmt_pct_signed(value: float, decimals: int = 1) -> str:
    """Signed percent: +12.3% / -45.0%. Pass a fraction (0.12 → +12.3%)."""
    if value is None:
        return "—"
    return f"{value*100:+.{decimals}f}%"


def fmt_pct_drop(value: float, decimals: int = 1) -> str:
    """Negative-formatted percent for a positive drop fraction (0.45 → -45.0%)."""
    return f"-{value*100:.{decimals}f}%"


def fmt_pct_contrib(value: float) -> str:
    """Contribution % — 0 decimals: 62%."""
    return f"{value:.0f}%"


def fmt_cvr(value: float) -> str:
    """CVR as 2-decimal %: 4.20%."""
    if value is None:
        return "—"
    return f"{value*100:.2f}%"


def fmt_count(value: float) -> str:
    """User counts: K shorthand, 1 decimal — 12.4K / 950."""
    if value is None:
        return "—"
    if value >= 1_000:
        return f"{value/1_000:.1f}K"
    return f"{value:,.0f}"


def direction_emoji(signed_change_fraction: float) -> str:
    """Return 🔻/➖/🔺 based on signed change."""
    if signed_change_fraction <= -DIRECTION_THRESHOLD:
        return DIRECTION_DROP_EMOJI
    if signed_change_fraction >= DIRECTION_THRESHOLD:
        return DIRECTION_RISE_EMOJI
    return DIRECTION_FLAT_EMOJI


def fmt_date_range(start, end) -> str:
    """Compact human date range, collapsing month when start/end share one.
    Examples: 'May 18 – 24'  /  'Apr 28 – May 4'."""
    s = pd.to_datetime(start)
    e = pd.to_datetime(end)
    if s.month == e.month and s.year == e.year:
        return f"{s.strftime('%b %-d')} – {e.strftime('%-d')}"
    return f"{s.strftime('%b %-d')} – {e.strftime('%b %-d')}"


# Omni CE dashboard. The dashboard is pre-configured with "Compare to: Previous
# Period", so providing just the Post window's dates is enough — Omni computes
# the comparison week automatically.
OMNI_DASHBOARD_URL = "https://headout.omniapp.co/dashboards/5368ab53"


def build_omni_dashboard_link(ce_id, post_period_start, post_period_end) -> str:
    """
    Build the Omni CE dashboard deep-link with the CE ID and Post-period date
    range pre-filtered. The dashboard's "Previous Period" comparison handles
    the Pre week automatically.

    Filter keys (`f--iv8lWOuS`, `f--uvd3KWWJ`) are Omni-internal stable IDs;
    the CE ID filter and date range filter for the dashboard, respectively.
    """
    ce_filter = {"values": [str(ce_id)]}

    # Omni's BETWEEN is end-exclusive, so right_side = post_end + 1 day.
    # (Example URL with post=May 18-24 has right_side="2026-05-25".)
    post_start_dt   = pd.to_datetime(post_period_start)
    post_end_plus_1 = pd.to_datetime(post_period_end) + pd.Timedelta(days=1)

    date_filter = {
        "kind":                   "BETWEEN",
        "left_side":              post_start_dt.strftime("%Y-%m-%d"),
        "right_side":             post_end_plus_1.strftime("%Y-%m-%d"),
        "ui_type":                "BETWEEN",
        "offset_interval_string": None,
    }

    params = {
        "f--iv8lWOuS": json.dumps(ce_filter,   separators=(",", ":")),
        "f--uvd3KWWJ": json.dumps(date_filter, separators=(",", ":")),
    }
    return f"{OMNI_DASHBOARD_URL}?{urllib.parse.urlencode(params)}"


# =============================================================================
# BIGQUERY
# =============================================================================

def run_query(sql_path: Path) -> pd.DataFrame:
    log.info("Loading SQL from %s", sql_path)
    sql = sql_path.read_text()
    client = bigquery.Client(project=PROJECT_ID)
    log.info("Running BigQuery (project=%s)…", PROJECT_ID)
    df = client.query(sql).to_dataframe()
    log.info("Returned %d rows", len(df))
    return df


# =============================================================================
# SHAPLEY DECOMPOSITION
# =============================================================================

def extract_factors(row: dict, orders_based_cvr: bool = False) -> dict[str, float]:
    """6-factor decomposition — used ONLY for the user-facing driver chips in
    messages. CVR here is converters/users (matches Omni's CVR card).
    NOT used inside Shapley anymore — see extract_factors_shapley below.

    orders_based_cvr (WEEKLY mode): when True, CVR is orders/users
    (count_orders/traffic) — the 6-factor CVR×Orders/User pair MERGED into a
    single factor — and orders_per_converter is neutralised to 1.0 (never shown
    in the weekly layout). This makes the 5 displayed weekly factors close the
    identity exactly: traffic × (orders/users) × (gross/orders) ×
    (completed/gross) × (revenue/completed) = revenue. Monthly callers leave it
    False and keep the unchanged 6-factor (converters-based CVR + Orders/User).
    """
    traffic              = row["traffic"]
    if orders_based_cvr:
        cvr                  = row["count_orders"] / row["traffic"]        if row["traffic"] > 0            else 0
        orders_per_converter = 1.0
    else:
        cvr                  = row["converters"] / row["traffic"]          if row["traffic"] > 0            else 0
        orders_per_converter = row["count_orders"] / row["converters"]     if row["converters"] > 0         else 0
    aov                  = row["gross_bookings"] / row["count_orders"]     if row["count_orders"] > 0       else 0
    completion_rate      = row["gross_bookings_completed"] / row["gross_bookings"] if row["gross_bookings"] > 0 else 0
    take_rate            = row["revenue"] / row["gross_bookings_completed"] if row["gross_bookings_completed"] > 0 else 0
    return dict(
        traffic=traffic,
        cvr=cvr,
        orders_per_converter=orders_per_converter,
        aov=aov,
        completion_rate=completion_rate,
        take_rate=take_rate,
    )


# 5-factor model used INTERNALLY for Shapley driver-pick. Ported from the
# ce-health skill (calc_shapley_decomposition / compute_shapley_for_ce in
# ~/.../skills/ce-health/ce_health.py:709–828). Identity:
#     net_revenue = traffic × (orders/users) × (gross/orders) × (completed/gross) × (revenue/completed)
# Telescopes exactly to actual revenue Δ (no unattributable residual) because
# every intermediate count cancels. Notably DROPS the orders_per_converter
# factor — the converter-based CVR + OPC pair was leaky (peak-volume mismatch
# inflated OPC's contribution and produced "112% of drop" artifacts).
# CVR here is ORDERS/USERS (different from the converters/users CVR shown to
# users in the message). This 5-factor model and its values are never surfaced
# in the message — only the primary-driver factor *name* is.
SHAPLEY_FACTORS = ["traffic", "cvr", "aov", "completion_rate", "take_rate"]


def extract_factors_shapley(row: dict) -> dict[str, float]:
    """5-factor values for the internal Shapley computation. CVR is orders/users
    (NOT converters/users). Small epsilon floors prevent div-by-zero for sparse
    CEs — matches ce-health skill's max(value, ε) pattern."""
    traffic = max(float(row["traffic"]), 0.001)
    orders  = float(row["count_orders"])
    gross   = float(row["gross_bookings"])
    gross_c = float(row["gross_bookings_completed"])
    revenue = float(row["revenue"])
    return {
        "traffic":         traffic,
        "cvr":             max(orders / traffic, 0.00001),
        "aov":             max(gross / orders if orders > 0 else 0, 0.01),
        "completion_rate": max(gross_c / gross if gross > 0 else 0, 0.00001),
        "take_rate":       max(revenue / gross_c if gross_c > 0 else 0, 0.00001),
    }


def decompose_change(pre: dict[str, float], post: dict[str, float]) -> dict[str, float]:
    """Generic Shapley decomposition — operates on whatever factor keys are in
    the input dicts (works for both 5- and 6-factor models)."""
    factor_keys = list(pre.keys())
    shapley = {f: 0.0 for f in factor_keys}
    for perm in permutations(factor_keys):
        for i, factor in enumerate(perm):
            term = 1.0
            for j, f in enumerate(perm):
                if j < i:
                    term *= post[f]
                elif j == i:
                    term *= post[f] - pre[f]
                else:
                    term *= pre[f]
            shapley[factor] += term
    n_perms = factorial(len(factor_keys))
    for factor in factor_keys:
        shapley[factor] /= n_perms
    return shapley


def factor_pct_changes(pre_f: dict[str, float], post_f: dict[str, float]) -> dict[str, float]:
    """Signed % change per factor, as a fraction."""
    out = {}
    for f in FACTORS:
        if pre_f[f] == 0:
            out[f] = 0.0
        else:
            out[f] = (post_f[f] - pre_f[f]) / pre_f[f]
    return out


# =============================================================================
# TRIGGER CHECKS
# =============================================================================

def revenue_movement(pre_revenue: float, post_revenue: float) -> tuple[str | None, float, str | None]:
    """
    Returns (direction, magnitude, tier).
      direction: "drop" if pre→post drop exceeds tier drop_threshold,
                 "rise" if pre→post rise exceeds tier rise_threshold,
                 None otherwise.
      magnitude: |fraction change| (positive number regardless of direction).
      tier:      the size tier the CE falls into (T1/T2/T3).
    """
    if pre_revenue <= 0:
        return None, 0.0, None
    signed_chg = (post_revenue - pre_revenue) / pre_revenue
    for tier, lo, hi, drop_t, rise_t in REVENUE_TIERS:
        if lo <= pre_revenue < hi:
            if signed_chg <= -drop_t:
                return "drop", abs(signed_chg), tier
            if signed_chg >= rise_t:
                return "rise", abs(signed_chg), tier
            return None, abs(signed_chg), tier
    return None, abs(signed_chg), None


def cvr_movement(pre_traffic: float, pre_cvr: float, post_cvr: float) -> tuple[str | None, float, str | None]:
    """Same shape as revenue_movement but for CVR. CVR check skipped when traffic too low."""
    if pre_traffic < CVR_MIN_TRAFFIC or pre_cvr <= 0:
        return None, 0.0, None
    signed_chg = (post_cvr - pre_cvr) / pre_cvr
    for bucket, lo, hi, drop_t, rise_t in CVR_BUCKETS:
        if lo <= pre_traffic < hi:
            if signed_chg <= -drop_t:
                return "drop", abs(signed_chg), bucket
            if signed_chg >= rise_t:
                return "rise", abs(signed_chg), bucket
            return None, abs(signed_chg), bucket
    return None, abs(signed_chg), None


# =============================================================================
# CORE PIPELINE
# =============================================================================

def analyze_ce_row(
    row: pd.Series,
    force_direction: str | None = None,
    skip_floor_check: bool = False,
    always: bool = False,
    weekly: bool = False,
) -> dict | None:
    """
    Compute the full alert dict for ONE CE row from the ce_revenue_cvr_drop.sql
    result. This is the single source of truth for the RCA analysis.

    Used by:
      - `evaluate_ces` (this script) — for weekly drop/rise alerts
      - `monthly_gap_alert.py` and `monthly_ce_alert.py` — to build the same
        "Drivers of Revenue Change" RCA thread reply for CEs in the gap-to-target
        table, regardless of whether they triggered a WoW alert.

    Args:
        row: pandas Series with the SQL columns (pre_revenue, post_revenue, …)
        force_direction: "drop" / "rise" / None.
            None  → natural detection (returns None if no significant movement).
            "drop"/"rise" → bypass trigger filter; mark revenue as triggered so
                  the standard RCA layout (drivers + Demand/CVR RCA) applies.
        skip_floor_check: if True, bypass the per-market eligibility floor.
            Use when the caller has its own selection logic (e.g. monthly
            gap-to-target rows that we want to analyze regardless of size).
        weekly: WoW (weekly_rca_helper.py) mode. When True:
            - The primary driver is picked from the 5 DISPLAYED factors
              (Traffic, CVR, AOV, Completion, Take rate — Orders/User excluded)
              using the direction-aware most-adverse-mover rule on the same %
              changes shown in the drivers table (NOT the internal 6/5-factor
              Shapley basis, which can contradict the displayed table).
            - Both Demand RCA and CVR RCA sub-sections are always rendered.
            Monthly callers leave weekly=False and get the unchanged 6-factor
            Shapley behavior.

    Returns:
        Alert dict if the CE qualifies (or force_direction is set);
        None otherwise.
    """
    pre_revenue  = float(row["pre_revenue"])
    if pre_revenue <= 0:
        return None  # can't compute multiplicative factors without Pre revenue

    post_revenue = float(row["post_revenue"])
    pre_traffic  = float(row["pre_traffic"])
    post_traffic = float(row["post_traffic"])
    pre_converters  = float(row["pre_users_order_completed"])
    post_converters = float(row["post_users_order_completed"])
    market = row.get("market") or "(unknown)"

    # Per-market eligibility floor (skippable for monthly use case)
    if not skip_floor_check:
        market_floor = MARKET_FLOORS.get(market, DEFAULT_MARKET_FLOOR)
        if pre_revenue < market_floor:
            return None

    rev_dir, rev_mag, rev_tier = revenue_movement(pre_revenue, post_revenue)
    pre_cvr  = pre_converters / pre_traffic   if pre_traffic  > 0 else 0.0
    post_cvr = post_converters / post_traffic if post_traffic > 0 else 0.0
    cvr_dir, cvr_mag, cvr_bucket = cvr_movement(pre_traffic, pre_cvr, post_cvr)

    # Determine direction
    if always:
        # Monthly RCA use case: always produce a full analysis for the requested
        # CE, regardless of thresholds. Direction follows the actual sign of the
        # revenue change. rev_triggered=True so the standard RCA layout renders.
        direction = "drop" if post_revenue <= pre_revenue else "rise"
        rev_triggered  = True
        cvr_triggered_ = (cvr_dir == direction)
    elif force_direction is not None:
        direction = force_direction
        # When forced, treat revenue as the trigger so the standard RCA layout
        # (drivers + Demand/CVR RCA sub-sections) renders. CVR-triggered only
        # if the CVR actually moved in the matching direction.
        rev_triggered  = True
        cvr_triggered_ = (cvr_dir == direction)
    else:
        # Natural detection: drops take priority over rises
        if rev_dir == "drop" or cvr_dir == "drop":
            direction = "drop"
        elif rev_dir == "rise" or cvr_dir == "rise":
            direction = "rise"
        else:
            return None  # no significant movement
        rev_triggered  = (rev_dir == direction)
        cvr_triggered_ = (cvr_dir == direction)

    rev_drop_pct = rev_mag  # "magnitude" of the active direction's metric
    cvr_drop_pct = cvr_mag

    # DISPLAYED factors always use the converters-based CVR (converting users /
    # traffic) — the CVR GMs see in the drivers table, Long-term Context, and the
    # CVR RCA. The orders/user CVR is used ONLY inside the Shapley primary-driver
    # calc below (extract_factors_shapley) and is never surfaced.
    pre_f = extract_factors({
        "traffic": pre_traffic, "converters": pre_converters,
        "count_orders": row["pre_count_orders"],
        "gross_bookings": row["pre_gross_bookings"],
        "gross_bookings_completed": row["pre_gross_bookings_completed"],
        "revenue": pre_revenue,
    }, orders_based_cvr=False)
    post_f = extract_factors({
        "traffic": post_traffic, "converters": post_converters,
        "count_orders": row["post_count_orders"],
        "gross_bookings": row["post_gross_bookings"],
        "gross_bookings_completed": row["post_gross_bookings_completed"],
        "revenue": post_revenue,
    }, orders_based_cvr=False)
    pct_changes = factor_pct_changes(pre_f, post_f)
    delta = post_revenue - pre_revenue

    # ---- Primary driver attribution (5-factor Shapley, internal) -----------
    # Internal-only: uses the 5-factor model (orders-based CVR) from the
    # ce-health skill so contributions telescope exactly to actual revenue
    # delta (no unattributable residual). 5-factor values are NEVER surfaced
    # to the user — only the primary-driver factor name is. User-facing driver
    # chips continue to show the 6-factor pct_changes (converters-based CVR).
    shapley_pre  = extract_factors_shapley({
        "traffic": pre_traffic,
        "count_orders": row["pre_count_orders"],
        "gross_bookings": row["pre_gross_bookings"],
        "gross_bookings_completed": row["pre_gross_bookings_completed"],
        "revenue": pre_revenue,
    })
    shapley_post = extract_factors_shapley({
        "traffic": post_traffic,
        "count_orders": row["post_count_orders"],
        "gross_bookings": row["post_gross_bookings"],
        "gross_bookings_completed": row["post_gross_bookings_completed"],
        "revenue": post_revenue,
    })
    contributions = decompose_change(shapley_pre, shapley_post)
    primary_factor = max(SHAPLEY_FACTORS, key=lambda f: abs(contributions[f]))
    primary_factors = [primary_factor]
    primary_attribution_mode = "shapley"  # always — 5-factor model is robust
    primary_value = abs(contributions[primary_factor] / delta * 100) if delta != 0 else 0.0
    top_2 = sorted(SHAPLEY_FACTORS, key=lambda f: -abs(contributions[f]))[:2]

    # Co-primary detection: when BOTH Traffic and CVR move significantly in
    # the delta's direction, surface both as primary AND force both RCA
    # sub-sections to render (regardless of Shapley top-2 ranking).
    if delta < 0:
        _same_dir = lambda c: c < 0
    elif delta > 0:
        _same_dir = lambda c: c > 0
    else:
        _same_dir = lambda c: True
    co_primary = (
        abs(pct_changes["traffic"]) >= COPRIMARY_THRESHOLD
        and abs(pct_changes["cvr"]) >= COPRIMARY_THRESHOLD
        and _same_dir(pct_changes["traffic"])
        and _same_dir(pct_changes["cvr"])
        and primary_attribution_mode == "shapley"  # only meaningful when Shapley is reliable
    )

    show_demand_rca = ("traffic" in top_2 and rev_triggered) or co_primary
    show_cvr_rca    = ("cvr" in top_2 and rev_triggered) or cvr_triggered_ or co_primary

    # ---- Weekly (WoW) overrides -------------------------------------------
    # The weekly alert shows 5 drivers (Traffic, CVR, AOV, Completion, Take rate;
    # Orders/User dropped). The primary driver(s) come from the INTERNAL 5-factor
    # Shapley (orders/user CVR) — the only use of orders/user. We surface driver
    # NAMES only: every factor whose |contribution| is ≥30% of the total absolute
    # contribution is called out, so a shared move reads "Primary drivers: CVR,
    # Traffic". No contribution % is ever shown. Both RCA sub-sections always render.
    if weekly:
        abs_contr = {f: abs(contributions[f]) for f in SHAPLEY_FACTORS}
        total_abs = sum(abs_contr.values())
        if total_abs > 0:
            ranked = sorted(SHAPLEY_FACTORS, key=lambda f: -abs_contr[f])
            primary_factors = [f for f in ranked if abs_contr[f] / total_abs >= 0.30] or [ranked[0]]
        else:
            primary_factors = ["traffic"]
        primary_factor = primary_factors[0]
        primary_attribution_mode = "shapley"
        primary_value = 0.0  # never shown in the weekly layout
        co_primary = False
        show_demand_rca = True
        show_cvr_rca = True

    # ---- Long-term Context verdict --------------------------------------
    def _chg(pre, post):
        if pre is None or pd.isna(pre) or float(pre) == 0:
            return None
        if post is None or pd.isna(post):
            return None
        return (float(post) - float(pre)) / float(pre)

    rev_cur_chg = _chg(pre_revenue, post_revenue)
    cvr_cur_chg = _chg(pre_cvr, post_cvr) if pre_cvr > 0 else None
    rev_ly_chg  = _chg(row.get("ly_pre_revenue"), row.get("ly_post_revenue"))
    cvr_ly_chg  = _chg(row.get("ly_pre_cvr"),     row.get("ly_post_cvr"))

    diffs = []
    if rev_triggered and rev_cur_chg is not None and rev_ly_chg is not None:
        diffs.append(abs(rev_cur_chg - rev_ly_chg))
    if cvr_triggered_ and cvr_cur_chg is not None and cvr_ly_chg is not None:
        diffs.append(abs(cvr_cur_chg - cvr_ly_chg))

    if not diffs:
        ltc_verdict = "limited"
    elif max(diffs) <= 0.10:
        ltc_verdict = "seasonal"
    else:
        ltc_verdict = "anomalous"

    return {
        "ce_id":         row["combined_entity_id"],
        "ce_name":       row.get("combined_entity_name") or "(unknown)",
        "market":        market,
        "pre_revenue":   pre_revenue,
        "post_revenue":  post_revenue,
        "rev_drop_pct":  rev_drop_pct,
        "rev_triggered": rev_triggered,
        "rev_tier":      rev_tier,
        "pre_cvr":       pre_cvr,
        "post_cvr":      post_cvr,
        "cvr_drop_pct":  cvr_drop_pct,
        "cvr_triggered": cvr_triggered_,
        "cvr_bucket":    cvr_bucket,
        "pre_traffic":   pre_traffic,
        "post_traffic":  post_traffic,
        "pct_changes":   pct_changes,
        "pre_factors":   {**pre_f, "revenue": pre_revenue},
        "post_factors":  {**post_f, "revenue": post_revenue},
        "weekly":        weekly,
        "primary_factor": primary_factor,
        "primary_factors": primary_factors,
        "primary_label":  (WEEKLY_FACTOR_LABELS if weekly else FACTOR_LABELS)[primary_factor],
        "primary_labels": [(WEEKLY_FACTOR_LABELS if weekly else FACTOR_LABELS)[f] for f in primary_factors],
        "primary_attribution_mode": primary_attribution_mode,
        "primary_value":  primary_value,
        "co_primary":     co_primary,
        "show_demand_rca": show_demand_rca,
        "show_cvr_rca":    show_cvr_rca,
        "ltc_verdict":     ltc_verdict,
        "direction":       direction,
        "raw_row":         row,
        "pre_period_start": row["pre_period_start"],
        "pre_period_end":   row["pre_period_end"],
        "post_period_start": row["post_period_start"],
        "post_period_end":  row["post_period_end"],
        "dollar_movement": abs(post_revenue - pre_revenue),
    }


def evaluate_ces(df: pd.DataFrame) -> list[dict]:
    """
    Per-row pass over the SQL result DataFrame. Returns the list of triggered
    alerts (drops or rises that cleared the per-tier thresholds). The heavy
    lifting (factor extraction, Shapley, LTC verdict, etc.) lives in
    `analyze_ce_row`, which is also called by the monthly alert scripts.
    """
    alerts: list[dict] = []
    excluded_by_floor = 0
    excluded_by_order_count = 0
    for _, row in df.iterrows():
        pre_revenue = float(row["pre_revenue"])
        market = row.get("market") or "(unknown)"
        if pre_revenue < MARKET_FLOORS.get(market, DEFAULT_MARKET_FLOOR):
            excluded_by_floor += 1
            continue
        # Min-order-count guard — prevents 1→0 order CEs from firing as huge drops
        if float(row["pre_count_orders"]) < MIN_PRE_ORDERS:
            excluded_by_order_count += 1
            continue
        alert = analyze_ce_row(row, skip_floor_check=True)
        if alert is not None:
            alerts.append(alert)
    n_drops = sum(1 for a in alerts if a["direction"] == "drop")
    n_rises = sum(1 for a in alerts if a["direction"] == "rise")
    log.info(
        "Evaluated %d CEs → %d below per-market floor → %d below min order count → %d drops + %d rises triggered",
        len(df), excluded_by_floor, excluded_by_order_count, n_drops, n_rises,
    )
    return alerts


# =============================================================================
# SLACK BLOCK KIT — MESSAGE BUILDERS
# =============================================================================

def build_ce_top_level_blocks(alert: dict) -> list[dict]:
    """
    Top-level message for ONE CE — the "headline".
    Each CE becomes its own top-level message in the channel so GMs can use
    its thread for per-CE discussion (Slack threads don't nest, so this is
    the only way to give each CE its own discussion space).

    Layout:
      1. header     — big bold "🔴 CE Name · CE 1234"
      2. section    — revenue line + primary driver one-liner
    """
    a = alert
    direction = a["direction"]

    # Title emoji — direction-aware:
    #   drops:  🔴 (revenue dropped) / 🟡 (only CVR dropped)
    #   rises:  🟢 (any positive movement — one color suffices, vs. drops where
    #           the rev-vs-CVR distinction is more operationally important)
    if direction == "drop":
        title_emoji = "🔴" if a["rev_triggered"] else "🟡"
    else:  # rise
        title_emoji = "🟢"

    # Title — backticked ID + bold name + L7D scope label (inline, replaces
    # the old standalone calendar-emoji line; reduces vertical noise per CE).
    title_line = (
        f"{title_emoji}  `[{a['ce_id']}]`  *{a['ce_name']}*  "
        f"|  _L7D vs Prev 7D_"
    )

    blocks: list[dict] = []

    # Date range is intentionally NOT shown in the top-level message — it's
    # the same week on every CE message for a given Monday run (redundant), and
    # the Omni link's URL params encode the exact dates for anyone who needs
    # them. Pre/Post are conveyed by the "→" arrow in each metric line.

    # --- Revenue line — bold IF revenue triggered ---------------------------
    rev_pct_signed = (a["post_revenue"] - a["pre_revenue"]) / a["pre_revenue"] if a["pre_revenue"] else 0
    if a["rev_triggered"]:
        revenue_line = (
            f"*Revenue:* {fmt_money(a['pre_revenue'])} → {fmt_money(a['post_revenue'])} "
            f"*({fmt_pct_signed(rev_pct_signed, 1)})*"
        )
    else:
        revenue_line = (
            f"Revenue: {fmt_money(a['pre_revenue'])} → {fmt_money(a['post_revenue'])} "
            f"({fmt_pct_signed(rev_pct_signed, 1)})"
        )

    # --- CVR line — bold IF CVR triggered; omit if traffic too low ----------
    # Threshold matches CVR_MIN_TRAFFIC (500) — below that CVR is too noisy
    # to be informative; showing "0.00% → 0.00%" would be misleading.
    cvr_line: str | None = None
    if a["pre_traffic"] >= CVR_MIN_TRAFFIC and a["pre_cvr"] > 0:
        cvr_pct_signed = (a["post_cvr"] - a["pre_cvr"]) / a["pre_cvr"] if a["pre_cvr"] else 0
        if a["cvr_triggered"]:
            cvr_line = (
                f"*CVR:* {fmt_cvr(a['pre_cvr'])} → {fmt_cvr(a['post_cvr'])} "
                f"*({fmt_pct_signed(cvr_pct_signed, 1)})*"
            )
        else:
            cvr_line = (
                f"CVR: {fmt_cvr(a['pre_cvr'])} → {fmt_cvr(a['post_cvr'])} "
                f"({fmt_pct_signed(cvr_pct_signed, 1)})"
            )

    # --- Primary driver — only for revenue-triggered alerts -----------------
    # (For CVR-only alerts, CVR IS the obvious driver; no need to repeat.)
    primary_line: str | None = None
    if a["rev_triggered"]:
        if a["primary_attribution_mode"] == "shapley":
            # Drop the contribution % (stakeholders found "105% of drop" confusing).
            # Show co-primary when both Traffic AND CVR moved significantly.
            if a.get("co_primary"):
                primary_line = f"⭐  *Primary drivers:* Traffic & CVR"
            else:
                primary_line = f"⭐  *Primary driver:* {a['primary_label']}"
        else:
            # Raw-mode fallback (sparse Mixpanel) — keep factor % change as the
            # only meaningful signal in this regime.
            primary_change = a["pct_changes"][a["primary_factor"]]
            primary_line = (
                f"⭐  *Primary mover:* {a['primary_label']} "
                f"_(factor change: {fmt_pct_signed(primary_change, 0)})_"
            )

    # --- Omni dashboard deep-link -------------------------------------------
    omni_url = build_omni_dashboard_link(
        a["ce_id"], a["post_period_start"], a["post_period_end"]
    )
    omni_line = f"📊  <{omni_url}|Omni dashboard>"

    # --- Significance callout — direction-aware, sits on its own line --------
    # "Significant" clarifies that we only flag movements above our tier
    # thresholds (answers "why aren't you calling out the small 9% move here?").
    # Direction emoji: 📉 (drop) / 📈 (rise) reinforces the direction.
    if direction == "drop":
        dir_emoji = "📉"
        dir_word = "drop"
    else:
        dir_emoji = "📈"
        dir_word = "rise"

    if a["rev_triggered"] and a["cvr_triggered"]:
        metric_text = "Revenue & CVR"
    elif a["rev_triggered"]:
        metric_text = "Revenue"
    else:
        metric_text = "CVR"
    trigger_callout = f"{dir_emoji}  *Significant {metric_text} {dir_word}*"

    parts = [title_line, trigger_callout, "", revenue_line]
    if cvr_line:
        parts.append(cvr_line)
    if primary_line:
        parts.append("")
        parts.append(primary_line)
    parts.append("")
    parts.append(omni_line)

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(parts)}})
    return blocks


def _render_wow_table(headers: list[str], rows: list[list[str]]) -> str:
    """Monospace table with dynamic column widths — the exact renderer behind the
    approved weekly WoW drivers / Long-term Context tables (header row, a `─`
    separator sized to the header, then the body), wrapped in a code fence."""
    def _trunc(s, w):
        s = str(s)
        return s if len(s) <= w else s[: w - 1] + "…"
    n = len(headers)
    caps = [28] + [22] * (n - 1)
    widths = [
        min(caps[j], max([len(_trunc(headers[j], caps[j]))]
                         + [len(_trunc(r[j], caps[j])) for r in rows] or [0]))
        for j in range(n)
    ]
    def fr(cells):
        return "  ".join(_trunc(c, widths[j]).ljust(widths[j]) for j, c in enumerate(cells)).rstrip()
    line = fr(headers)
    sep = "─" * len(line)
    return "```\n" + line + "\n" + sep + "\n" + "\n".join(fr(r) for r in rows) + "\n```"


def _build_wow_drivers_text(a: dict) -> str:
    """Weekly 'Drivers of Revenue Change' section — the 5-factor
    `Driver | W-1 | W0 | Δ%` table (Traffic, CVR, AOV, Completion, Take rate),
    all user-based, + the direction-aware ⭐ primary driver. No Orders/User row.
    """
    pre_f, post_f, pct = a["pre_factors"], a["post_factors"], a["pct_changes"]
    rows = [
        ["Traffic",    fmt_count(pre_f["traffic"]),          fmt_count(post_f["traffic"]),          fmt_pct_signed(pct["traffic"], 1)],
        ["CVR",        fmt_cvr(pre_f["cvr"]),                 fmt_cvr(post_f["cvr"]),                 fmt_pct_signed(pct["cvr"], 1)],
        ["AOV",        fmt_money(pre_f["aov"]),               fmt_money(post_f["aov"]),               fmt_pct_signed(pct["aov"], 1)],
        ["Completion", _fmt_pct1(pre_f["completion_rate"]),   _fmt_pct1(post_f["completion_rate"]),   fmt_pct_signed(pct["completion_rate"], 1)],
        ["Take rate",  _fmt_pct1(pre_f["take_rate"]),         _fmt_pct1(post_f["take_rate"]),         fmt_pct_signed(pct["take_rate"], 1)],
    ]
    tbl = _render_wow_table(["Driver", "W-1", "W0", "Δ%"], rows)
    labels = a.get("primary_labels") or [a["primary_label"]]
    if len(labels) > 1:
        primary = f"⭐  *Primary drivers:* {', '.join(labels)}"
    else:
        primary = f"⭐  *Primary driver:* {labels[0]}"
    return "*Drivers of Revenue Change* _(WoW)_\n" + tbl + f"\n{primary}"


def build_ce_thread_detail_blocks(alert: dict, recent_label: str = "L4W avg",
                                  weekly: bool = False) -> list[dict]:
    """
    Thread reply for ONE CE — the detailed RCA, attached as a thread reply
    to the CE's top-level message.

    `recent_label` labels the Long-term Context "recent baseline" column —
    "L4W avg" for the weekly alert, "L3M avg" for the monthly alert.

    Monthly layout (weekly=False, default):
      1. section    — drivers table (6 factor chips) + Shapley contribution %
      2. section    — Long-term Context (L3M avg + LY Pre/Post)
      3. section    — Demand RCA (only if Traffic in top-2)
      4. section    — CVR RCA (only if CVR in top-2, or CVR-only triggered)
      5. context    — "Deeper RCA under development" footer

    Weekly layout (weekly=True) — the approved WoW thread reply:
      1. section    — `Driver | W-1 | W0 | Δ%` table (5 drivers) + ⭐ primary
      2. section    — Long-term Context with a W0 column
      3. section    — Demand RCA (paid/organic USERS + channel mix)
      4. section    — CVR RCA (user-based CVR + funnel steps)
      (no dev footer — the helper appends the thick separator instead)
    """
    a = alert
    row = a["raw_row"]
    blocks: list[dict] = []

    if weekly:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": _build_wow_drivers_text(a)}})
        blocks.append({"type": "section", "text": {"type": "mrkdwn",
                       "text": _build_longterm_context_text(row, a, recent_label, weekly=True)}})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": _build_demand_rca_text(row, a)}})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": _build_cvr_rca_text(row, a)}})
        return blocks

    # --- Drivers table + Shapley primary driver (always shown) ---------------
    pct = a["pct_changes"]
    def driver_chip(f_key: str) -> str:
        v = pct[f_key]
        return f"{direction_emoji(v)} {FACTOR_LABELS[f_key]} *{fmt_pct_signed(v, 1)}*"

    # Orders/User intentionally omitted — not surfaced anywhere in the alert.
    driver_row1 = f"{driver_chip('traffic')}   {driver_chip('cvr')}   {driver_chip('aov')}"
    driver_row2 = f"{driver_chip('completion_rate')}   {driver_chip('take_rate')}"

    # Primary driver wording — Shapley mode drops the contribution % entirely
    # (stakeholder feedback: "112% of rise" was confusing). Co-primary surfaces
    # both Traffic & CVR when both moved significantly in the same direction.
    if a["primary_attribution_mode"] == "shapley":
        if a.get("co_primary"):
            primary_line = f"⭐  *Primary drivers:* Traffic & CVR"
        else:
            primary_line = f"⭐  *Primary driver:* {a['primary_label']}"
    else:
        primary_line = (
            f"⭐  *Primary mover:* {a['primary_label']} "
            f"_(factor change: {fmt_pct_signed(a['primary_value'], 1)})_"
        )

    drivers_text = (
        "*Drivers of Revenue Change*\n\n"
        f"{driver_row1}\n{driver_row2}\n\n"
        f"{primary_line}"
    )
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": drivers_text}})

    # --- Long-term Context (L4W avg + LY same-week comparison) ---------------
    # Always shown — gives GMs seasonal & baseline context to interpret the
    # WoW change. Heading carries a verdict tag (Seasonal / Anomalous /
    # Limited Data). NULL values (new CEs without LY data) render as "N/A".
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": _build_longterm_context_text(row, a, recent_label)},
    })

    # --- Demand RCA (conditional) --------------------------------------------
    if a["show_demand_rca"]:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": _build_demand_rca_text(row, a)},
        })

    # --- CVR RCA (conditional) -----------------------------------------------
    if a["show_cvr_rca"]:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": _build_cvr_rca_text(row, a)},
        })

    # --- Footer (RCA under development) --------------------------------------
    blocks.append(RCA_UNDER_DEV_FOOTER)
    return blocks


# Footer shown at the bottom of each CE's thread reply.
RCA_UNDER_DEV_FOOTER = {
    "type": "context",
    "elements": [{
        "type": "mrkdwn",
        "text": "🛠️  _Deeper Demand & CVR RCA modules under development — RCA skill coming soon_",
    }],
}


def _build_demand_rca_text(row: pd.Series, a: dict) -> str:
    pre_total   = float(row["pre_traffic"])
    post_total  = float(row["post_traffic"])
    pre_paid    = float(row["pre_traffic_paid"])
    post_paid   = float(row["post_traffic_paid"])
    pre_org     = float(row["pre_traffic_organic"])
    post_org    = float(row["post_traffic_organic"])
    pre_goog    = float(row["pre_traffic_google"])
    post_goog   = float(row["post_traffic_google"])
    pre_msft    = float(row["pre_traffic_microsoft"])
    post_msft   = float(row["post_traffic_microsoft"])
    pre_other   = float(row["pre_traffic_paid_other"])
    post_other  = float(row["post_traffic_paid_other"])

    def pct(p, c):
        if p == 0:
            return 0.0
        return (c - p) / p

    # Find biggest paid-channel mover (by absolute change in users) to mark with arrow
    paid_movers = {
        "Google Ads":    (pre_goog, post_goog),
        "Microsoft Ads": (pre_msft, post_msft),
        "Other Paid":    (pre_other, post_other),
    }

    paid_change = post_paid - pre_paid
    paid_arrow = ""
    if a["rev_triggered"] and abs(paid_change) > abs(post_org - pre_org):
        paid_arrow = "   ← driver"

    lines = [
        "🚦  *Demand RCA*",
        "",
        "*Paid vs Organic (unique users)*",
        f"•  Total:    {fmt_count(pre_total)} → {fmt_count(post_total)}   *({fmt_pct_signed(pct(pre_total, post_total), 1)})*",
        f"•  Paid:      {fmt_count(pre_paid)} → {fmt_count(post_paid)}   *({fmt_pct_signed(pct(pre_paid, post_paid), 1)})*{paid_arrow}",
        f"•  Organic:  {fmt_count(pre_org)} → {fmt_count(post_org)}   *({fmt_pct_signed(pct(pre_org, post_org), 1)})*",
        "",
        "*Channel Mix (paid users)*",
        f"•  Google Ads:     {fmt_count(pre_goog)} → {fmt_count(post_goog)}   *({fmt_pct_signed(pct(pre_goog, post_goog), 1)})*",
        f"•  Microsoft Ads:  {fmt_count(pre_msft)} → {fmt_count(post_msft)}   *({fmt_pct_signed(pct(pre_msft, post_msft), 1)})*",
        f"•  Other Paid:     {fmt_count(pre_other)} → {fmt_count(post_other)}   *({fmt_pct_signed(pct(pre_other, post_other), 1)})*",
    ]
    return "\n".join(lines)


LTC_VERDICT_LABELS = {
    "seasonal":  "🟢 Seasonal Pattern",
    "anomalous": "🔴 Anomalous",
    "limited":   "⚪ Limited Data",
}


# Long-term Context driver rows — (label, factor_key or "revenue", formatter, is_extensive).
# `is_extensive` metrics (Revenue, Traffic) are shown as an AVG WEEKLY value in the
# L4W column (pooled 4-week total ÷ 4); ratio metrics are scale-free so shown as-is.
def _fmt_pct1(v):  # 1-decimal percent for CR / Take Rate
    return f"{v * 100:.1f}%"

LTC_DRIVER_ROWS = [
    # NOTE: Orders/User intentionally excluded — not surfaced anywhere.
    ("Revenue",     "revenue",              fmt_money,   True),
    ("Traffic",     "traffic",              fmt_count,   True),
    ("CVR",         "cvr",                  fmt_cvr,     False),
    ("AOV",         "aov",                  fmt_money,   False),
    ("Completion",  "completion_rate",      _fmt_pct1,   False),
    ("Take Rate",   "take_rate",            _fmt_pct1,   False),
]


def _ltc_factors(row: pd.Series, prefix: str, orders_based_cvr: bool = False) -> dict | None:
    """Build the 6-factor dict (+revenue) for one period from raw SQL columns.
    `prefix` is 'l4w_', 'ly_pre_', or 'ly_post_'. Returns None if the period has
    no data (CE didn't exist / no activity) so callers can render N/A.

    orders_based_cvr (WEEKLY): CVR = orders/users, matching the weekly drivers
    table so the Long-term Context CVR column is on the same basis."""
    def g(col):
        v = row.get(prefix + col)
        return 0.0 if v is None or pd.isna(v) else float(v)

    revenue = g("total_revenue") if prefix == "l4w_" else g("revenue")
    traffic     = g("traffic")
    converters  = g("converters")
    count_orders = g("count_orders")
    gross       = g("gross_bookings")
    gross_c     = g("gross_bookings_completed")

    if traffic == 0 and revenue == 0 and count_orders == 0:
        return None

    factors = extract_factors({
        "traffic": traffic, "converters": converters,
        "count_orders": count_orders, "gross_bookings": gross,
        "gross_bookings_completed": gross_c, "revenue": revenue,
    }, orders_based_cvr=orders_based_cvr)
    factors["revenue"] = revenue
    return factors


def _build_longterm_context_text(row: pd.Series, a: dict, recent_label: str = "L4W avg",
                                 weekly: bool = False) -> str:
    """
    Build the 'Long-term Context' monospace table — a full driver matrix:
    L4W avg + LY same-week Pre/Post for Revenue and ALL 6 revenue drivers.
    LY Post cell carries the YoY %change (LY Pre → LY Post).

    Format:
        *Long-term Context — 🟢 Seasonal Pattern*

        Metric        L4W avg    LY Pre     LY Post
        Revenue       $5.2K      $4.9K      $3.4K (-30.6%)
        Traffic       2.4K       2.3K       2.1K (-8.7%)
        CVR           3.50%      3.51%      2.95% (-16.0%)
        AOV           $186       $180       $185 (+2.8%)
        Completion    95.0%      94.0%      91.0% (-3.2%)
        Take Rate     27.9%      28.0%      27.6% (-1.4%)
    """
    # CVR in the Long-term Context is always converters/traffic (the displayed
    # basis) — never the internal orders/user Shapley CVR.
    l4w     = _ltc_factors(row, "l4w_",     orders_based_cvr=False)
    ly_pre  = _ltc_factors(row, "ly_pre_",  orders_based_cvr=False)
    ly_post = _ltc_factors(row, "ly_post_", orders_based_cvr=False)

    def cell(period, key, fmt, is_extensive, divide_by=1):
        if period is None:
            return "N/A"
        val = period[key]
        if is_extensive and divide_by != 1:
            val = val / divide_by
        return fmt(val)

    def ly_post_cell(key, fmt):
        if ly_post is None:
            return "N/A"
        post_str = fmt(ly_post[key])
        if ly_pre is None or ly_pre[key] == 0:
            return post_str
        chg = (ly_post[key] - ly_pre[key]) / ly_pre[key]
        return f"{post_str} ({fmt_pct_signed(chg, 1)})"

    # Weekly layout: dynamic-width table with a W0 column up front (the approved
    # WoW Long-term Context). W0 = the post-week's own value for each metric.
    if weekly:
        w0 = a["post_factors"]
        rows = []
        for label, key, fmt, is_extensive in LTC_DRIVER_ROWS:
            w0_str     = fmt(w0[key])
            l4w_str    = cell(l4w, key, fmt, is_extensive, divide_by=4 if is_extensive else 1)
            ly_pre_str = cell(ly_pre, key, fmt, is_extensive, divide_by=1)
            ly_post_str = ly_post_cell(key, fmt)
            rows.append([label, w0_str, l4w_str, ly_pre_str, ly_post_str])
        table = _render_wow_table(["Metric", "W0", recent_label, "LY Pre", "LY Post"], rows)
        verdict_label = LTC_VERDICT_LABELS.get(a.get("ltc_verdict", "limited"), LTC_VERDICT_LABELS["limited"])
        return f"*Long-term Context — {verdict_label}*\n{table}"

    header = f"{'Metric':<13}{recent_label:<11}{'LY Pre':<11}{'LY Post':<20}"
    table_lines = [header]
    for label, key, fmt, is_extensive in LTC_DRIVER_ROWS:
        l4w_str     = cell(l4w, key, fmt, is_extensive, divide_by=4 if is_extensive else 1)
        ly_pre_str  = cell(ly_pre, key, fmt, is_extensive, divide_by=1)
        ly_post_str = ly_post_cell(key, fmt)
        table_lines.append(f"{label:<13}{l4w_str:<11}{ly_pre_str:<11}{ly_post_str:<20}")

    table = "```\n" + "\n".join(table_lines) + "\n```"
    verdict_label = LTC_VERDICT_LABELS.get(a.get("ltc_verdict", "limited"), LTC_VERDICT_LABELS["limited"])
    return f"*Long-term Context — {verdict_label}*\n\n{table}"


def _build_cvr_rca_text(row: pd.Series, a: dict) -> str:
    pre_traffic   = float(row["pre_traffic"])
    post_traffic  = float(row["post_traffic"])
    pre_lp        = float(row["pre_users_select_page_viewed"])
    post_lp       = float(row["post_users_select_page_viewed"])
    pre_co        = float(row["pre_users_checkout_started"])
    post_co       = float(row["post_users_checkout_started"])
    pre_oc        = float(row["pre_users_order_completed"])
    post_oc       = float(row["post_users_order_completed"])

    pre_lp2s  = pre_lp / pre_traffic   if pre_traffic   > 0 else 0
    post_lp2s = post_lp / post_traffic if post_traffic  > 0 else 0
    pre_s2c   = pre_co / pre_lp        if pre_lp        > 0 else 0
    post_s2c  = post_co / post_lp      if post_lp       > 0 else 0
    pre_c2o   = pre_oc / pre_co        if pre_co        > 0 else 0
    post_c2o  = post_oc / post_co      if post_co       > 0 else 0

    def step_chg(p, c):
        if p == 0:
            return 0
        return (c - p) / p

    lp2s_chg = step_chg(pre_lp2s, post_lp2s)
    s2c_chg  = step_chg(pre_s2c, post_s2c)
    c2o_chg  = step_chg(pre_c2o, post_c2o)

    # Mark biggest dropping step
    drops = {"LP2S": lp2s_chg, "S2C": s2c_chg, "C2O": c2o_chg}
    biggest_drop_step = min(drops, key=lambda k: drops[k])
    arrows = {k: ("   ← biggest step drop" if k == biggest_drop_step and drops[k] < -0.02 else "") for k in drops}

    overall_cvr_change = (a["post_cvr"] - a["pre_cvr"]) / a["pre_cvr"] if a["pre_cvr"] else 0

    lines = [
        "📉  *CVR RCA*",
        "",
        f"*CVR:*  {fmt_cvr(a['pre_cvr'])} → {fmt_cvr(a['post_cvr'])}   *({fmt_pct_signed(overall_cvr_change, 1)})*",
        "",
        "*Funnel Steps*",
        f"•  LP2S:   {fmt_cvr(pre_lp2s)} → {fmt_cvr(post_lp2s)}   *({fmt_pct_signed(lp2s_chg, 1)})*{arrows['LP2S']}",
        f"•  S2C:    {fmt_cvr(pre_s2c)}  → {fmt_cvr(post_s2c)}   *({fmt_pct_signed(s2c_chg, 1)})*{arrows['S2C']}",
        f"•  C2O:    {fmt_cvr(pre_c2o)} → {fmt_cvr(post_c2o)}   *({fmt_pct_signed(c2o_chg, 1)})*{arrows['C2O']}",
    ]
    return "\n".join(lines)


# =============================================================================
# SLACK POSTING
# =============================================================================

def slack_post(token: str, channel: str, blocks: list[dict], thread_ts: str | None = None,
               fallback_text: str = "Revenue & CVR Drop Alert") -> dict:
    payload = {
        "channel": channel,
        "blocks": blocks,
        "text": fallback_text,
        "username": "Revenue & CVR Drop Alert",
        "icon_emoji": ":rotating_light:",
    }
    if thread_ts:
        payload["thread_ts"] = thread_ts
    resp = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"},
        data=json.dumps(payload),
        timeout=15,
    )
    body = resp.json()
    if not body.get("ok"):
        log.error("Slack post failed: %s", body)
    return body


def slack_get_permalink(token: str, channel_id: str, ts: str) -> str | None:
    """Fetch the canonical permalink for a posted Slack message.
    Returns None on failure (logged as warning, not fatal)."""
    try:
        resp = requests.get(
            "https://slack.com/api/chat.getPermalink",
            headers={"Authorization": f"Bearer {token}"},
            params={"channel": channel_id, "message_ts": ts},
            timeout=10,
        )
        body = resp.json()
        if body.get("ok"):
            return body.get("permalink")
        log.warning("chat.getPermalink failed: %s", body.get("error"))
    except Exception as e:
        log.warning("chat.getPermalink exception: %s", e)
    return None


def build_market_summary_blocks(market: str, alerts_with_links: list[tuple[dict, str | None]]) -> list[dict]:
    """Single-section table-of-contents summary for a market's CEs.

    Per-CE line carries the same content shape stakeholders are used to from
    the legacy summary:
      Rev-triggered: 🔴 [id] name — -35% ($5.4K → $3.5K) · Primary driver: CVR · see thread ↗
      CVR-only:      🟡 [id] name — revenue held, CVR -15% · see thread ↗
      Rise:          🟢 [id] name — +44% ($5.0K → $7.2K) · Primary driver: Traffic · see thread ↗
      Co-primary:    🔴 [id] name — -35% ($5.4K → $3.5K) · Primary drivers: Traffic & CVR · see thread ↗
    """
    n = len(alerts_with_links)
    header = f"📋  *{market} — Weekly Drop & Rise Summary*\n{n} CEs flagged this week:"

    lines = []
    for alert, permalink in alerts_with_links:
        link_suffix = f"  ·  <{permalink}|see thread ↗>" if permalink else ""
        ce_prefix = f"`[{alert['ce_id']}]`  {alert['ce_name']}"

        if alert["direction"] == "drop":
            emoji = "🔴" if alert["rev_triggered"] else "🟡"
        else:  # rise
            emoji = "🟢"

        if not alert["rev_triggered"]:
            # CVR-only case (only ever 🟡 — direction is "drop" with rev not triggered)
            signed_cvr = -alert["cvr_drop_pct"] if alert["direction"] == "drop" else alert["cvr_drop_pct"]
            line = (
                f"{emoji}  {ce_prefix} — revenue held, "
                f"*CVR {fmt_pct_signed(signed_cvr, 0)}*{link_suffix}"
            )
        else:
            # Revenue triggered (drop or rise) — show revenue %, pre→post, and primary driver
            signed_rev = -alert["rev_drop_pct"] if alert["direction"] == "drop" else alert["rev_drop_pct"]
            rev_range = f"{fmt_money(alert['pre_revenue'])} → {fmt_money(alert['post_revenue'])}"

            # Primary driver label — handle co-primary
            if alert.get("co_primary"):
                primary_label_part = f"Primary drivers: *Traffic & CVR*"
            else:
                primary_label_part = f"Primary driver: *{alert['primary_label']}*"

            line = (
                f"{emoji}  {ce_prefix} — "
                f"*{fmt_pct_signed(signed_rev, 0)}*  _({rev_range})_  ·  "
                f"{primary_label_part}{link_suffix}"
            )

        lines.append(line)

    body = header + "\n\n" + "\n".join(lines)
    return [{"type": "section", "text": {"type": "mrkdwn", "text": body}}]


# =============================================================================
# ENTRY POINT
# =============================================================================

def _print_blocks_for_dry_run(blocks: list[dict]) -> None:
    for b in blocks:
        if b.get("type") == "header":
            text = b["text"]["text"]
            print()
            print("=" * 60)
            print(f"  {text}")
            print("=" * 60)
            print()
        elif b.get("type") == "section":
            print(b["text"]["text"])
            print()
        elif b.get("type") == "divider":
            print("─" * 60)
        elif b.get("type") == "context":
            for el in b.get("elements", []):
                if el.get("type") == "mrkdwn":
                    print(f"  {el['text']}")
            print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly Revenue & CVR Drop Alert — test runner")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip Slack posting; print formatted messages to stdout")
    parser.add_argument("--channel", default=TEST_CHANNEL_NAME,
                        help=f"Slack channel (default: {TEST_CHANNEL_NAME})")
    parser.add_argument("--market", default=None,
                        help="Filter to a single market (e.g., 'North America')")
    parser.add_argument("--max-ces-per-market", type=int, default=None,
                        help="Cap the number of CEs alerted per market (top by dollar drop)")
    args = parser.parse_args()

    df = run_query(SQL_FILE)
    if df.empty:
        log.warning("No rows returned from BigQuery — nothing to alert on")
        return

    alerts = evaluate_ces(df)
    if not alerts:
        log.info("No CEs crossed thresholds this run")
        return

    # Group by market, sort each market by dollar drop, optionally cap
    by_market: dict[str, list[dict]] = {}
    for a in alerts:
        by_market.setdefault(a["market"], []).append(a)
    for m in by_market:
        # Drops first, then rises (drops are urgent; rises are learning).
        # Within each direction, biggest dollar movement first.
        by_market[m].sort(
            key=lambda x: (0 if x["direction"] == "drop" else 1, -x["dollar_movement"])
        )
        if args.max_ces_per_market:
            by_market[m] = by_market[m][: args.max_ces_per_market]

    # Apply --market filter
    if args.market:
        if args.market not in by_market:
            log.warning("Market %r has no firing CEs. Available markets: %s",
                        args.market, sorted(by_market.keys()))
            return
        by_market = {args.market: by_market[args.market]}

    log.info("Markets with firing CEs: %d", len(by_market))

    token = os.environ.get("REVENUE_ALERT_SLACK_TOKEN")
    if not args.dry_run and not token:
        log.error("REVENUE_ALERT_SLACK_TOKEN env var not set. Pass --dry-run or export the token.")
        sys.exit(1)

    for market, market_alerts in by_market.items():
        log.info("Market %s: %d firing CEs → posting %d top-level + %d thread replies",
                 market, len(market_alerts), len(market_alerts), len(market_alerts))

        # Track (alert, permalink) per CE so we can post a market summary at end
        alerts_with_links: list[tuple[dict, str | None]] = []

        for ce_idx, alert in enumerate(market_alerts):
            top_blocks    = build_ce_top_level_blocks(alert)
            thread_blocks = build_ce_thread_detail_blocks(alert)

            if args.dry_run:
                print(f"\n========== CE {ce_idx + 1}/{len(market_alerts)} — {market} — TOP-LEVEL (CE {alert['ce_id']}) ==========\n")
                _print_blocks_for_dry_run(top_blocks)
                print(f"\n---------- CE {alert['ce_id']} — THREAD REPLY (RCA detail) ----------\n")
                _print_blocks_for_dry_run(thread_blocks)
                alerts_with_links.append((alert, None))  # placeholder for dry-run summary preview
                continue

            # 1) Post the CE's top-level "headline" message
            log.info("  → CE %s (%s): posting top-level headline", alert["ce_id"], alert["ce_name"])
            resp = slack_post(token, args.channel, top_blocks,
                              fallback_text=f"CE {alert['ce_id']} — {alert['ce_name']}")
            if not resp.get("ok"):
                log.warning("    ❌ Top-level post failed for CE %s: %s", alert["ce_id"], resp.get("error"))
                continue
            ce_ts = resp["ts"]
            channel_id = resp.get("channel")
            log.info("    ✅ Top-level posted: ts=%s", ce_ts)

            # Capture permalink for the end-of-run summary message
            permalink = slack_get_permalink(token, channel_id, ce_ts) if channel_id else None
            alerts_with_links.append((alert, permalink))

            time.sleep(0.6)  # Let the top-level surface before threading

            # 2) Post the RCA detail as a thread reply under that CE's top-level
            r = slack_post(token, args.channel, thread_blocks,
                           thread_ts=ce_ts,
                           fallback_text=f"RCA detail — CE {alert['ce_id']}")
            if r.get("ok"):
                log.info("    ✅ Thread reply posted: ts=%s", r.get("ts"))
            else:
                log.warning("    ❌ Thread reply failed: %s", r.get("error"))

            time.sleep(0.6)  # Respect Slack rate limits between CEs

        # --- After all CE messages for this market, post the summary ----------
        if alerts_with_links:
            summary_blocks = build_market_summary_blocks(market, alerts_with_links)
            if args.dry_run:
                print(f"\n========== MARKET SUMMARY — {market} ==========\n")
                _print_blocks_for_dry_run(summary_blocks)
            else:
                log.info("Posting market summary for %s (%d CEs) → %s",
                         market, len(alerts_with_links), args.channel)
                r = slack_post(token, args.channel, summary_blocks,
                               fallback_text=f"{len(alerts_with_links)} CEs flagged in {market} this week")
                if r.get("ok"):
                    log.info("  ✅ Summary posted: ts=%s", r.get("ts"))
                else:
                    log.warning("  ❌ Summary post failed: %s", r.get("error"))


if __name__ == "__main__":
    main()
