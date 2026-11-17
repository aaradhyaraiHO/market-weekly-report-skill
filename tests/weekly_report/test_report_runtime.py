import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scripts/weekly_report'))
import report_runtime as runtime
import report_release as release
from google.cloud import bigquery

class RuntimeTests(unittest.TestCase):
    def test_only_tighter_caps_allowed(self):
        self.assertEqual(runtime.cap_config(bigquery.QueryJobConfig()).maximum_bytes_billed, 80*1024**3)
        self.assertEqual(runtime.cap_config(bigquery.QueryJobConfig(maximum_bytes_billed=1)).maximum_bytes_billed, 1)
        with self.assertRaises(ValueError):
            runtime.cap_config(bigquery.QueryJobConfig(maximum_bytes_billed=140*1024**3))

    def test_unbounded_http_is_finite_and_shorter_timeouts_preserved(self):
        self.assertEqual(runtime.bounded_timeout(None), (15,60))
        self.assertEqual(runtime.bounded_timeout((None,None)), (15,60))
        self.assertEqual(runtime.bounded_timeout((2,3)), (2,3))
        self.assertEqual(runtime.bounded_timeout(300), 60)

    def test_acknowledged_job_reused_without_serializing_rows(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'REPORT_QUERY_JOURNAL':str(Path(root).resolve())}):
            c=Mock(project='headout-analytics',location='EU'); job=Mock(job_id='job_one',error_result=None)
            original=Mock(return_value=job); c.get_job.return_value=job
            cfg=runtime.cap_config(bigquery.QueryJobConfig())
            self.assertIs(runtime.submit(c,'SELECT 1',cfg,original,{}),job)
            self.assertIs(runtime.submit(c,'SELECT 1',cfg,original,{}),job)
            self.assertEqual(original.call_count,1)
            self.assertEqual(c.get_job.call_count,1)
            text=next(Path(root).glob('*.json')).read_text()
            self.assertNotIn('SELECT 1',text); self.assertNotIn('rows',text)

    def test_lost_ack_stops_without_replaying_query(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'REPORT_QUERY_JOURNAL':str(Path(root).resolve())}):
            c=Mock(project='p',location='EU');original=Mock(side_effect=TimeoutError())
            cfg=runtime.cap_config(bigquery.QueryJobConfig())
            with self.assertRaises(TimeoutError): runtime.submit(c,'SELECT 1',cfg,original,{})
            c.get_job.side_effect=RuntimeError('missing or permission unavailable')
            with self.assertRaisesRegex(RuntimeError,'no query replayed'):
                runtime.submit(c,'SELECT 1',cfg,original,{})
            self.assertEqual(original.call_count,1)

    def test_independent_gate_cannot_inherit_producer_cache(self):
        step=Mock(name='unused');step.name='source-reconciliation';step.command=('python3','gate.py')
        argv,env,deadline=release.execution(step,Path('/package'),{'REPORT_QUERY_JOURNAL':'/old'})
        self.assertNotIn('REPORT_QUERY_JOURNAL',env)
        self.assertTrue(argv[1].endswith('report_bootstrap.py'))
        self.assertLessEqual(deadline,3600)

    def test_wrapper_preserves_non_python_and_module_commands(self):
        for argv in (['node','x.js'], ['python3','-m','unittest'], ['vercel','deploy']):
            self.assertEqual(runtime.command(argv),argv)

    def test_bootstrap_preserves_normal_site_packages_and_children(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'probe.py';child=Path(root)/'child.py'
            child.write_text('import requests, numpy\nfrom google.cloud import bigquery\nassert bigquery.Client._report_runtime_installed\nprint("child guarded")\n')
            p.write_text('import requests, numpy, subprocess, sys\nfrom google.cloud import bigquery\nassert bigquery.Client._report_runtime_installed\nsubprocess.run([sys.executable,sys.argv[1]],check=True)\n')
            result=subprocess.run(runtime.command([sys.executable,str(p),str(child)]),capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('child guarded',result.stdout)

if __name__=='__main__':unittest.main()

class ProcessDeadlineTests(unittest.TestCase):
    def test_deadline_terminates_descendants_before_return(self):
        import signal,time
        with tempfile.TemporaryDirectory() as root:
            pidfile=Path(root)/'child.pid'
            script=Path(root)/'parent.py'
            script.write_text('import subprocess,sys,time\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(100)"])\nopen(sys.argv[1],"w").write(str(p.pid))\ntime.sleep(100)\n')
            with self.assertRaises(subprocess.TimeoutExpired):
                release.run_bounded([sys.executable,str(script),str(pidfile)],cwd=root,env=dict(os.environ),timeout=1)
            pid=int(pidfile.read_text())
            result=subprocess.run(['ps','-p',str(pid),'-o','stat='],text=True,capture_output=True,timeout=5)
            self.assertTrue(result.returncode != 0 or result.stdout.strip().startswith('Z'),result.stdout)

class ArtifactCheckpointTests(unittest.TestCase):
    def test_only_complete_unchanged_artifacts_are_reused(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'REPORT_QUERY_JOURNAL':str(Path(root).resolve())}):
            path=Path(root).resolve()/'snapshot.json';build=Mock(side_effect=lambda:path.write_text('frozen'))
            self.assertFalse(runtime.artifact_checkpoint('market',{'week':'2026-11-08'},[path],build))
            self.assertTrue(runtime.artifact_checkpoint('market',{'week':'2026-11-08'},[path],build))
            self.assertEqual(build.call_count,1)
            with self.assertRaisesRegex(ValueError,'inputs changed'):
                runtime.artifact_checkpoint('market',{'week':'2026-11-15'},[path],build)
            path.write_text('changed')
            with self.assertRaisesRegex(ValueError,'artifact changed'):
                runtime.artifact_checkpoint('market',{'week':'2026-11-08'},[path],build)
            self.assertEqual(build.call_count,1)
