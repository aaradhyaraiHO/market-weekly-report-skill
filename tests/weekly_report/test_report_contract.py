import datetime as dt
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts/weekly_report'))
import report_contract as c

class ContractTests(unittest.TestCase):
    def test_independent_omni_operand_inventory(self):
        # Literal reviewed source inventory; does not derive expectations from producer constants.
        expected={'sum_google_ads_spend','sum_google_split_ads_spend','sum_google_brand_ads_spend',
            'sum_google_remarketing_ads_spend','sum_pmax_ads_spend','sum_travel_ads_spend',
            'sum_microsoft_ads_spend','sum_microsoft_split_ads_spend','sum_microsoft_brand_ads_spend',
            'sum_microsoft_remarketing_ads_spend','sum_facebook_ads_spend','sum_facebook_split_ads_spend',
            'sum_facebook_remarketing_ads_spend','sum_apple_ads_spend','sum_criteo_remarketing_ads_spend'}
        self.assertEqual(set(c.AD_COSTS),expected); self.assertEqual(len(c.AD_COSTS),15)
        self.assertIn('COALESCE(sum_microsoft_brand_ads_spend, 0)',c.ad_cost_sql(null_policy='bing_only'))
        self.assertNotIn('COALESCE(sum_google_ads_spend',c.ad_cost_sql(null_policy='bing_only'))
        self.assertEqual(c.ad_cost_sql(null_policy='all_zero').count('COALESCE('),15)

    def test_q4_company_goal_is_90_and_no_2027_target_inferred(self):
        self.assertEqual(c.COMPANY_TARGETS[4][c.OKR_IDS[3]],'+90% YoY')
        self.assertEqual(c.COMPANY_GEL_TARGET_SOURCE['source_cells'][4],'G30')

    def test_status_needs_target_baseline_and_complete_week_progress(self):
        kw=dict(cutoff=dt.date(2026,11,14),value=49,revenue_ly=100,target=90)
        self.assertEqual(c.gel_progress(**kw)['status'],'At risk')
        self.assertEqual(c.gel_progress(**{**kw,'target':None})['status'],'Status unavailable')
        self.assertEqual(c.gel_progress(**{**kw,'revenue_ly':0})['status'],'Status unavailable')
        self.assertEqual(c.gel_progress(**{**kw,'cutoff':dt.date(2026,10,10)})['status'],'Tracking')
