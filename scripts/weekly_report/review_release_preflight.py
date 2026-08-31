#!/usr/bin/env python3
"""Fail fast if a Review release directory is not a complete Market Notebook site.

Run this before any *Preview* deployment. It is deliberately filesystem-only:
it cannot deploy, alter aliases, or call external services.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def is_headout_report(path: Path) -> bool:
    stem = path.stem
    return stem == "weekly-report-headout" or stem.startswith("weekly-report-headout-20")


def verify(directory: Path, report: str) -> list[str]:
    # Review is only testable as a whole when the authenticated Granola-link
    # route ships with the same artifact as the report and Review proxy.
    required = ["index.html", "api/actions.js", "api/review.js", "api/review-summary.js", "api/granola-link.js", report]
    missing = [item for item in required if not (directory / item).is_file()]
    if missing:
        return [f"missing required full-site artifact: {item}" for item in missing]

    failures: list[str] = []
    reports = sorted(directory.glob("weekly-report-*.html"))
    if not reports:
        failures.append("no weekly report pages found")
        return failures
    # Review is market-scoped. Headout/global is deliberately excluded; every
    # market report must still carry the same bootstrap.
    for page in reports:
        shell = page.read_text()
        if is_headout_report(page):
            if 'id="review-view"' in shell or "initReviewView" in shell or 'data-report-view="review"' in shell:
                failures.append(f"{page.name} must not contain Review")
            continue
        if 'id="review-view"' not in shell:
            failures.append(f"{page.name} has no Review container")
        if "initReviewView" not in shell:
            failures.append(f"{page.name} has no Review bootstrap")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a complete-site Review Preview artifact")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--report", default="weekly-report-north-america.html")
    args = parser.parse_args()
    failures = verify(args.directory, args.report)
    if failures:
        print("Review release preflight failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Review release preflight passed: {args.directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
