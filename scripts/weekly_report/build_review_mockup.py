#!/usr/bin/env python3
"""Refresh the self-contained Weekly Review mockups from canonical UI sources.

The mock document owns only its in-memory API fixture and boot code. Production
CSS and interaction logic are copied from ``review/review-view.{css,js}``, so
the two user-facing mockup paths cannot silently drift from the injectable UI.
This is a local documentation build: it performs no network or production I/O.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "scripts" / "weekly_report" / "review"
DOCS = ROOT / "docs" / "weekly-review"
CANONICAL = DOCS / "review-tab-redesign-mockup.html"
BODY = DOCS / "review-tab-redesign-mockup.body.html"
FINAL = DOCS / "final-wbr-review-mode.html"


def replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"could not locate exactly one {label} block")
    return updated


def refresh(document: str, css: str, js: str) -> str:
    document = replace_once(
        document,
        r"<style>\s*/\* Weekly Review tab — production styles.*?</style>",
        "<style>\n" + css.rstrip() + "\n</style>",
        "production CSS",
    )
    document = replace_once(
        document,
        r"<script>\s*/\* Weekly Review tab — production logic.*?</script>",
        "<script>\n" + js.rstrip() + "\n</script>",
        "production JavaScript",
    )
    return document


def main() -> None:
    css = (REVIEW / "review-view.css").read_text()
    js = (REVIEW / "review-view.js").read_text()
    canonical = refresh(CANONICAL.read_text(), css, js)
    body = refresh(BODY.read_text(), css, js)
    CANONICAL.write_text(canonical)
    BODY.write_text(body)
    # Keep the historically shared path functional, but make it the same
    # artifact instead of maintaining a second Review workflow implementation.
    FINAL.write_text(canonical)
    print(f"refreshed {CANONICAL.relative_to(ROOT)}")
    print(f"refreshed {BODY.relative_to(ROOT)}")
    print(f"mirrored {FINAL.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
