"""Read-only accessors for weekly-report bucket consumers.

The snapshot still carries both legacy bucket structures and the current
``buckets_final`` structure.  Consumers should use the explicitly named
accessor that matches the contract they currently consume; this module does
not calculate, normalize, or migrate bucket membership.
"""
from __future__ import annotations


FINAL_FLUCTUATION_PATHS = {
    "down": ("defend", "seasonality_down"),
    "up": ("compound", "seasonality_up"),
}


def final_buckets(snapshot: dict) -> dict:
    """Return the current report bucket envelope."""
    return snapshot.get("buckets_final") or {}


def final_losing_money(snapshot: dict) -> dict:
    """Return ``buckets_final.defend.losing_money``."""
    return (final_buckets(snapshot).get("defend") or {}).get("losing_money") or {}


def final_losing_money_rows(snapshot: dict) -> list[dict]:
    """Return current Losing Money rows in report order: existing, then new."""
    losing_money = final_losing_money(snapshot)
    return (losing_money.get("existing") or []) + (losing_money.get("new") or [])


def final_fluctuation_rows(snapshot: dict, direction: str) -> list[dict]:
    """Return the current report's down or up fluctuation rows."""
    try:
        family, key = FINAL_FLUCTUATION_PATHS[direction]
    except KeyError as exc:
        raise ValueError(f"unknown fluctuation direction: {direction}") from exc
    return (final_buckets(snapshot).get(family) or {}).get(key) or []


def legacy_losing_money_rows(snapshot: dict, group: str) -> list[dict]:
    """Return a legacy Losing Money sub-list from the current envelope.

    ``export_flagged.py`` still asks for the pre-V2 group names. Keeping that
    read explicit preserves its frozen header-only behavior until the exporter
    compatibility fix is approved separately.
    """
    return final_losing_money(snapshot).get(group) or []
