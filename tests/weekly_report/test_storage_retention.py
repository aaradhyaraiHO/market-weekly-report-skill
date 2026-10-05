from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/weekly_report'))
import storage_retention as retention
import report_storage as storage


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.work = Path(self.tmp.name).resolve()
        self.root = self.work / '.cache/weekly_report'
        (self.root / 'old/notebook').mkdir(parents=True)
        (self.root / 'pinned/notebook').mkdir(parents=True)
        for rel in ('old/notebook/report.html', 'pinned/notebook/report.html'):
            (self.root / rel).write_text('report fixture')
        (self.root / 'old/receipt.json').write_text('{}')
        now = datetime.now(timezone.utc)
        sha = storage.sha256(self.root / 'old/notebook/report.html')
        self.rows = [{'candidate': 'old/notebook/report.html', 'retained_equivalent': 'pinned/notebook/report.html',
                      'sha256': sha, 'size': 14}]
        self.manifest = self.work / 'backup.json'
        self.manifest.write_text(json.dumps({'files': self.rows}))
        self.receipt = self.work / 'restore.json'
        self.receipt.write_text(json.dumps({'archive_sha256_verified': True, 'source_or_production_modified': False,
                                           'original_paths_mapped_to_verified_objects': 1,
                                           'all_unique_objects_restored_and_hashed': 1}))
        evidence = {'path': str(self.root / 'old/receipt.json'), 'sha256': storage.sha256(self.root / 'old/receipt.json')}
        self.registry = {'cache_root': str(self.root), 'pins': ['pinned'], 'references': ['pinned/notebook'],
                         'references_verified_at': now.isoformat(), 'reference_evidence': [evidence],
                         'artifacts': {'old': {'kind': 'duplicate_working', 'status': 'closed_verified',
                                              'closed_at': (now - timedelta(days=10)).isoformat(), 'evidence': [evidence]}},
                         'backup': {'manifest': str(self.manifest), 'manifest_sha256': storage.sha256(self.manifest),
                                    'restore_receipt': str(self.receipt), 'restore_receipt_sha256': storage.sha256(self.receipt)}}

    def test_dry_run_does_not_delete(self):
        result = retention.plan(self.registry, self.rows)
        self.assertTrue(result['candidates'][0]['safe'])
        self.assertTrue((self.root / self.rows[0]['candidate']).exists())

    def test_pins_and_unknown_and_young_artifacts_protected(self):
        for key, value in [('status', 'running'), ('kind', 'unknown'), ('closed_at', datetime.now(timezone.utc).isoformat())]:
            with self.subTest(key=key):
                modified = json.loads(json.dumps(self.registry))
                modified['artifacts']['old'][key] = value
                self.assertFalse(retention.plan(modified, self.rows)['candidates'][0]['safe'])
        self.registry['pins'].append('old')
        self.assertFalse(retention.plan(self.registry, self.rows)['candidates'][0]['safe'])

    def test_expired_references_fail_closed(self):
        self.registry['references_verified_at'] = '2020-01-01T00:00:00+00:00'
        with self.assertRaises(ValueError):
            retention.plan(self.registry, self.rows)

    def test_release_audit_reports_expired_references_without_enabling_deletion(self):
        self.registry['references_verified_at'] = '2020-01-01T00:00:00+00:00'
        policy = self.work / 'audit-policy.json'
        policy.write_text(json.dumps({'registry': self.registry, 'candidates': self.rows}))
        with patch.object(retention, 'apply', side_effect=AssertionError('audit attempted deletion')):
            result = retention.audit_policy(policy)
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['deletion_enabled'])
        self.assertFalse(result['candidates'][0]['safe'])
        self.assertIn('expired', result['blockers'][0])
        self.assertTrue((self.root / self.rows[0]['candidate']).exists())

    def test_release_audit_validates_fresh_pair_and_keeps_it(self):
        policy = self.work / 'audit-policy.json'
        policy.write_text(json.dumps({'registry': self.registry, 'candidates': self.rows}))
        result = retention.audit_policy(policy)
        self.assertEqual(result['status'], 'evaluated')
        self.assertTrue(result['candidates'][0]['safe'])
        self.assertFalse(result['deletion_enabled'])
        (self.root / self.rows[0]['retained_equivalent']).write_text('changed')
        self.assertFalse(retention.audit_policy(policy)['candidates'][0]['safe'])
        self.assertTrue((self.root / self.rows[0]['candidate']).exists())

    def test_release_audit_unconfigured_protects_everything(self):
        result = retention.audit_policy(self.work / 'missing-policy.json')
        self.assertEqual(result['status'], 'unconfigured')
        self.assertFalse(result['deletion_enabled'])

    def test_backup_evidence_change_blocks(self):
        self.receipt.write_text('{}')
        with self.assertRaises(ValueError):
            retention.plan(self.registry, self.rows)

    def test_missing_keeper_blocks(self):
        (self.root / 'pinned/notebook/report.html').rename(self.root / 'pinned/notebook/renamed.html')
        self.assertFalse(retention.plan(self.registry, self.rows)['candidates'][0]['safe'])

    def test_changed_candidate_invalidates_approval(self):
        approved = retention.plan(self.registry, self.rows)['plan_sha256']
        (self.root / self.rows[0]['candidate']).write_text('changed')
        with self.assertRaises(ValueError):
            retention.apply(self.registry, self.rows, approved, self.work / 'journal', lock_path=self.work / 'lock')
        self.assertTrue((self.root / self.rows[0]['candidate']).exists())

    def test_apply_only_exact_file_preserves_metadata_and_equivalent(self):
        approved = retention.plan(self.registry, self.rows)['plan_sha256']
        retention.apply(self.registry, self.rows, approved, self.work / 'journal', lock_path=self.work / 'lock')
        self.assertFalse((self.root / self.rows[0]['candidate']).exists())
        self.assertTrue((self.root / 'old/receipt.json').exists())
        self.assertTrue((self.root / self.rows[0]['retained_equivalent']).exists())
        self.assertTrue((self.root / 'old' / storage.RETIRED).exists())
        events = [json.loads(line)['event'] for line in (self.work / 'journal/deletion-journal.jsonl').read_text().splitlines()]
        self.assertEqual(events, ['intent', 'removed', 'complete'])
        with self.assertRaises(ValueError):
            storage.deployable(self.root / 'old/notebook')

    def test_symlink_candidate_or_parent_blocks(self):
        candidate = self.root / self.rows[0]['candidate']
        candidate.rename(candidate.with_suffix('.fixture'))
        candidate.symlink_to(candidate.with_suffix('.fixture'))
        self.assertFalse(retention.plan(self.registry, self.rows)['candidates'][0]['safe'])

    def test_duplicate_candidate_and_keeper_candidate_rejected(self):
        with self.assertRaises(ValueError):
            retention.plan(self.registry, self.rows * 2)

    def test_active_writer_blocks_before_any_deletion(self):
        approved = retention.plan(self.registry, self.rows)['plan_sha256']
        with storage.writer_lock('monthly', self.work / 'lock'):
            with self.assertRaises(RuntimeError):
                retention.apply(self.registry, self.rows, approved, self.work / 'journal', lock_path=self.work / 'lock')
        self.assertTrue((self.root / self.rows[0]['candidate']).exists())

    def test_discovery_is_limited_to_backup_scope(self):
        (self.root / 'old/unregistered.html').write_text('unknown')
        self.assertEqual(retention.discover(self.registry), self.rows)

    def test_missing_protected_reference_blocks(self):
        self.registry['references'].append('missing/notebook')
        with self.assertRaisesRegex(ValueError, 'Missing protected'):
            retention.plan(self.registry, self.rows)

    def test_resume_reconciles_unlink_without_acknowledgement(self):
        approved = retention.plan(self.registry, self.rows)['plan_sha256']
        append = retention.append_record
        def fail_after_unlink(stream, record):
            if record['event'] == 'removed':
                raise OSError('simulated interruption after unlink')
            append(stream, record)
        with patch.object(retention, 'append_record', side_effect=fail_after_unlink):
            with self.assertRaises(OSError):
                retention.apply(self.registry, self.rows, approved, self.work / 'journal', lock_path=self.work / 'lock')
        retention.apply(self.registry, self.rows, approved, self.work / 'journal', lock_path=self.work / 'lock', resume=True)
        events = [json.loads(line)['event'] for line in (self.work / 'journal/deletion-journal.jsonl').read_text().splitlines()]
        self.assertEqual(events, ['intent', 'reconciled_removed', 'complete'])
        self.assertTrue((self.root / self.rows[0]['retained_equivalent']).exists())

    def test_resume_rejects_tampered_scope(self):
        approved = retention.plan(self.registry, self.rows)['plan_sha256']
        retention.apply(self.registry, self.rows, approved, self.work / 'journal', lock_path=self.work / 'lock')
        with self.assertRaisesRegex(ValueError, 'scope'):
            retention.apply(self.registry, [], approved, self.work / 'journal', lock_path=self.work / 'lock', resume=True)


if __name__ == '__main__':
    unittest.main()
