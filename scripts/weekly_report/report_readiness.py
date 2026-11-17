"""Read-only shared dependency preflight before generation or notebook copies."""
import argparse
import datetime as dt
import json
from pathlib import Path
from google.cloud import bigquery
import config
from bq import client
from report_contract import AD_COSTS, OTHER_COSTS, CONTRACT_VERSION
from report_runtime import cap_config, atomic

REQUIRED = {
    'combined_entity_stats': {'combined_entity_id','business_market','report_date','report_timestamp',
        'sum_revenue_predicted','sum_revenue','sum_order_value','count_orders',
        'sum_co_marketing_commission','sum_insider_commission','sum_direct_costs',*AD_COSTS,*OTHER_COSTS},
    'fct_orders_lambda': {'order_id','created_at','amount_revenue_usd','combined_entity_id'},
    'fct_bookings_lambda': {'order_id','booking_id'},
    'revenue_goals': {'target_month','entity_type','market','target_revenue'},
}


def check(month, bq=None):
    bq=bq or client()
    errors=[]; evidence={}
    for name, required in REQUIRED.items():
        table=bq.get_table(f'{config.BQ_PROJECT}.{config.BQ_DATASET}.{name}',timeout=30)
        fields={f.name for f in table.schema}
        missing=sorted(required-fields)
        evidence[name]={'required_columns':sorted(required),'missing_columns':missing}
        if missing:errors.append(f'{name}: missing required columns {missing}')
    if errors:raise ValueError('; '.join(errors))
    # An actual Drive-backed read catches missing Drive scope; metadata/dry-run cannot prove it.
    cfg=cap_config(bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter('month','DATE',month+'-01')],
        labels={'tool':'report_release','step':'dependency_preflight'}))
    rows=list(bq.query('SELECT COUNT(*) AS n FROM `headout-analytics.analytics_reporting.revenue_goals` '
        "WHERE target_month=@month AND entity_type IN ('Market','Combined Entity')",job_config=cfg,timeout=30).result(timeout=120))
    if len(rows)!=1 or int(rows[0]['n'])<=0:raise ValueError('No approved revenue goals for requested month')
    return {'schema':'report-dependency-readiness/v1','status':'passed','month':month,
        'contract':CONTRACT_VERSION,'observed_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'schemas':evidence,'drive_goals_read':'passed','goal_rows':int(rows[0]['n']),
        'limitations':['Read permission and required schema only; source reconciliation and browser proof remain required']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--month',required=True);p.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    try: result=check(args.month)
    except Exception as exc:
        atomic(args.out,{'status':'failed','error_type':type(exc).__name__,'observed_at':dt.datetime.now(dt.timezone.utc).isoformat()})
        raise
    atomic(args.out,result);print(json.dumps({'status':result['status'],'receipt':str(args.out)}))
if __name__=='__main__':main()
