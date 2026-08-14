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


def render(markets, template_path=TEMPLATE, goals=None):
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
        "headlines": build_headline_payload(scoped_markets, goals),
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
    parser.add_argument("--out", help="output HTML path")
    args = parser.parse_args()
    paths = list(args.inputs)
    if args.glob:
        paths += sorted(globmod.glob(args.glob))
    markets = render_v1.load_markets(paths)
    output = args.out or out_path(markets)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w") as handle:
        handle.write(render(markets, goals=load_goals(args.goals)))
    print(f"wrote: {output}")


if __name__ == "__main__":
    main()
