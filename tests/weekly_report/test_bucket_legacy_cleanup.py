"""Removing obsolete display metadata must not alter current bucket tables."""
from __future__ import annotations

from contextlib import ExitStack
from copy import deepcopy
import gzip
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "weekly_report"))
import buckets
import headline_v2


class LegacyBucketCleanup(unittest.TestCase):
    def test_current_tables_ignore_removed_legacy_outputs(self):
        fixtures = Path(__file__).parent / "fixtures" / "captured"
        for path in sorted(fixtures.glob("snapshot_*.json.gz")):
            with self.subTest(shape=path.name):
                original = json.loads(gzip.decompress(path.read_bytes()))
                cleaned = deepcopy(original)
                for key in ("bucket_b3", "bucket_b4", "bucket_cascade"):
                    cleaned.pop(key, None)
                for key in ("bucket_b1", "bucket1_fluctuations"):
                    rows = cleaned.get(key) or []
                    if isinstance(rows, dict):
                        rows = rows.get("rows") or []
                    for row in rows:
                        for field in ("is_home", "also_in", "stake_usd", "in_store", "is_win", "spark_rpc"):
                            row.pop(field, None)
                # Freeze optional external enrichment so this comparison is offline
                # and both versions receive exactly the same lookup values.
                with ExitStack() as stack:
                    for name in ("_mmp_map", "_prior_proplus_map", "_launch_map", "_troas_now_map"):
                        stack.enter_context(patch.object(buckets, name, return_value={}))
                    expected = buckets.build_buckets(original)
                    actual = buckets.build_buckets(cleaned)
                self.assertEqual(expected, actual)
                original["buckets_final"] = expected
                cleaned["buckets_final"] = actual
                self.assertEqual(headline_v2._diagnostic_bucket_view(original),
                                 headline_v2._diagnostic_bucket_view(cleaned))
                self.assertEqual(headline_v2._ce_bucket_memberships(original),
                                 headline_v2._ce_bucket_memberships(cleaned))


if __name__ == "__main__":
    unittest.main()
