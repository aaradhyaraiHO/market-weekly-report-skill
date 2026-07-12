"""
Thin BigQuery helper for the weekly report mart.

Returns query results as pandas DataFrames. Every query is labelled and
byte-capped per the analytics-skill hygiene rules.
"""
from __future__ import annotations

import pandas as pd
from google.cloud import bigquery

import config

_client: bigquery.Client | None = None


def client() -> bigquery.Client:
    global _client
    if _client is None:
        _client = bigquery.Client(project=config.BQ_PROJECT)
    return _client


def query_df(sql: str, label: str = "run", params: dict | None = None) -> pd.DataFrame:
    """
    Run `sql` and return a DataFrame. `params` maps @name -> value (str/int/float
    or list for @name IN UNNEST). Dates should be passed as ISO strings and cast
    in SQL, or as datetime.date (mapped to DATE params).
    """
    query_params = []
    for name, value in (params or {}).items():
        if isinstance(value, (list, tuple)):
            elem_type = "STRING"
            query_params.append(bigquery.ArrayQueryParameter(name, elem_type, list(value)))
        elif isinstance(value, bool):
            query_params.append(bigquery.ScalarQueryParameter(name, "BOOL", value))
        elif isinstance(value, int):
            query_params.append(bigquery.ScalarQueryParameter(name, "INT64", value))
        elif isinstance(value, float):
            query_params.append(bigquery.ScalarQueryParameter(name, "FLOAT64", value))
        else:
            query_params.append(bigquery.ScalarQueryParameter(name, "STRING", str(value)))

    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=config.MAX_BYTES_BILLED,
        query_parameters=query_params,
        labels={"tool": "weekly_report", "step": label[:63].lower()},
    )
    header = f"-- Query Run by Claude using Analytics-Skill [weekly_report:{label}]\n"
    job = client().query(header + sql, job_config=job_config)
    rows = [dict(r) for r in job.result()]
    return pd.DataFrame(rows)
