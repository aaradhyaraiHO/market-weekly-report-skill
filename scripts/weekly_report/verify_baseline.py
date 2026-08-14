#!/usr/bin/env python3
"""Run the no-write end-to-end Weekly Report V1 baseline verification."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TESTS = REPO / "tests" / "weekly_report"


def main() -> int:
    suite = unittest.defaultTestLoader.discover(str(TESTS), pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
