from django.core.cache import cache

from corehq.apps.celery import serial_task

from .table_ddl import create_or_update_project_db


def _sync_queued_key(domain):
    return f'project-db-sync-queued-{domain}'


def schedule_project_db_sync(domain):
    """Queue a schema sync unless one is already queued for the domain"""
    if cache.add(_sync_queued_key(domain), True, timeout=5 * 60):
        # Schedule the task with a 15 second debounce delay
        update_project_db_schema.apply_async([domain], countdown=15)


@serial_task('{domain}', timeout=30 * 60)
def update_project_db_schema(domain):
    cache.delete(_sync_queued_key(domain))
    create_or_update_project_db(domain)
