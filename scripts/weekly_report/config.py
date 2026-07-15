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
MAX_BYTES_BILLED = 30 * 1024 ** 3  # 30 GB cap per query (analytics-skill hygiene)

CE_STATS = f"`{BQ_PROJECT}.{BQ_DATASET}.combined_entity_stats`"
ADS_STATS = f"`{BQ_PROJECT}.{BQ_DATASET}.google_ads_campaign_stats`"
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
}

# --------------------------------------------------------------------------- #
# Window
# --------------------------------------------------------------------------- #
WEEKS_BACK = 12
MATURITY_DAYS = 3          # generate off data >= 3 days matured
YOY_LAG_DAYS = 364         # weekday-aligned year-over-year (52 * 7)
SCHEMA_VERSION = 1

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
# Fluctuation engine — POF gates (CM1/conv & RPC daily alert)
# --------------------------------------------------------------------------- #
POF = dict(
    baseline_window_days=28,
    baseline_excl_last_days=3,
    baseline_min_valid_days=14,
    baseline_dev_threshold=0.20,   # >= 20% deviation vs 28d baseline
    sdlw_threshold=0.25,           # +-25% same-day-last-week (short-term trigger)
    roll7_wow_threshold=0.25,      # +-25% 7d-rolling WoW (alternate trigger/evidence)
    persistence_threshold=0.15,    # 3-day persistence >= 15% (reported metric)
    # A qualifying day must also hold on a trailing-3-day smoothed basis: the
    # swing persists, not just spikes. Calibrated to the NA reference — at 0.15
    # a one-off up-day (e.g. Disneyland 2026-07-02) leaks in; 0.20 reproduces
    # exactly the 5 reference alerts and drops all single-day noise.
    persistence_smoothed_dev=0.20,
    cv_max=0.50,                   # coefficient of variation <= 0.50
    min_conv_per_day=10,           # >= 10 conversions/day
    min_clicks_35d=500,            # >= 500 clicks / trailing 35d
)

# --------------------------------------------------------------------------- #
# Fluctuation engine — CVR WoW signal
# --------------------------------------------------------------------------- #
CVR_WOW_DROP_THRESHOLD = 0.30   # CVR drop > 30% WoW
CVR_MIN_CLICKS_WK = 300         # >= 300 clicks/wk floor

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
VALIDATION_NA = {
    "week_start": "2026-06-29",
    "market_revenue_actuals": 615432,   # sum_revenue basis (plan reference)
    "no_bid_campaigns": 57,
    "no_bid_spend": 21705,
    "cm1_conv_alerts": [
        "High Roller",
        "Edge NYC",
        "Universal Studios Hollywood",
        "American Museum of Natural History",
        "Arte Museum New York",
    ],
    "cm1_conv_alert_count": 5,
    "cv_excluded": 0,
}


# --------------------------------------------------------------------------- #
# Notes backend (Google Sheet + Apps Script web app)
# --------------------------------------------------------------------------- #
NOTES_SHEET_ID = os.environ.get("WR_NOTES_SHEET_ID", "1hC_IAsJrlPcpFv5K49eRtcwgK6i_DkAt4ZvETxlK-s8")
NOTES_SCRIPT_URL = os.environ.get("WR_NOTES_SCRIPT_URL", "https://script.google.com/macros/s/AKfycbzyr4kiG4PW61490CoqEQjIreeCV_9eeb7amiDgZ9uqgORe4gDWSzUAjvx8CfNmp2vLmQ/exec")

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
def _monday(d: dt.date) -> dt.date:
    """Monday of the ISO week containing d."""
    return d - dt.timedelta(days=d.weekday())


def latest_complete_week(today: dt.date | None = None) -> dt.date:
    """
    Monday (week_start) of the most recent fully-complete week whose Sunday end
    is at least MATURITY_DAYS in the past.
    """
    today = today or dt.date.today()
    # Monday of the week that just ended before today's week.
    candidate = _monday(today) - dt.timedelta(days=7)
    # Push back until the Sunday end is >= MATURITY_DAYS matured.
    while (today - (candidate + dt.timedelta(days=6))).days < MATURITY_DAYS:
        candidate -= dt.timedelta(days=7)
    return candidate


def week_starts(w0_monday: dt.date, n: int = WEEKS_BACK) -> list[dt.date]:
    """The n Mondays ending at (and including) w0_monday, oldest first."""
    return [w0_monday - dt.timedelta(weeks=(n - 1 - i)) for i in range(n)]


def iso(d: dt.date) -> str:
    return d.isoformat()
