import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/weekly_report'))
import vercel_upload as upload
import run_v2_release


class FakeClient:
    def __init__(self, states=('READY',), code=0, reference='dpl_new'):
        self.states = list(states)
        self.code, self.reference = code, reference
        self.uploads = 0
        self.created = False
        self.state = 'BUILDING'
        self.canonical_override = None
        self.inspection_errors = 0

    def inspect(self, ref):
        if ref == upload.CANONICAL:
            return {'id': self.canonical_override or ('dpl_new' if self.created and self.state == 'READY' else 'dpl_base'),
                    'url': 'market-notebook-fixture-headout.vercel.app', 'readyState': 'READY'}
        if self.inspection_errors:
            self.inspection_errors -= 1
            raise subprocess.TimeoutExpired('inspect', 45)
        if len(self.states) > 1:
            self.state = self.states.pop(0)
        else:
            self.state = self.states[0]
        return {'id': 'dpl_new', 'url': 'market-notebook-fixture-headout.vercel.app', 'readyState': self.state}

    def upload(self, *args):
        self.uploads += 1
        self.created = True
        return self.code, self.reference


class DeploymentTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.base = self.root / 'base/notebook'
        self.notebook = self.root / 'package/notebook'
        self.base.mkdir(parents=True)
        (self.notebook / '.vercel').mkdir(parents=True)
        (self.base / 'history.html').write_bytes(b'preserved report history')
        (self.notebook / 'index.html').write_bytes(b'prepared report bytes')
        (self.notebook / '.vercel/project.json').write_text(json.dumps({
            'projectId': upload.PROJECT_ID, 'orgId': upload.ORG_ID, 'projectName': 'market-notebook'}))
        self.manifest = self.root / 'package/artifact.json'
        self.artifact = {'week': '2026-11-01', 'test': 'frozen'}
        self.manifest.write_text(json.dumps(self.artifact))
        self.receipt = self.root / 'package/deployment_transport.json'
        self.baseline = self.base.parent / 'deployment_receipt.json'
        self.baseline.write_text(json.dumps({'status': 'verified', 'deployment_id': 'dpl_base', 'files': upload.files(self.base)}))
        self.before = upload.files(self.notebook)
        p = patch.object(upload, 'verify_artifact', return_value=self.artifact)
        p.start()
        self.addCleanup(p.stop)
        self.now = 0

    def sleep(self, seconds):
        self.now += seconds

    def execute(self, client, sleep=None):
        result = upload.deploy_prepared(self.notebook, self.base, self.manifest, self.receipt, client,
            clock=lambda: self.now, sleep=sleep or self.sleep)
        self.assertEqual(upload.files(self.notebook), self.before)
        return result

    def test_ready_deployment_returns_only_to_browser_gate(self):
        client = FakeClient(states=('BUILDING', 'READY'))
        result = self.execute(client)
        self.assertEqual(result['status'], 'ready_for_browser_verification')
        self.assertEqual(client.uploads, 1)
        self.assertNotIn('post-alerts', self.receipt.read_text())

    def test_nonzero_monitor_exit_with_identity_does_not_reupload(self):
        client = FakeClient(code=124)
        self.assertEqual(self.execute(client)['deployment_id'], 'dpl_new')
        self.execute(client)
        self.assertEqual(client.uploads, 1)

    def test_inspection_timeout_retries_read_only(self):
        client = FakeClient()
        client.inspection_errors = 2
        self.execute(client)
        self.assertEqual(client.uploads, 1)
        self.assertEqual(self.now, 30)

    def test_expired_monitor_resumes_same_deployment_id(self):
        client = FakeClient(states=('BUILDING',))
        def expire(_):
            self.now += 901
        with self.assertRaisesRegex(RuntimeError, 'resume this receipt/ID'):
            self.execute(client, expire)
        client.states = ['READY']
        self.execute(client)
        self.assertEqual(client.uploads, 1)

    def test_unknown_upload_outcome_blocks_replay(self):
        client = FakeClient(code=1, reference=None)
        with self.assertRaisesRegex(RuntimeError, 'No confirmed deployment identity'):
            self.execute(client)
        with self.assertRaisesRegex(ValueError, 'Upload outcome uncertain'):
            self.execute(client)
        self.assertEqual(client.uploads, 1)

    def test_created_deployment_is_reconciled_from_preserved_acknowledgement(self):
        client = FakeClient(code=124, reference=None)
        with self.assertRaises(RuntimeError):
            self.execute(client)
        self.receipt.with_suffix('.stdout.log').write_text(json.dumps({'deployment': {'id': 'dpl_new'}}))
        result = self.execute(client)
        self.assertEqual(result['deployment_id'], 'dpl_new')
        self.assertEqual(client.uploads, 1)

    def test_changed_manifest_cannot_resume_receipt(self):
        client = FakeClient()
        self.execute(client)
        self.manifest.write_text(json.dumps({**self.artifact, 'new': 'different'}))
        upload.verify_artifact.return_value = json.loads(self.manifest.read_text())
        with self.assertRaisesRegex(ValueError, 'another artifact'):
            self.execute(client)
        self.assertEqual(client.uploads, 1)

    def test_history_or_prepared_artifact_changes_stop_before_upload(self):
        client = FakeClient()
        (self.base / 'history.html').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'Base notebook no longer matches'):
            self.execute(client)
        self.assertEqual(client.uploads, 0)

    def test_preservation_gate_failure_stops_before_upload(self):
        upload.verify_artifact.return_value = {'different': 'artifact'}
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, 'Prepared notebook differs'):
            self.execute(client)
        self.assertEqual(client.uploads, 0)

    def test_wrong_project_stops_before_any_write(self):
        p = self.notebook / '.vercel/project.json'
        p.write_text(json.dumps({'projectId': 'central-tracking'}))
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, 'approved Headout'):
            self.execute(client)
        self.assertEqual(client.uploads, 0)
        self.assertFalse(self.receipt.exists())

    def test_intervening_production_release_is_never_overwritten(self):
        client = FakeClient()
        client.canonical_override = 'dpl_someone_else'
        with self.assertRaisesRegex(ValueError, 'Production advanced'):
            self.execute(client)
        self.assertEqual(client.uploads, 0)

    def test_failed_build_is_not_replaced(self):
        client = FakeClient(states=('ERROR',))
        with self.assertRaisesRegex(RuntimeError, 'existing deployment failed'):
            self.execute(client)
        self.assertEqual(client.uploads, 1)

    def test_unknown_vendor_source_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'Unreviewed Vercel upload client'):
            upload.patched_upload('different vendor code')

    def test_only_project_deployment_identity_is_extracted(self):
        self.assertEqual(upload.deployment_reference(json.dumps({'deployment': {'id': 'dpl_new'}})), 'dpl_new')
        self.assertEqual(upload.deployment_reference('Production: https://market-notebook-abc-headout.vercel.app'),
                         'https://market-notebook-abc-headout.vercel.app')
        for value in ('https://evil.example/dpl_', 'https://central-tracking-abc-headout.vercel.app',
                      'dpl_first dpl_second', 'Error: retry vercel deploy --prod'):
            self.assertIsNone(upload.deployment_reference(value))

    def test_recurring_plan_selects_guarded_transport_before_queries(self):
        plan = run_v2_release.build_plan('2026-11-08', self.notebook, deploy=True, post_alerts=True, base_notebook=self.base)
        self.assertEqual(plan[0].name, 'deployment-transport-preflight')
        self.assertFalse(plan[0].external_write)
        self.assertIn('--check', plan[0].command)
        deploy = next(s for s in plan if s.name == 'deploy-vercel')
        self.assertIn(str(ROOT / 'scripts/weekly_report/vercel_upload.py'), deploy.command)
        self.assertIn('--under-release-lock', deploy.command)
        self.assertEqual([s.name for s in plan][-3:], ['deploy-vercel', 'verify-live-reports', 'post-alerts'])

    def test_child_cannot_claim_nonexistent_parent_guard(self):
        lock = self.root / 'writer.lock'
        lock.write_text(json.dumps({'pid': 1}))
        with patch.object(upload.report_storage, 'LOCK', lock):
            with self.assertRaisesRegex(ValueError, 'parent does not own'):
                upload.require_parent_lock()

    def test_parent_guard_is_checked_across_real_processes(self):
        lock = self.root / 'guard.lock'
        code = ('import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); '
                'import vercel_upload as u; u.report_storage.LOCK=Path(sys.argv[2]); u.require_parent_lock()')
        command = [sys.executable, '-c', code, str(ROOT / 'scripts/weekly_report'), str(lock)]
        with upload.report_storage.writer_lock('fixture-parent', lock):
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_receipt_cannot_write_through_dotdot_into_rollback_notebook(self):
        client = FakeClient()
        path = self.root / 'base/../base/notebook/transport.json'
        with self.assertRaisesRegex(ValueError, 'outside immutable notebooks'):
            upload.deploy_prepared(self.notebook, self.base, self.manifest, path, client)
        self.assertEqual(client.uploads, 0)

    def test_preflight_does_not_create_tool_cache_or_upload(self):
        before = sorted(str(p) for p in self.root.rglob('*'))
        with patch.object(upload, 'toolchain', return_value=(Path('/node'), Path('/vendor'))), \
                patch.object(upload, 'prepare_cli') as prepare, patch.object(upload.Client, 'upload') as send, \
                patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(upload.main(['--check', '--notebook', str(self.notebook)]), 0)
        self.assertFalse(prepare.called)
        self.assertFalse(send.called)
        self.assertEqual(sorted(str(p) for p in self.root.rglob('*')), before)

    def test_inspection_auth_failure_is_not_retried(self):
        client = upload.Client(Path('/node'), Path('/vendor'))
        failed = subprocess.CompletedProcess([], 1, '', 'Error: Unauthorized (401)')
        with patch.object(upload.subprocess, 'run', return_value=failed) as run, patch.object(upload.time, 'sleep') as sleep:
            with self.assertRaisesRegex(ValueError, 'authentication/permissions'):
                client.inspect('dpl_new')
        self.assertEqual(run.call_count, 1)
        self.assertFalse(sleep.called)

    def test_inspection_transient_failure_retries_reads_only(self):
        client = upload.Client(Path('/node'), Path('/vendor'))
        good = subprocess.CompletedProcess([], 0, json.dumps({'id': 'dpl_new', 'url': 'fixture',
            'name': 'market-notebook', 'target': 'production', 'contextName': 'headout', 'readyState': 'READY'}), '')
        with patch.object(upload.subprocess, 'run', side_effect=[subprocess.TimeoutExpired('inspect', 45), good]) as run, \
                patch.object(upload.time, 'sleep'):
            self.assertEqual(client.inspect('dpl_new')['id'], 'dpl_new')
        self.assertEqual(run.call_count, 2)
        self.assertTrue(all('deploy' not in call.args[0] for call in run.call_args_list))

    def test_client_upload_returns_created_id_without_watching_build(self):
        client = upload.Client(Path('/node'), Path('/vendor'))
        def simulate(command, **kwargs):
            self.assertIn('--archive=tgz', command)
            self.assertIn('--no-wait', command)
            self.assertIn('--format=json', command)
            self.assertIn(str(self.notebook), command)
            self.assertEqual(kwargs['timeout'], 90 * 60)
            kwargs['stdout'].write(json.dumps({'deployment': {'id': 'dpl_new'}}))
            kwargs['stdout'].flush()
            return subprocess.CompletedProcess(command, 0)
        with patch.object(upload, 'prepare_cli', return_value=self.root / 'tool'), \
                patch.object(upload.subprocess, 'run', side_effect=simulate) as run:
            code, ref = client.upload(self.notebook, 'manifest-hash', self.receipt)
        self.assertEqual((code, ref), (0, 'dpl_new'))
        self.assertEqual(run.call_count, 1)
        self.assertEqual(upload.files(self.notebook), self.before)

    def test_large_upload_timeout_is_bounded_and_still_stops_without_identity(self):
        client=upload.Client(Path('/node'),Path('/vendor'))
        with patch.object(upload,'prepare_cli',return_value=self.root/'tool'), patch.object(
                upload.subprocess,'run',side_effect=subprocess.TimeoutExpired('upload',90*60)) as run:
            self.assertEqual(client.upload(self.notebook,'manifest-hash',self.receipt),(124,None))
        self.assertEqual(run.call_args.kwargs['timeout'],5400)
        self.assertEqual(run.call_count,1)
        self.assertEqual(upload.files(self.notebook),self.before)


if __name__ == '__main__':
    unittest.main()
