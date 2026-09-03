from corehq.apps.celery import serial_task
from corehq.util.quickcache import quickcache

from .table_ddl import create_or_update_project_db


@quickcache(['domain'], timeout=60 * 60, memoize_timeout=20)
def schedule_project_db_sync(domain):
    """Queue a schema sync unless one is already queued for the domain"""
    # Schedule the task with a 30 second debounce delay
    update_project_db_schema.apply_async([domain], countdown=30)


@serial_task('{domain}', timeout=30 * 60)
def update_project_db_schema(domain):
    schedule_project_db_sync.clear(domain)
    create_or_update_project_db(domain)
