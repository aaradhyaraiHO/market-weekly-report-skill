"""
WoW revenue Shapley decomposition for the market-headline drawer.

Revenue telescopes exactly across five funnel factors:

    Revenue = Clicks x CVR x AOV x CR x TR
      Clicks         = paid clicks               (level 0)
      CVR  = orders / clicks                      (level 1 = orders)
      AOV  = booked GBV / orders                  (level 2 = sum_order_value)
      CR   = completed GBV / booked GBV           (level 3 = sum_order_value_completed)
      TR   = revenue / completed GBV              (level 4 = revenue, predicted)

Because each factor is a ratio of consecutive levels, the product telescopes to
revenue regardless of the paid/total mix — so the decomposition always
reconstructs the exact revenue the report displays. NOTE the CVR factor here is
orders-per-paid-click (the revenue-bridge conversion rate), which is a blended
demand-capture rate and is DISTINCT from the displayed "Paid CVR"
(ad_conversions / ad_clicks).

Attribution is exact Shapley over the 5 factors (2^4 marginal orderings per
factor); by the efficiency property the five values sum to Delta-revenue exactly.
"""
from __future__ import annotations

from itertools import combinations
from math import factorial

FACTORS = ["traffic", "cvr", "aov", "cr", "tr"]

# Human labels for the emitted block.
LABELS = {
    "traffic": "Traffic",
    "cvr": "CVR",
    "aov": "AOV",
    "cr": "Completion",
    "tr": "Take rate",
}


def _levels_to_factors(L: dict) -> dict | None:
    """L: {clicks, orders, gbv, gbv_completed, revenue} -> the 5 factor values."""
    clicks = L.get("clicks") or 0
    orders = L.get("orders") or 0
    gbv = L.get("gbv") or 0
    gbv_c = L.get("gbv_completed") or 0
    rev = L.get("revenue") or 0
    if min(clicks, orders, gbv, gbv_c) <= 0:
        return None
    return {
        "traffic": float(clicks),
        "cvr": orders / clicks,
        "aov": gbv / orders,
        "cr": gbv_c / gbv,
        "tr": rev / gbv_c,
    }


def wow_revenue_shapley(levels_w0: dict, levels_wm1: dict) -> dict | None:
    """
    Shapley attribution of (revenue_W0 - revenue_W-1) to the 5 factors.
    Returns {traffic, cvr, aov, cr, tr, total, net_delta, reconstructs, labels}
    or None if a level is non-positive (factors undefined).
    """
    f0 = _levels_to_factors(levels_w0)
    f1 = _levels_to_factors(levels_wm1)
    if f0 is None or f1 is None:
        return None

    n = len(FACTORS)
    phi = {f: 0.0 for f in FACTORS}
    for i in FACTORS:
        rest = [f for f in FACTORS if f != i]
        for r in range(len(rest) + 1):
            weight = factorial(r) * factorial(n - 1 - r) / factorial(n)
            for subset in combinations(rest, r):
                # subset at W0, the remaining "others" at W-1, factor i toggled.
                base = 1.0
                for f in rest:
                    base *= f0[f] if f in subset else f1[f]
                phi[i] += weight * base * (f0[i] - f1[i])

    total = sum(phi.values())
    net_delta = (levels_w0.get("revenue") or 0) - (levels_wm1.get("revenue") or 0)
    out = {f: round(phi[f], 1) for f in FACTORS}
    out["total"] = round(total, 1)
    out["net_delta"] = round(net_delta, 1)
    # Efficiency check: Shapley total must equal the actual revenue delta.
    out["reconstructs"] = abs(total - net_delta) < max(1.0, abs(net_delta) * 1e-6)
    out["labels"] = LABELS
    return out
