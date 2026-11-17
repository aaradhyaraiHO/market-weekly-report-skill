import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/weekly_report'))
import report_baseline as b

class BaselineTests(unittest.TestCase):
    def test_only_verified_unchanged_canonical_deployment_can_be_retained(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root).resolve();base=p/'base/notebook';target=p/'new/notebook';base.mkdir(parents=True);target.mkdir(parents=True)
            (target/'history.html').write_text('history and audit code unchanged')
            manifest=p/'new/artifact.json';manifest.write_text(json.dumps({'month':'2026-10'}))
            proof=p/'new/proof.json';proof.write_text(json.dumps({'status':'verified','method':'signed-in-browser',
                'observations':[],'manifest_sha256':'proofhash'}))
            transport=p/'new/transport.json';transport.write_text(json.dumps({'status':'ready_for_browser_verification',
                'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'deployment_id':'dpl_new',
                'notebook':str(target),'base_notebook':str(base)}))
            client=Mock();client.inspect.return_value={'id':'dpl_new','readyState':'READY','url':'fixture'}
            validator=Mock(return_value={'manifest_sha256':'proofhash'})
            with patch.object(b,'check_project'),patch.object(b.report_storage,'STATE',p/'state'):
                result=b.finalize(target,base,manifest,proof,transport,client,cadence='monthly',validator=validator)
                self.assertEqual(result['files'],b.files(target))
                self.assertEqual(json.loads((p/'state/current_production.json').read_text())['deployment_id'],'dpl_new')
                client.inspect.return_value['id']='dpl_other'
                with self.assertRaisesRegex(ValueError,'advanced'):
                    b.finalize(target,base,manifest,proof,transport,client,cadence='monthly',validator=validator)
                self.assertEqual(json.loads((target.parent/'deployment_receipt.json').read_text())['deployment_id'],'dpl_new')
