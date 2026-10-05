import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import report_storage as storage
import run_v2_release


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_capacity_boundary_and_no_emergency_pruning(self):
        with patch.object(storage.shutil, 'disk_usage') as disk:
            disk.return_value.free = 50 * storage.GIB
            self.assertTrue(storage.preflight([self.root])['capacity_pass'])
            disk.return_value.free -= 1
            result = storage.preflight([self.root])
            self.assertFalse(result['capacity_pass'])
            self.assertEqual(result['volumes'][0]['estimated_verified_reclaimable_bytes'], 0)
            self.assertFalse(result['emergency_deletion'])

    def test_estimate_cannot_lower_floor_or_be_invalid(self):
        for value in (-1, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                storage.preflight([self.root], working_bytes=value)
        self.assertEqual(storage.preflight([self.root], working_bytes=1)['volumes'][0]['required_bytes'], 50 * storage.GIB)

    def test_same_volume_counted_once(self):
        self.assertEqual(len(storage.preflight([self.root, self.root / 'future'])['volumes']), 1)

    def test_shared_lock_rejects_concurrent_writer_and_releases(self):
        lock = self.root / 'writer.lock'
        with storage.writer_lock('weekly', lock):
            with self.assertRaises(RuntimeError):
                with storage.writer_lock('monthly', lock):
                    self.fail('concurrent writer admitted')
        with storage.writer_lock('retention', lock):
            self.assertTrue(lock.exists())

    def test_shared_lock_blocks_an_independent_process(self):
        lock = self.root / 'writer.lock'
        command = [sys.executable, '-c',
                   'import sys; sys.path.insert(0, sys.argv[1]); import report_storage as s; '
                   'from pathlib import Path;\n'
                   'try:\n with s.writer_lock("monthly", Path(sys.argv[2])): pass\n'
                   'except RuntimeError: sys.exit(42)\n',
                   str(ROOT / 'scripts/weekly_report'), str(lock)]
        with storage.writer_lock('weekly', lock):
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 42)
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_low_disk_stops_before_lock_creation(self):
        with patch.object(storage.shutil, 'disk_usage') as disk:
            disk.return_value.free = 49 * storage.GIB
            with self.assertRaises(RuntimeError):
                with storage.release_guard('weekly', [self.root], lock_path=self.root / 'lock'):
                    self.fail('low disk admitted')
        self.assertFalse((self.root / 'lock').exists())

    def test_symlinks_rejected(self):
        (self.root / 'link').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            storage.preflight([self.root / 'link' / 'future'])

    def test_retired_ancestor_blocks_deployment(self):
        (self.root / storage.RETIRED).write_text('{}')
        with self.assertRaises(ValueError):
            storage.deployable(self.root / 'notebook')

    def test_copy_has_independent_mutation_and_inode(self):
        source, target = self.root / 'source.html', self.root / 'target.html'
        source.write_bytes(b'original' * 10000)
        result = storage.copy_independent(source, target)
        self.assertIn(result, ('clone', 'copy'))
        self.assertEqual(source.read_bytes(), target.read_bytes())
        self.assertNotEqual(source.stat().st_ino, target.stat().st_ino)
        target.write_text('changed')
        self.assertEqual(source.read_bytes(), b'original' * 10000)

    def test_copy_fallback_and_atomic_error_preserves_target(self):
        source, target = self.root / 'source', self.root / 'target'
        source.write_text('source'); target.write_text('previous')
        with patch.object(storage, '_clone', return_value=False):
            self.assertEqual(storage.copy_independent(source, target), 'copy')
        target.write_text('previous')
        with patch.object(storage, '_clone', side_effect=OSError('full')):
            with self.assertRaises(OSError):
                storage.copy_independent(source, target)
        self.assertEqual(target.read_text(), 'previous')

    def test_notebook_copy_preserves_nested_bytes_without_inode_sharing(self):
        source, target = self.root / 'base', self.root / 'stage'
        (source / 'api').mkdir(parents=True)
        (source / 'api/review.js').write_bytes(b'unchanged mini audit')
        storage.copy_notebook(source, target)
        self.assertEqual((source / 'api/review.js').read_bytes(), (target / 'api/review.js').read_bytes())
        self.assertNotEqual((source / 'api/review.js').stat().st_ino, (target / 'api/review.js').stat().st_ino)
        with self.assertRaises(FileExistsError):
            storage.copy_notebook(source, target)

    def test_estimate_ignores_only_non_deployed_build_cache(self):
        (self.root / 'node_modules').mkdir()
        (self.root / 'node_modules/link').symlink_to('/unavailable')
        (self.root / 'history.html').write_text('history')
        self.assertEqual(storage.tree_bytes(self.root, exclude_build_cache=True), 7)
        with self.assertRaises(ValueError):
            storage.tree_bytes(self.root)

    def test_canonical_v2_renders_once_and_keeps_baseline_gate(self):
        plan = run_v2_release.build_plan('2026-09-27', self.root)
        for step in plan:
            if step.name in ('build-markets', 'build-headout'):
                self.assertEqual(step.command[step.command.index('--renderer') + 1], 'snapshots')
        self.assertEqual(sum(s.name == 'combined-v2-gate' for s in plan), 1)
        self.assertEqual(plan[0].name, 'baseline')


if __name__ == '__main__':
    unittest.main()
