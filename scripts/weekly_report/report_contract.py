"""Versioned metric operands and approved target evidence for both cadences.

Calendar windows and NULL policies remain explicit at each caller. This module
contains no queries, rendering, publishing, storage, or bucket classification.
"""
import datetime as dt
import math

CONTRACT_API_VERSION = 1
CONTRACT_VERSION = "report-metrics/2026-11-17"
OKR_IDS = ("grow_cumulative_pro_plus_ces", "launch_new_pro_plus_mature",
           "launch_new_pro_plus_emerging_growth", "grow_non_poi_gel_revenue_yoy")
AD_COSTS = ('sum_google_ads_spend', 'sum_google_split_ads_spend', 'sum_pmax_ads_spend',
    'sum_travel_ads_spend', 'sum_google_remarketing_ads_spend', 'sum_google_brand_ads_spend',
    'sum_microsoft_ads_spend', 'sum_microsoft_split_ads_spend',
    'sum_microsoft_brand_ads_spend', 'sum_microsoft_remarketing_ads_spend',
    'sum_facebook_ads_spend', 'sum_facebook_split_ads_spend',
    'sum_facebook_remarketing_ads_spend', 'sum_apple_ads_spend', 'sum_criteo_remarketing_ads_spend')
OTHER_COSTS = ('sum_coupon_discount', 'sum_wallet_credits', 'sum_affiliate_commission',
               'sum_creator_collab_costs', 'sum_creator_collab_coupon_costs')
BING_NULL_ZERO = frozenset(('sum_microsoft_brand_ads_spend', 'sum_microsoft_remarketing_ads_spend'))


def ad_cost_sql(*, null_policy):
    if null_policy not in ('bing_only', 'all_zero'):
        raise ValueError('Unknown cost NULL policy')
    return ' + '.join(f'COALESCE({c}, 0)' if null_policy == 'all_zero' or c in BING_NULL_ZERO
                      else c for c in AD_COSTS)


def _number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None

COMPANY_TARGETS = {
    3: {
        "grow_cumulative_pro_plus_ces": "500 CEs",
        "launch_new_pro_plus_mature": "55 CEs",
        "launch_new_pro_plus_emerging_growth": "35 CEs",
        "grow_non_poi_gel_revenue_yoy": "+100% YoY",
    },
    4: {
        "grow_cumulative_pro_plus_ces": "520 CEs",
        "launch_new_pro_plus_mature": "45 CEs",
        "launch_new_pro_plus_emerging_growth": "25 CEs",
        "grow_non_poi_gel_revenue_yoy": "+90% YoY",
    },
}

COMPANY_GEL_TARGET_SOURCE = {
    "source": "https://docs.google.com/spreadsheets/d/1vRgfr9jnefP7grYKa-zaSkUzCpT7pnah7UCkaZuz5Dg/edit?gid=1972760172",
    "source_tab": "H2 2026",
    "source_verified_on": "2026-11-02",
    "source_cells": {3: "F30", 4: "G30"},
}

def _market_gel_target(slug, market_name, report_date, allocations):
    """Return only a source-evidenced target at the measured market/quarter grain."""
    if (allocations.get('schema') != 'weekly-market-okr-targets/v1'
            or allocations.get('kr_id') != OKR_IDS[3]
            or allocations.get('unit') != 'pct_yoy'):
        return None
    source = allocations.get('source') or {}
    record = (allocations.get('markets') or {}).get(slug) or {}
    quarter = f'{report_date.year}-Q{(report_date.month - 1) // 3 + 1}'
    period = (record.get('periods') or {}).get(quarter) or {}
    value = _number(period.get('value'))
    raw = str(period.get('raw', ''))
    try:
        verified = dt.date.fromisoformat(source.get('verified_on', ''))
    except (ValueError, TypeError):
        return None
    if (record.get('grain') != 'market' or record.get('source_market') != market_name
            or not source.get('url') or not source.get('tab') or not source.get('kr_cell')
            or not period.get('cell') or verified > dt.datetime.now(dt.timezone.utc).date()
            or value is None or value <= 0 or not raw.endswith('%')
            or _number(raw[:-1]) != value):
        return None
    return {'market_slug': slug, 'quarter': quarter, 'grain': 'market',
            'value': value, 'unit': 'pct_yoy', 'source': source['url'],
            'source_tab': source['tab'], 'source_cell': period['cell'],
            'source_verified_on': source['verified_on']}



def gel_progress(*, cutoff, value, revenue_ly, target):
    """Central flowrev policy; count only completed Sunday–Saturday weeks.

    Callers must establish target grain/provenance before supplying target.
    This function never computes or replaces actual revenue/growth.
    """
    observed, baseline, approved = map(_number, (value, revenue_ly, target))
    if approved is None or approved <= 0:
        return {'status': 'Status unavailable', 'status_reason': 'verified_target_unavailable'}
    if observed is None or baseline is None or baseline <= 0:
        return {'status': 'Status unavailable', 'status_reason': 'comparison_unavailable'}
    qm = (cutoff.month - 1)//3*3+1
    start = dt.date(cutoff.year, qm, 1)
    end = dt.date(cutoff.year+1, 1, 1) if qm == 10 else dt.date(cutoff.year, qm+3, 1)
    first = start + dt.timedelta(days=(6-start.weekday()) % 7)
    total = ((end-dt.timedelta(days=1)-first).days//7)+1
    elapsed = max(0, min(total, (cutoff-dt.timedelta(days=6)-first).days//7+1))
    tracking = elapsed/total < .30
    return {'status': 'Tracking' if tracking else 'On track' if observed >= approved else 'At risk',
            'status_reason': 'early_quarter' if tracking else 'qtd_growth_vs_target',
            'status_target_value': approved, 'status_attainment_pct': observed/approved*100,
            'status_weeks_elapsed': elapsed, 'status_weeks_total': total}
