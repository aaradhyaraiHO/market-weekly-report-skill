#!/usr/bin/env python3
"""Fail closed on crossed V2 diagnostic and Review-mode API routes.

Run this against the deployment package immediately before a V2 deploy.  It
requires both unversioned current aliases and dated V2 reports so a stale alias
cannot silently bypass the audit.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


DATED_REPORT = re.compile(r"-\d{4}-\d{2}-\d{2}\.html$")
# The first V2 renderer used ACTIONS_API; the current renderer uses ACTIONS_URL
# with a data override.  Keep both forms in the guard so an old archive cannot
# bypass it, while auditing the route the current report actually calls.
ACTIONS_DECLARATION = re.compile(r"const\s+ACTIONS_(?:API|URL)\s*=")
ACTION_ROUTE = re.compile(
    r"const\s+ACTIONS_(?:API|URL)\s*=\s*(?:DATA\.actions_url\s*\|\|\s*)?['\"]/api/actions['\"]"
)
REVIEW_ROUTE = re.compile(
    r"const\s+ACTIONS_(?:API|URL)\s*=\s*(?:DATA\.actions_url\s*\|\|\s*)?['\"]/api/review['\"]"
)


def v2_reports(deploy: Path) -> list[Path]:
    return sorted(
        path for path in deploy.glob("weekly-report-*.html")
        if ACTIONS_DECLARATION.search(path.read_text(errors="replace"))
    )


def audit_v2_deployment(deploy: Path, *, require_proxies: bool = True) -> dict:
    """Validate all current and dated V2 reports and their isolated proxies."""
    reports = v2_reports(deploy)
    if not reports:
        raise ValueError("no V2 reports found for routing audit")
    dated = [path for path in reports if DATED_REPORT.search(path.name)]
    current = [path for path in reports if not DATED_REPORT.search(path.name)]
    if not dated or not current:
        raise ValueError("routing audit requires both current aliases and dated V2 reports")

    failures = []
    for path in reports:
        source = path.read_text(errors="replace")
        if REVIEW_ROUTE.search(source) or not ACTION_ROUTE.search(source):
            failures.append(path.name)
    if failures:
        raise ValueError("V2 diagnostic actions must use /api/actions only: " + ", ".join(failures))

    api = deploy / "api"
    actions = api / "actions.js"
    review = api / "review.js"
    if require_proxies and (not actions.is_file() or not review.is_file()):
        missing = [str(path) for path in (actions, review) if not path.is_file()]
        raise ValueError("isolated V2 proxies missing: " + ", ".join(missing))
    return {"reports": len(reports), "current": len(current), "dated": len(dated)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deploy", type=Path)
    args = parser.parse_args()
    result = audit_v2_deployment(args.deploy)
    print("V2 action routing verified: {reports} reports ({current} current, {dated} dated)".format(**result))


if __name__ == "__main__":
    main()
