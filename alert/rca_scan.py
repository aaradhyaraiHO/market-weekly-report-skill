"""Exact, bounded funnel scans using only BigQuery's temporary query results.

No daily counts are summed: retain DISTINCT source rows, UNION ALL the disjoint
date slices, and run the original weekly COUNT(DISTINCT user_id) expressions.
No permanent tables, credentials, user-level downloads or metric fallbacks.
"""
import datetime as dt
import logging
import re

from google.cloud import bigquery

SOURCE = '`headout-analytics.analytics_reporting.mixpanel_user_page_funnel_progression`'
FIELDS = (
    'event_date', 'combined_entity_id', 'advertising_channel_type', 'channel_name',
    'user_id', 'has_select_page_viewed', 'select_page_viewed_timestamp',
    'has_checkout_started', 'checkout_started_timestamp', 'has_order_completed',
    'order_completed_timestamp', 'session_start_timestamp',
)
log = logging.getLogger(__name__)


def byte_cap_error(error):
    reasons = [r.get('reason') for r in (getattr(error, 'errors', None) or [])]
    return 'bytesBilledLimitExceeded' in reasons or any(
        text in str(error).lower() for text in (
            'bytesbilledlimitexceeded', 'limit for bytes billed',
            'maximum bytes billed', 'maximum_bytes_billed', 'bytes billed limit',
        )
    )


def bounded_dataframe(client, sql, ce_ids, start, end, config_factory, quote):
    """Keep the normal one-job path; use exact date slices only on a byte cap."""
    try:
        return client.query(sql, job_config=config_factory()).to_dataframe()
    except Exception as error:
        if not byte_cap_error(error):
            raise
        log.warning('RCA funnel scan exceeded cap; preparing exact bounded source slices')
    return sliced_dataframe(client, sql, ce_ids, start, end, config_factory, quote)


def sliced_dataframe(client, sql, ce_ids, start, end, config_factory, quote):
    if sql.count(SOURCE) != 1 or not ce_ids or end < start:
        raise ValueError('Unsupported RCA source/window; cannot safely split scan')
    # All source slices use the same warehouse snapshot, even across retries.
    as_of = dt.datetime.now(dt.timezone.utc).isoformat()
    quoted_ids = ', '.join(quote(value) for value in ce_ids)
    tables = []

    def scan(left, right):
        query = f"""SELECT DISTINCT {', '.join(FIELDS)}
FROM {SOURCE} FOR SYSTEM_TIME AS OF TIMESTAMP('{as_of}')
WHERE event_date BETWEEN DATE('{left.isoformat()}') AND DATE('{right.isoformat()}')
  AND combined_entity_id IN ({quoted_ids})
  AND (advertising_channel_type <> 'PERFORMANCE_MAX' OR advertising_channel_type IS NULL)"""
        config = config_factory()
        config.dry_run = True
        config.use_query_cache = False
        estimate = client.query(query, job_config=config).total_bytes_processed
        if estimate is None:
            raise ValueError('RCA source scan estimate unavailable')
        if estimate > config.maximum_bytes_billed:
            if left == right:
                raise ValueError(f'RCA single-day source {left} requires {estimate} bytes; cap unchanged')
            middle = left + (right - left) // 2
            scan(left, middle)
            scan(middle + dt.timedelta(days=1), right)
            return
        job = client.query(query, job_config=config_factory())
        job.result()  # Finish before referencing its private temporary result.
        ref = job.destination
        if ref is None or not ref.dataset_id.startswith('_'):
            raise ValueError('Expected anonymous query-result table; refusing permanent destination')
        parts = (ref.project, ref.dataset_id, ref.table_id)
        if any(not re.fullmatch(r'[A-Za-z0-9_-]+', value) for value in parts):
            raise ValueError('Invalid query-result table identifier')
        tables.append('`' + '.'.join(parts) + '`')
        log.info('RCA source slice %s..%s: %s bytes processed (cap %s)',
                 left, right, job.total_bytes_processed, config.maximum_bytes_billed)

    scan(start, end)
    source = '(' + ' UNION ALL '.join('SELECT * FROM ' + table for table in tables) + ')'
    # Keep all original grouping, joins, null handling and DISTINCT expressions.
    return client.query(sql.replace(SOURCE, source), job_config=config_factory()).to_dataframe()
