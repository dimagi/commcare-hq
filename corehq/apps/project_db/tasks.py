from django.core.cache import cache

from psycopg2 import errorcodes
from sqlalchemy.exc import OperationalError

from corehq.apps.celery import serial_task

from .populate import backfill_typed_columns
from .table_ddl import CaseTable, create_or_update_project_db


def _sync_queued_key(domain):
    return f'project-db-sync-queued-{domain}'


def schedule_project_db_sync(domain):
    """Queue a schema sync unless one is already queued for the domain"""
    if cache.add(_sync_queued_key(domain), True, timeout=5 * 60):
        # Schedule the task with a 15 second debounce delay
        update_project_db_schema.apply_async([domain], countdown=15)


@serial_task('{domain}', timeout=30 * 60, max_retries=3)
def update_project_db_schema(domain):
    cache.delete(_sync_queued_key(domain))
    try:
        to_backfill = create_or_update_project_db(domain)
    except OperationalError as err:
        if err.orig.pgcode == errorcodes.LOCK_NOT_AVAILABLE:
            update_project_db_schema.retry(exc=err)
        raise
    for case_type, column_names in to_backfill.items():
        backfill_project_db_columns.delay(domain, case_type, column_names)


@serial_task('{domain}-{case_type}', timeout=60 * 60)
def backfill_project_db_columns(domain, case_type, column_names):
    table = CaseTable(domain, case_type).reflect()
    if table is not None:
        backfill_typed_columns(table, [table.c[name] for name in column_names])
