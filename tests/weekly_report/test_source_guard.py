import copy
import datetime as dt
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/weekly_report'))
import source_guard as g
import headline_v2

class SourceGuardTests(unittest.TestCase):
    def row(self, **kw):
        return dict(report_date=dt.date(2026,11,6),business_market='CSEE',ce_id='5266',
                    revenue=155.537,booked_revenue=164.1895,gbv=903.0805,
                    cm1_business=150,gross_marketing_cost=50,missing_revenue=0,**kw)

    def test_actual_november_six_incident_blocks_before_publication(self):
        row=self.row();row.update(revenue=-322022.0958389321,booked_revenue=-337249.3705)
        errors=g.anomalies([row])
        self.assertTrue(any('5266 2026-11-06: extreme negative revenue' in e for e in errors))
        self.assertTrue(any('booked_revenue' in e for e in errors))
        self.assertEqual(row['revenue'],-322022.0958389321)  # no clamping

    def test_corrected_input_and_small_refunds_are_allowed(self):
        self.assertFalse(g.anomalies([self.row()]))
        row=self.row();row.update(revenue=-50,booked_revenue=-60)
        self.assertFalse(g.anomalies([row]))

    def test_nan_missing_and_unknown_source_fail_closed(self):
        for value in (None,float('nan'),float('inf')):
            row=self.row();row['revenue']=value
            self.assertTrue(g.anomalies([row]))
        row=self.row();row['missing_revenue']=1
        self.assertTrue(g.anomalies([row]))
        row=self.row();row['revenue']=None
        with patch.object(g,'read_daily',return_value=[row]):
            result=g.check('2026-11-01',snapshots=['must-not-open.json'],goals={})
        self.assertEqual(result['status'],'failed')
        with patch.object(g,'read_daily',return_value=[]):
            self.assertEqual(g.check('2026-11-01')['status'],'failed')

    def goal(self):
        return dict(month='2026-11',forecast_authority=g.FORECAST_AUTHORITY,
            forecast_revenue=1520271.50481,forecast_source_revenue=1520271.50481,
            forecast_source_days=30,mtd_revenue=349508.15628658223,
            forecast_remaining_revenue=1520271.50481-349508.15628658223)

    def test_report_cannot_substitute_104_percent_for_goals_96_percent(self):
        goal=self.goal();self.assertFalse(g.validate_goal(goal))
        goal['forecast_revenue']=1635103.00965
        self.assertTrue(g.validate_goal(goal))
        goal=self.goal();goal.pop('forecast_authority')
        self.assertTrue(g.validate_goal(goal))
        goal=self.goal();goal['forecast_source_days']=29
        self.assertTrue(g.validate_goal(goal))

    def test_stale_snapshot_and_roi_drift_are_rejected(self):
        rows=[];weekly=[];ly=[]
        for offset in (0,-7,-364):
            day=dt.date(2026,11,1)+dt.timedelta(days=offset)
            row=self.row();row['report_date']=day;rows.append(row)
            fact=dict(week=str(day if offset!=-364 else dt.date(2026,11,1)),
                      revenue=155.537,cm1_business=150,gross_marketing_cost=50,roi1_pct=300)
            (ly if offset==-364 else weekly).append(fact)
        snapshot=dict(meta=dict(market_slug='headout',market='Headout',week_start='2026-11-01'),
                      market_summary=dict(weekly=weekly,weekly_ly=ly))
        self.assertFalse(g.reconcile(snapshot,rows)[0])
        bad=copy.deepcopy(snapshot);bad['market_summary']['weekly'][0]['revenue']=2302669
        self.assertTrue(g.reconcile(bad,rows)[0])
        bad=copy.deepcopy(snapshot);bad['market_summary']['weekly'][0]['roi1_pct']=112.04
        self.assertTrue(g.reconcile(bad,rows)[0])

    def test_guard_scans_true_global_and_approved_comparison_windows(self):
        import pandas as pd
        with patch.object(g, 'query_df', return_value=pd.DataFrame()) as query:
            g.read_daily('2026-11-01')
        sql,label,params=query.call_args.args
        self.assertNotIn('@market',sql)
        self.assertEqual(params['s0'],'2026-10-25')
        self.assertEqual(params['e0'],'2026-11-08')
        self.assertEqual(params['s1'],'2025-10-26')
        self.assertEqual(params['e1'],'2025-11-09')

    def test_forged_forecast_provenance_still_fails_independent_source_comparison(self):
        goal=self.goal();goal.update(forecast_revenue=1635103,forecast_source_revenue=1635103,
                                     forecast_remaining_revenue=1635103-goal['mtd_revenue'])
        self.assertFalse(g.validate_goal(goal))
        with patch.object(g,'read_daily',return_value=[self.row()]), patch.object(g,'read_month_forecasts',
                return_value=[dict(business_market='North America',revenue=1520271.50481,missing_revenue=0,days=30)]):
            result=g.check('2026-11-01',goals={'north_america':goal})
        self.assertEqual(result['status'],'failed')
        self.assertTrue(any('fresh Goals-authority source' in error for error in result['failures']))
        self.assertIn('headout',result['unavailable_goals'])

    def test_country_forecast_cannot_fall_back_to_four_week_extrapolation(self):
        goal=self.goal();goal.update(ce_target_pacing={'a':dict(monthly_goal=100,mtd_revenue=20)},
                                    ce_month_forecasts={'a':95},remaining_days=23)
        result=headline_v2._country_goal(goal,[dict(ce_id='a')],[dict(revenue=1000)],[])
        self.assertEqual(result['forecast_revenue'],95)
        goal['ce_month_forecasts']={}
        result=headline_v2._country_goal(goal,[dict(ce_id='a')],[dict(revenue=1000)],[])
        self.assertIsNone(result['forecast_revenue'])

if __name__=='__main__': unittest.main()
