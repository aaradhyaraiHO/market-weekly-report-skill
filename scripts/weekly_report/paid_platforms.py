"""Optional Search platform evidence, using the existing Paid metric canon.

The source query includes exactly Google Ads and Microsoft Ads Search. Subtract
only additive facts; ratios must be recomputed from each platform's operands.
Missing operands stay unavailable, including in older cached snapshots.
"""
import math

import config


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
