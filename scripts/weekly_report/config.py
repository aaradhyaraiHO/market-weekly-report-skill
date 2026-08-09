"""
Configuration + shared constants for the Weekly Market Report V1 data mart.

Worktree: wt-weekly-data. Fills the `meta`, `market_summary`, `ces`, `followup`,
and `bucket1_fluctuations` sections of the snapshot contract (see the master plan
at thoughts/shared/plans/2026-07-09-weekly-report-v1.md).

METRIC BASIS — all definitions follow the Headout analytics-skill canonical
references (business.md / marketing.md). Two explicit decisions (Aaradhya,
2026-07-09):
  1. REVENUE = sum_revenue_predicted (the skill's DEFAULT revenue metric), NOT
     the actuals sum_revenue the master plan originally specified. Predicted
     revenue nets out expected cancellations, so market-level numbers run
     ~5% below the plan's actuals reference (NA W0 ~$580K vs $615.4K). The
     revenue reference therefore no longer validates; the fluctuation engine
     (CM1/conv alerts) is basis-independent and remains the hard validation gate.
  2. AOV = GBV / orders (canonical), NOT revenue / orders.
All other metrics (TR, CVR, ROI, CM1) already match canon; see the provenance
block emitted by build_snapshot.py.
"""
from __future__ import annotations

import datetime as dt
import os

# --------------------------------------------------------------------------- #
# BigQuery
# --------------------------------------------------------------------------- #
BQ_PROJECT = "headout-analytics"
BQ_DATASET = "analytics_reporting"
MAX_BYTES_BILLED = 80 * 1024 ** 3  # 80 GB cap per query (SEA/CSEE-sized markets exceeded the old 40 GB; analytics-skill hygiene)

CE_STATS = f"`{BQ_PROJECT}.{BQ_DATASET}.combined_entity_stats`"
ADS_STATS = f"`{BQ_PROJECT}.{BQ_DATASET}.ads_campaign_stats`"
DIM_CE = f"`{BQ_PROJECT}.{BQ_DATASET}.dim_combined_entities`"
FCT_ORDERS = f"`{BQ_PROJECT}.{BQ_DATASET}.fct_orders`"
FCT_BOOKINGS = f"`{BQ_PROJECT}.{BQ_DATASET}.fct_bookings`"
MIXPANEL_FUNNEL = f"`{BQ_PROJECT}.{BQ_DATASET}.mixpanel_user_page_funnel_progression`"
INV_AVAIL = f"`{BQ_PROJECT}.{BQ_DATASET}.inventory_availability`"

# --------------------------------------------------------------------------- #
# Pilot markets  (slug -> business_market value)
# --------------------------------------------------------------------------- #
MARKETS = {
    "north_america": "North America",
    "italy": "Italy",
    "oceania": "Oceania",
    # fan-out (2026-07-20) — business_market strings verified against combined_entity_stats
    "france": "France",
    "united_kingdom": "United Kingdom",
    "iberia": "Iberia",
    "csee": "CSEE",
    "east_asia": "East Asia",
    "sea": "South East Asia",
    "uae": "United Arab Emirates",
    # MENA subdivisions (2026-07-27) — separate pilots, all alert to #mkt-mena-expansion-internal
    "gcc": "GCC",
    "north_africa": "North Africa",
    "rest_of_mea": "Rest of MEA",
}

# --------------------------------------------------------------------------- #
# Window
# --------------------------------------------------------------------------- #
WEEKS_BACK = 12
MATURITY_DAYS = 3          # generate off data >= 3 days matured
YOY_LAG_DAYS = 364         # weekday-aligned year-over-year (52 * 7)
SCHEMA_VERSION = 1
# Report week = SUNDAY -> SATURDAY (2026-08-03 decision; was Monday -> Sunday).
# One-day shift back so W0 carries 2 maturation days by the Monday run — weekend
# backfill isn't complete by Monday on a Mon–Sun week. All 12 weeks re-bucket on
# the new boundary every build (no 6-day transition week). SQL week-truncs use
# BQ_WEEK below; python-side boundaries all flow through _week_start().
WEEK_START_DAY = "SUNDAY"
BQ_WEEK = f"WEEK({WEEK_START_DAY})"
_WEEKDAY_OFFSET = {"MONDAY": 0, "SUNDAY": 1}[WEEK_START_DAY]  # days before Monday

# --------------------------------------------------------------------------- #
# Metric bases  (analytics-skill canon; revenue overridden to predicted)
# --------------------------------------------------------------------------- #
REVENUE_COL = "sum_revenue_predicted"   # decision 2026-07-09; skill default
CVR_BASIS = "paid_ads"                  # count_ad_conversions / count_ad_clicks

# --------------------------------------------------------------------------- #
# Validity gates  (master plan BigQuery facts — kept)
# --------------------------------------------------------------------------- #
CVR_MAX_PCT = 50.0
ROI_MIN_PCT = 0.0
ROI_MAX_PCT = 1000.0
WEEKLY_SPEND_FLOOR = 50.0   # ROI computed only where weekly spend >= $50

# --------------------------------------------------------------------------- #
# Fluctuation engine — CM1/conv & RPC swing gate
# --------------------------------------------------------------------------- #
# Simplified L3W-vs-W0 ratio comparison (2026-08-03) — replaces the daily POF
# engine (28d baseline + SDLW + CV + 3-day persistence). One pooled ratio over
# the report week (Sun–Sat) vs the prior 3 weeks; flags at >=35%. Volume floor
# is the standard weekly MIN_ORDERS_WK below.
FLUCTUATION_THRESHOLD = 0.35   # |change| >= 35% flags
FLUCTUATION_L3W_DAYS = 21      # comparison period: 21 days before the report week
# Sustained-shift requirement (2026-08-09). When True, a CE flags only if the SAME-direction
# move also cleared the threshold on the prior week's own W0-vs-L3W comparison — i.e. the
# level shifted and stayed shifted, rather than one week wobbling. Trades volume for
# flags that are still true next week.
# Sustained shift is a LABEL on each row, never a filter (2026-08-10). Filtering on it
# deleted brand-new moves — the opposite of early warning. Rows always show; `sustained`
# marks the ones that also cleared the threshold last week (a confirmed 2-week trend).
# Dollar floor on W0 Google-Search spend — the "enough money to be worth acting on" gate.
# The order floor alone lets $79 CEs through. Set 0 to disable.
FLUCTUATION_MIN_SPEND_W0 = 200.0

# --------------------------------------------------------------------------- #
# Fluctuation engine — CVR WoW signal
# --------------------------------------------------------------------------- #
CVR_WOW_DROP_THRESHOLD = 0.30   # CVR drop > 30% WoW
CVR_MIN_CLICKS_WK = 300         # >= 300 clicks/wk floor
MIN_ORDERS_WK = 10              # >= 10 orders in BOTH weeks for the weekly (WoW) paths —
                                # the weekly analog of the daily engine's min_conv_per_day=10;
                                # a ratio off <10 orders on either side is noise (2026-07-20)

# --------------------------------------------------------------------------- #
# Gray-zone (P2.3) — near-miss band around bucket triggers
# --------------------------------------------------------------------------- #
GRAY_ZONE_PP = 5.0              # within 5pp of a B1 ROI trigger / B2 CVR trigger

# --------------------------------------------------------------------------- #
# Recommendation
# --------------------------------------------------------------------------- #
SEASONALITY_ADJ_PCT = 0.15      # +-15% / 7d adjustment recommendation
PAID_CONTRIB_LOW_PCT = 30.0     # < 30% paid contribution -> "review - low paid"

# --------------------------------------------------------------------------- #
# tROAS / bid-change innocence check
# --------------------------------------------------------------------------- #
TROAS_LOOKBACK_DAYS = 10        # window before W0 to look for campaign tROAS changes
TROAS_FALLBACK_PCT = 135.0      # spend-weighted tROAS fallback where none set

# --------------------------------------------------------------------------- #
# NA validation references  (master plan; revenue on ACTUALS basis)
# --------------------------------------------------------------------------- #
# week_start is a SUNDAY, matching WEEK_START_DAY. It was 2026-06-29 (a MONDAY) — a
# leftover from the pre-2026-08-03 Mon→Sun convention. That silently broke `--validate`:
# combined_entity_stats buckets weeks on WEEK(SUNDAY), so every weekly lookup keyed on the
# Monday missed (BQ returns 06-28; the code asked for 06-29) and each CE came back all-None.
# Snapped to its own week-start, 2026-06-28 → 07-04, which shares 6 of 7 days with the
# original reference span (2026-08-08).
#
# ⚠ The cm1_conv_alerts list below is STILL STALE, for two independent reasons:
#   1. it was calibrated against the DAILY POF engine (28d baseline · ≥20% dev · SDLW ·
#      CV ≤0.50 · 3-day persistence), which no longer exists — CM1/conv now fires on a
#      single L3W-vs-W0 pooled ratio at ≥35%;
#   2. the reference span itself shifted by a day in the Mon→Sun move.
# So `--validate` will still report a MISMATCH until it is re-baselined against a fresh NA
# run. Kept for provenance, not as a passing gate. no_bid/revenue anchors below were
# always informational (validate_na never gated them).
VALIDATION_NA = {
    "week_start": "2026-06-28",
    "market_revenue_actuals": 615432,   # sum_revenue basis (plan reference, informational)
    "no_bid_campaigns": 57,             # original plan anchor (informational, not gated)
    "no_bid_spend": 21705,              # original plan anchor (informational, not gated)
    "cm1_conv_alerts": [                # GOOGLE-ONLY basis (2026-07-20 re-baseline)
        "High Roller",
        "Edge NYC",
        "Universal Studios Hollywood",
        "American Museum of Natural History",
    ],
    "cm1_conv_alert_count": 4,
}


# --------------------------------------------------------------------------- #
# Notes backend (Google Sheet + Apps Script web app)
# --------------------------------------------------------------------------- #
NOTES_SHEET_ID = os.environ.get("WR_NOTES_SHEET_ID", "1hC_IAsJrlPcpFv5K49eRtcwgK6i_DkAt4ZvETxlK-s8")
NOTES_SCRIPT_URL = os.environ.get("WR_NOTES_SCRIPT_URL", "https://script.google.com/macros/s/AKfycbyvXB69WxTM1p9qO4tQXxPfV28mkXOOiTKqW8J4SH2P_vtblTYd6bUQGJSb8HyLLGhOjA/exec")

# Market -> primary Slack channel for "Post to #channel" (id + display name).
# Channel IDs verified against the monthly-review market_channels mapping; the
# REVENUE_ALERT_SLACK_TOKEN bot must be invited to each channel it posts to.
NOTES_SLACK_CHANNELS = {
    "north_america": {"id": "CNSHDD2H1",   "name": "mkt-usa"},
    "italy":         {"id": "C045L2WQ79P", "name": "mkt-italy-switzerland-malta"},
    "oceania":       {"id": "CHKRLFDPU",   "name": "mkt-anz"},
}

# --------------------------------------------------------------------------- #
# Date helpers
# --------------------------------------------------------------------------- #
def _week_start(d: dt.date) -> dt.date:
    """Start (WEEK_START_DAY) of the report week containing d."""
    return d - dt.timedelta(days=(d.weekday() + _WEEKDAY_OFFSET) % 7)


_monday = _week_start  # legacy alias (pre Sun-Sat shift); do not use in new code


def latest_complete_week(today: dt.date | None = None) -> dt.date:
    """
    week_start of the most recent COMPLETE report week — i.e. the week that just
    ended (its last day has passed). Sun→Sat weeks: run on Monday and W0 ended the
    Saturday before yesterday, giving 2 maturation days. No further maturity
    pushback: data maturity is handled per-bucket where it matters (the
    Fluctuations bucket runs on the matured portion; see build_snapshot). §1
    headlines use business predicted revenue, which settles immediately.
    """
    today = today or dt.date.today()
    return _week_start(today) - dt.timedelta(days=7)


def latest_matured_week(today: dt.date | None = None) -> dt.date:
    """
    week_start of the most recent week whose last day is >= MATURITY_DAYS in the
    past. Used by the Fluctuations bucket for its 28-day ROI/spend context anchor
    and its all-unsettled fallback — the paid-attribution windows that must be
    fully settled.
    """
    today = today or dt.date.today()
    candidate = _week_start(today) - dt.timedelta(days=7)
    while (today - (candidate + dt.timedelta(days=6))).days < MATURITY_DAYS:
        candidate -= dt.timedelta(days=7)
    return candidate


def week_starts(w0_start: dt.date, n: int = WEEKS_BACK) -> list[dt.date]:
    """The n week_starts ending at (and including) w0_start, oldest first."""
    return [w0_start - dt.timedelta(weeks=(n - 1 - i)) for i in range(n)]


def iso(d: dt.date) -> str:
    return d.isoformat()
