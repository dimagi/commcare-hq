from collections import defaultdict
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from celery.exceptions import Retry
from celery.schedules import crontab
from psycopg2 import errorcodes
from sqlalchemy.exc import OperationalError

from corehq.apps.celery import periodic_task, task

from .models import PendingOperation
from .populate import backfill_typed_columns
from .table_ddl import CaseTable, create_or_update_project_db


def schedule_project_db_sync(domain):
    """Record that the domain needs a schema sync, and queue processing"""
    PendingOperation.objects.create(domain=domain, operation=PendingOperation.Operation.SYNC)
    transaction.on_commit(lambda: _queue_processing(domain))


def _queue_processing(domain):
    """Queue an update unless one is already queued or running for the domain"""
    if cache.add(_processing_queued_key(domain), True, timeout=60 * 60):
        # Schedule the task with a 15 second debounce delay
        _process_pending_operations.apply_async([domain], countdown=15)


def _processing_queued_key(domain):
    return f'project-db-processing-queued-{domain}'


@periodic_task(run_every=crontab(minute=0), queue='background_queue')
def queue_stale_pending_operations():
    """Requeue processing for domains whose operations were lost or failed"""
    cutoff = timezone.now() - timedelta(hours=1)
    domains = (
        PendingOperation.objects.filter(created_on__lt=cutoff)
        .values_list('domain', flat=True).distinct()
    )
    for domain in domains:
        _queue_processing(domain)


@task(bind=True, queue='background_queue', ignore_result=True, default_retry_delay=30)
def _process_pending_operations(self, domain):
    with _ProcessingLock(domain):
        try:
            _apply_pending_sync(domain)
            _apply_pending_backfills(domain)
        except OperationalError as err:
            if err.orig.pgcode == errorcodes.LOCK_NOT_AVAILABLE:
                raise self.retry(exc=err)  # Couldn't get a write lock, retry
            raise

    # Requeue operations recorded during this run
    if PendingOperation.objects.filter(domain=domain).exists():
        _queue_processing(domain)


class _ProcessingLock:
    """Clear the lock at the end unless we're retrying"""
    def __init__(self, domain):
        self.key = _processing_queued_key(domain)

    def __enter__(self):
        ...

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not Retry:
            cache.delete(self.key)


def _apply_pending_sync(domain):
    sync_ids = list(PendingOperation.objects.filter(
        domain=domain, operation=PendingOperation.Operation.SYNC,
    ).values_list('id', flat=True))
    if sync_ids:
        create_or_update_project_db(domain)
        # Delete only syncs present before update started
        PendingOperation.objects.filter(id__in=sync_ids).delete()


def _apply_pending_backfills(domain):
    pending_ops = defaultdict(list)
    for op in PendingOperation.objects.filter(
        domain=domain, operation=PendingOperation.Operation.BACKFILL,
    ):
        pending_ops[op.args['case_type']].append(op)

    for case_type, ops in pending_ops.items():
        if (table := CaseTable(domain, case_type).reflect()) is not None:
            column_names = {name for op in ops for name in op.args['columns']}
            if columns := [col for col in table.c if col.name in column_names]:
                backfill_typed_columns(table, columns)
        PendingOperation.objects.filter(id__in=[op.id for op in ops]).delete()
