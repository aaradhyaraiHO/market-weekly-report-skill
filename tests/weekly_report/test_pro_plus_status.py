"""Verified central stock/flow statuses, isolated from all report measurements."""
import copy
import datetime as dt
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts/weekly_report'))
spec = importlib.util.spec_from_file_location('pro_plus_builder', ROOT/'alert/v2/build_market_okr_results.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ProPlusStatus(unittest.TestCase):
    week = dt.date(2026, 10, 25)

    def history(self, values=None, week=None):
        week = week or self.week
        return [{'week': str(week-dt.timedelta(weeks=5-i)), 'value': v}
                for i,v in enumerate(values or [489,493,492,495,492,487])]

    def row(self, index=0, value=487, reached=2):
        row = {'id': builder.OKR_IDS[index], 'value':value,
               'target':builder.COMPANY_TARGETS[4][builder.OKR_IDS[index]],
               'drilldown':{'ce_ids':[str(i) for i in range(value)]}}
        if index:
            row['reached'] = reached
        return row

    def status(self, row=None, history=None, week=None, slug='headout'):
        return builder._pro_plus_status(slug=slug,week_start=week or self.week,
                                       row=row or self.row(),history=history)

    def test_verified_six_week_projection_not_current_count_attainment(self):
        row = self.row(); original = copy.deepcopy(row)
        result = self.status(row,self.history())
        self.assertEqual(result['status'], ':large_yellow_circle: At risk')
        self.assertAlmostEqual(result['status_slope'], -2/7)
        self.assertAlmostEqual(result['status_projected_value'],484.42857142857144)
        self.assertEqual(result['status_weeks_ahead'],9)
        self.assertEqual(result['status_target_cell'],'G13')
        self.assertEqual(row,original)

    def test_stock_can_be_on_track_below_current_target_using_projection(self):
        result=self.status(self.row(value=500),self.history([450,460,470,480,490,500]))
        self.assertEqual(result['status'],':large_green_circle: On track')
        self.assertEqual(result['status_projected_value'],590)

    def test_flow_is_achieved_or_projected_not_linear_ramp(self):
        for index,value in ((1,26),(2,9)):
            result=self.status(self.row(index,value))
            self.assertEqual(result['status'],':large_yellow_circle: At risk')
            self.assertEqual(result['status_projected_value'],value)
            self.assertEqual(result['status_reached'],2)
            self.assertEqual(result['status_target_cell'],{1:'G24',2:'G25'}[index])
        self.assertEqual(self.status(self.row(1,45))['status'],':large_green_circle: On track')
        self.assertEqual(self.status(self.row(2,25))['status'],':large_green_circle: On track')

    def test_early_quarter_remains_neutral(self):
        week=dt.date(2026,10,18)
        self.assertEqual(self.status(self.row(1,26),week=week)['status'],'Tracking')
        self.assertEqual(self.status(self.row(),self.history(week=week),week)['status'],'Tracking')

    def test_no_market_or_future_quarter_company_fallback(self):
        self.assertEqual(self.status(self.row(1,26),slug='italy')['status'],'Status unavailable')
        self.assertEqual(self.status(self.row(1,26),week=dt.date(2027,10,24))['status'],'Status unavailable')
        row=self.row(1,26);row['target']='55 CEs'
        self.assertEqual(self.status(row)['status'],'Status unavailable')

    def test_missing_stale_partial_or_invalid_history_never_becomes_flat(self):
        invalid=[None,[],self.history()[:-1],self.history(week=dt.date(2026,10,18)),
                 self.history([489,493,float('nan'),495,492,487]),
                 self.history([489,493,492,495,492,488]),
                 self.history([489,493,492,-1,492,487])]
        for history in invalid:
            with self.subTest(history=history):
                self.assertEqual(self.status(history=history)['status'],'Status unavailable')

    def test_invalid_counts_members_and_achieved_subsets_fail_closed(self):
        for field,value in (('value',None),('value',float('inf')),('value',-1),
                            ('value',26.5),('reached',None),('reached',27),('reached',-1)):
            row=self.row(1,26);row[field]=value
            self.assertEqual(self.status(row)['status'],'Status unavailable')
        row=self.row(1,26);row['drilldown']['ce_ids'][1]='0'
        self.assertEqual(self.status(row)['status'],'Status unavailable')
        row['drilldown']=None
        self.assertEqual(self.status(row)['status'],'Status unavailable')
        self.assertEqual(self.status(self.row(1,0,reached=0))['status'],':large_yellow_circle: At risk')

    def test_q3_q4_boundary_is_not_silently_scored_with_cross_quarter_data(self):
        row=self.row(1,26);row['target']='55 CEs'
        self.assertEqual(self.status(row,week=dt.date(2026,9,27))['status_reason'],
                         'quarter_boundary_unavailable')

    def test_builder_uses_status_evidence_without_changing_counts(self):
        raw={'market':'Headout','pro_plus_ces':487,'pro_plus_ce_ids':','.join(map(str,range(487))),
             'pro_plus_status_history':self.history(),'new_pro_plus_mature_on_pace':26,
             'new_pro_plus_mature_reached':2,'mature_ce_ids':','.join(map(str,range(26))),
             'new_pro_plus_emerging_growth_on_pace':9,'new_pro_plus_emerging_growth_reached':2,
             'emerging_growth_ce_ids':','.join(map(str,range(9)))}
        before=copy.deepcopy(raw)
        rows=builder.build_results([raw],{'headout':'Headout'},str(self.week))['markets']['headout']
        self.assertEqual([r['value'] for r in rows[:3]],[487,26,9])
        self.assertTrue(all(r['status']==':large_yellow_circle: At risk' for r in rows[:3]))
        self.assertEqual(raw,before)
        raw['new_pro_plus_mature_on_pace']=None;raw['mature_ce_ids']=None
        missing=builder.build_results([raw],{'headout':'Headout'},str(self.week))['markets']['headout'][1]
        self.assertEqual(missing['status'],'Status unavailable')

    def test_history_read_failure_does_not_replace_or_fail_core_measurements(self):
        import pandas as pd
        import bq
        raw={'market':'Headout','pro_plus_ces':487}
        with mock.patch.object(bq,'query_df',side_effect=[pd.DataFrame([raw]),RuntimeError('read failed')]):
            records,names=builder.query_results(str(self.week))
        self.assertEqual(records,[{**raw,'pro_plus_status_history':None}])

    def test_history_query_matches_central_13_week_six_checkpoint_contract(self):
        sql=builder.PRO_PLUS_STATUS_HISTORY_SQL
        for part in ('INTERVAL 119 DAY','INTERVAL 35 DAY','RANGE BETWEEN 84 PRECEDING',
                     'COUNTIF(l92 >= 10000)','DATE_ADD(DATE(@week_start), INTERVAL 6 DAY)'):
            self.assertIn(part,sql)


if __name__=='__main__':
    unittest.main()
