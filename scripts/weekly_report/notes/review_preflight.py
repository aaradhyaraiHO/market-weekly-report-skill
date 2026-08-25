#!/usr/bin/env python3
"""Non-mutating preflight for the isolated WBR Review service.

This deliberately validates configuration only.  It never calls Apps Script,
Slack, Granola or the legacy Weekly Report Notes service, so it is safe to run
before a canary or cutover.
"""

from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse


BASE_REQUIRED = (
    "REVIEW_MODE_APPS_SCRIPT_URL",
    "REVIEW_MODE_PROXY_SECRET",
)
SERVER_REQUIRED = (
    "REVIEW_MODE_INGEST_SECRET",
    "REVIEW_MODE_AI_WEBHOOK_URL",
    "REVIEW_MODE_AI_WEBHOOK_SECRET",
    "ANTHROPIC_API_KEY",
    "GRANOLA_WEBHOOK_SECRET",
)


def configured(name: str) -> bool:
    return bool(os.environ.get(name, "").strip())


def https_url(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return f"{name} is missing"
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        return f"{name} must be an HTTPS URL"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--server",
        action="store_true",
        help="also validate the Vercel-only Slack/AI/Granola ingress configuration",
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    for name in BASE_REQUIRED:
        if not configured(name):
            errors.append(f"{name} is missing")
    endpoint_error = https_url("REVIEW_MODE_APPS_SCRIPT_URL")
    if endpoint_error and endpoint_error not in errors:
        errors.append(endpoint_error)

    if args.server:
        for name in SERVER_REQUIRED:
            if not configured(name):
                errors.append(f"{name} is missing")
        for name in ("REVIEW_MODE_AI_WEBHOOK_URL",):
            endpoint_error = https_url(name)
            if endpoint_error and endpoint_error not in errors:
                errors.append(endpoint_error)
        if not configured("SLACK_BOT_TOKEN"):
            warnings.append("SLACK_BOT_TOKEN is missing: saving notes can work, but Slack posting/sync cannot")
    else:
        warnings.append("Server integration values not checked; rerun with --server before a live canary")

    if errors:
        print("Review preflight: BLOCKED")
        for error in errors:
            print(f"  ✗ {error}")
    else:
        print("Review preflight: configuration present")
        print("  ✓ Review uses REVIEW_MODE_* configuration only")
        print("  ✓ No legacy NOTES_URL or action service is consulted")

    for warning in warnings:
        print(f"  ! {warning}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
