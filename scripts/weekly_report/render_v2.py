#!/usr/bin/env python3
"""Render the isolated Weekly Report V2 Market Headlines preview."""
from __future__ import annotations

import argparse
import glob as globmod
import json
import os

import render as render_v1
from headline_v2 import build_headline_payload

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "template", "report_v2_template.html")
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(REPO_ROOT, "thoughts", "shared", "weekly-report-v2")


def load_goals(path):
    if not path:
        return {}
    with open(path) as handle:
        payload = json.load(handle)
    return payload.get("markets", payload)


def load_ce_dimensions(path):
    if not path:
        return {}
    with open(path) as handle:
        payload = json.load(handle)
    return payload.get("markets", payload)


def load_okr_results(path):
    """Load the optional market-grain OKR sidecar used by Alert V2."""
    if not path or not os.path.exists(path):
        return {}
    with open(path) as handle:
        payload = json.load(handle)
    return payload


def _attach_market_okrs(headlines, okr_results):
    """Attach only same-week market evidence; country views remain un-enriched."""
    if not isinstance(okr_results, dict):
        return headlines
    markets = okr_results.get("markets")
    sidecar_week = okr_results.get("week_start")
    if not isinstance(markets, dict):
        return headlines
    for headline in headlines:
        slug = headline.get("market_slug")
        if sidecar_week != headline.get("week_start") or not isinstance(markets.get(slug), list):
            continue
        headline["market_okrs"] = markets[slug]
    return headlines


def render(markets, template_path=TEMPLATE, goals=None, ce_dimensions=None, okr_results=None):
    with open(template_path) as handle:
        html = handle.read()
    first_slug = markets[0].get("meta", {}).get("market_slug")
    scoped_markets = [
        market for market in markets
        if market.get("meta", {}).get("market_slug") == first_slug
    ]
    scoped_markets.sort(key=lambda market: market.get("meta", {}).get("week_start", ""))
    payload = {
        "schema_version": 2,
        "source_schema_version": markets[0].get("meta", {}).get("schema_version", 1),
        "headlines": _attach_market_okrs(
            build_headline_payload(scoped_markets, goals, ce_dimensions), okr_results
        ),
        # Reuse the established V1 action sidecar contract. Rendering remains
        # read-only; writes only happen after an explicit reviewer interaction.
        "notes_url": (os.environ.get("WR_NOTES_SCRIPT_URL") or render_v1.NOTES_SCRIPT_URL) or None,
        "notes_channels": render_v1.NOTES_SLACK_CHANNELS,
    }
    data_json = json.dumps(payload, separators=(",", ":")).replace("<", "\\u003c")
    names = " · ".join(item["market"] for item in payload["headlines"])
    return html.replace("__REPORT_DATA_JSON__", data_json).replace("__TITLE__", f"Weekly V2 — {names}")


def out_path(markets):
    meta = markets[0]["meta"]
    slug = meta.get("market_slug", "market") if len(markets) == 1 else "multi"
    return os.path.join(OUT_DIR, f"report_{slug}_{meta.get('week_start', 'week')}.html")


def main():
    parser = argparse.ArgumentParser(description="Render Weekly Report V2 Market Headlines")
    parser.add_argument("inputs", nargs="+", help="schema-v1 snapshot or bundle JSON files")
    parser.add_argument("--glob", help="additional snapshot glob")
    parser.add_argument("--goals", help="optional approved monthly-goal sidecar JSON")
    parser.add_argument("--ce-dimensions", help="optional CE-to-BDM/Growth-region sidecar JSON")
    parser.add_argument("--okr-results", help="optional same-week market OKR sidecar JSON")
    parser.add_argument("--out", help="output HTML path")
    args = parser.parse_args()
    paths = list(args.inputs)
    if args.glob:
        paths += sorted(globmod.glob(args.glob))
    markets = render_v1.load_markets(paths)
    output = args.out or out_path(markets)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w") as handle:
        handle.write(render(
            markets,
            goals=load_goals(args.goals),
            ce_dimensions=load_ce_dimensions(args.ce_dimensions),
            okr_results=load_okr_results(args.okr_results),
        ))
    print(f"wrote: {output}")


if __name__ == "__main__":
    main()
