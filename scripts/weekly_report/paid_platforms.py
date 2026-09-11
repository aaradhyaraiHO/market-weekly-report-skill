"""Optional Search platform evidence, using the existing Paid metric canon.

The source query includes exactly Google Ads and Microsoft Ads Search. Subtract
only additive facts; ratios must be recomputed from each platform's operands.
Missing operands stay unavailable, including in older cached snapshots.
"""
import math

import config

SOURCE_FIELDS = {
    "spend": "spend", "cm1": "cm1", "paid_clicks": "paid_clicks",
    "paid_conversions": "conversions", "paid_impressions": "paid_impressions",
    "paid_revenue": "offline_revenue", "coupon_wallet": "coupon_wallet",
}
GOOGLE_SOURCE_FIELDS = {
    "spend": "spend_g", "cm1": "cm1_g", "paid_clicks": "paid_clicks_g",
    "paid_conversions": "conversions_g", "paid_impressions": "sis_impr",
    "paid_revenue": "offline_revenue_g", "coupon_wallet": "coupon_wallet_g",
    "sis_impr": "sis_impr", "sis_elig": "sis_elig",
}


def _source_number(raw):
    if raw is None or isinstance(raw, bool):
        return None
    try:
        parsed = float(raw)
    except (ValueError, TypeError):
        return None
    return parsed if math.isfinite(parsed) else None


def missing_source_fields(source):
    fields = set(SOURCE_FIELDS.values()) | set(GOOGLE_SOURCE_FIELDS.values())
    return sorted(field for field in fields if _source_number(source.get(field)) is None)


def source_platforms(source):
    """Retain exact query operands, including nulls, without defaulting to zero."""
    return platform_metrics(
        {key: _source_number(source.get(field)) for key, field in SOURCE_FIELDS.items()},
        {key: _source_number(source.get(field)) for key, field in GOOGLE_SOURCE_FIELDS.items()},
    )


def attach_aggregate_platforms(row, paid_frame):
    """Add history to a manual market rollup without changing its core fields."""
    if paid_frame.empty:
        row["paid_platform_source_status"] = "no_rows"
    else:
        fields = set(SOURCE_FIELDS.values()) | set(GOOGLE_SOURCE_FIELDS.values())
        # A partial sum is not a complete platform total: retain null if any
        # constituent is missing. Core report aggregates remain untouched.
        operands = {key: float(paid_frame[key].sum(min_count=len(paid_frame))) for key in fields if key in paid_frame}
        if "coupon_wallet_g" in paid_frame:
            row["paid_platforms"] = source_platforms(operands)
        missing = missing_source_fields(operands)
        if missing:
            row["paid_platform_missing_fields"] = missing


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def platform_metrics(total, google):
    def subtract(key):
        a, b = number(total.get(key)), number(google.get(key))
        return a - b if a is not None and b is not None else None

    bing = {key: subtract(key) for key in total}
    result = {}
    for platform, source in (("google", google), ("bing", bing)):
        facts = {key: number(value) for key, value in source.items()}
        def ratio(numerator, denominator, scale=1, gate=None):
            n, d = facts.get(numerator), facts.get(denominator)
            if n is None or d is None or d <= 0:
                return None
            value = scale * n / d
            return value if gate is None or gate[0] <= value <= gate[1] else None

        spend, coupon = facts.get("spend"), facts.get("coupon_wallet")
        facts["roi_cost"] = spend + coupon if spend is not None and coupon is not None else None
        revenue = facts.get("paid_revenue")
        result[platform] = {
            **facts,
            "paid_ctr_pct": ratio("paid_clicks", "paid_impressions", 100),
            "paid_cvr_pct": ratio("paid_conversions", "paid_clicks", 100, (0, config.CVR_MAX_PCT)),
            "cpc": ratio("spend", "paid_clicks"),
            "paid_rpc": ratio("paid_revenue", "paid_clicks"),
            "paid_cm2": revenue - spend if revenue is not None and spend is not None else None,
            "cm1_per_conv": ratio("cm1", "paid_conversions"),
            "roi_pct": ratio("cm1", "roi_cost", 100, (config.ROI_MIN_PCT, config.ROI_MAX_PCT))
            if spend is not None and spend >= config.WEEKLY_SPEND_FLOOR else None,
            "paid_sis_pct": ratio("sis_impr", "sis_elig", 100, (0, 100)) if platform == "google" else None,
        }
    return result


def snapshot_platforms(row):
    if isinstance(row.get("paid_platforms"), dict):
        return row["paid_platforms"]
    fields = ("spend", "cm1", "paid_clicks", "paid_conversions", "paid_impressions", "paid_revenue", "coupon_wallet")
    google_fields = {"spend": "spend_g", "cm1": "cm1_g", "paid_clicks": "paid_clicks_g",
                     "paid_conversions": "conversions_g", "paid_impressions": "sis_impr",
                     "paid_revenue": "offline_revenue_g", "coupon_wallet": "coupon_wallet_g"}
    result = platform_metrics({key: row.get(key) for key in fields},
                              {key: row.get(google_fields[key]) for key in fields})
    result["google"]["paid_sis_pct"] = number(row.get("paid_sis_pct"))
    return result
