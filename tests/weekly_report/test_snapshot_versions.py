import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/weekly_report'))
import snapshot_versions as v

class SnapshotVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve();self.slug='csee';self.week='2026-11-01'
        self.name=f'snapshot_{self.slug}_{self.week}.json'
        self.original=self.root/self.name;self.original.write_text(json.dumps({'value':'original'}))
        self.new=self.root/'correction/snapshots'/self.name;self.new.parent.mkdir(parents=True)
        self.new.write_text(json.dumps({'meta':{'market_slug':self.slug,'week_start':self.week},'value':'corrected'}))
        self.sha=hashlib.sha256(self.new.read_bytes()).hexdigest()
        self.receipt=self.root/'correction/deployment_receipt.json'
        self.receipt.write_text(json.dumps(dict(status='verified',week=self.week,snapshot_dir=str(self.new.parent),snapshots={self.name:self.sha})))
        self.index=dict(schema=v.SCHEMA,weeks={self.week:{self.slug:dict(snapshot=str(self.new),sha256=self.sha,receipt=str(self.receipt))}})
    def activate(self): (self.root/v.REGISTRY).write_text(json.dumps(self.index))
    def load(self): return v.load_prior(self.root,self.slug,self.week)
    def test_no_correction_preserves_existing_read_behavior(self):
        self.assertEqual(self.load()['value'],'original')
        self.assertIsNone(v.load_prior(self.root,'absent',self.week))
    def test_verified_correction_is_used_without_rewriting_original(self):
        before=self.original.read_bytes();self.activate()
        self.assertEqual(self.load()['value'],'corrected');self.assertEqual(self.original.read_bytes(),before)
    def test_tampered_or_unverified_correction_never_falls_back(self):
        self.activate();self.new.write_text('{}')
        with self.assertRaises(v.CorrectionEvidenceError):self.load()
        self.new.write_text(json.dumps({'meta':{'market_slug':self.slug,'week_start':self.week},'value':'corrected'}))
        data=json.loads(self.receipt.read_text());data['status']='staged';self.receipt.write_text(json.dumps(data))
        with self.assertRaises(v.CorrectionEvidenceError):self.load()
    def test_symlinks_and_out_of_cache_paths_are_rejected(self):
        self.activate();target=self.new.with_suffix('.saved');self.new.rename(target);self.new.symlink_to(target)
        with self.assertRaises(v.CorrectionEvidenceError):self.load()
        self.index['weeks'][self.week][self.slug]['snapshot']='/tmp/'+self.name;self.activate()
        with self.assertRaises(v.CorrectionEvidenceError):self.load()
    def test_corrupt_registry_never_reverts_to_the_old_snapshot(self):
        (self.root/v.REGISTRY).write_text('{broken')
        with self.assertRaises(v.CorrectionEvidenceError):self.load()

if __name__=='__main__':unittest.main()
