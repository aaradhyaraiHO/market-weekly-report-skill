import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/weekly_report'))
import report_readiness as r

class ReadinessTests(unittest.TestCase):
    def client(self):
        c=Mock()
        c.get_table.side_effect=lambda name,**kw:Mock(schema=[Mock(name='') for _ in []])
        def table(name,**kw):
            fields=[]
            for name in r.REQUIRED[name.split('.')[-1]]:
                f=Mock();f.name=name;fields.append(f)
            return Mock(schema=fields)
        c.get_table.side_effect=table;c.query.return_value.result.return_value=[{'n':1}]
        return c
    def test_real_drive_read_is_required(self):
        c=self.client();self.assertEqual(r.check('2026-11',c)['status'],'passed')
        c.query.assert_called_once();self.assertFalse(c.query.call_args.kwargs['job_config'].dry_run)
        c.query.return_value.result.side_effect=PermissionError('scope unavailable')
        with self.assertRaises(PermissionError):r.check('2026-11',c)
    def test_schema_gap_stops_before_query(self):
        c=self.client();c.get_table.side_effect=None;c.get_table.return_value=Mock(schema=[])
        with self.assertRaisesRegex(ValueError,'missing required columns'):r.check('2026-11',c)
        c.query.assert_not_called()
