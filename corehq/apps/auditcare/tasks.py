import logging
import re
from datetime import UTC, date, datetime

from django.conf import settings
from django.db import connections, router

from celery.schedules import crontab
from dateutil.relativedelta import relativedelta
from psycopg2 import sql

from dimagi.utils.logging import notify_error, notify_exception

from corehq.apps.celery import periodic_task
from corehq.util.metrics import metrics_gauge

from .models import AccessAudit, NavigationEventAudit

log = logging.getLogger(__name__)

MODELS_TO_PRUNE = [NavigationEventAudit, AccessAudit]


@periodic_task(
    run_every=crontab(hour=2, minute=0, day_of_month='1'),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery'),
)
def prune_auditcare_tables():
    """Drop partitions older than ``AUDITCARE_RETENTION_YEARS``."""
    cutoff = datetime.now(UTC).date() - relativedelta(
        years=settings.AUDITCARE_RETENTION_YEARS
    )
    for model in MODELS_TO_PRUNE:
        try:
            dropped = _drop_expired_partitions(model, cutoff)
        except Exception:
            notify_exception(
                None,
                'Error pruning auditcare partitions',
                details={
                    'model': model.__name__,
                },
            )
        else:
            metrics_gauge(
                'commcare.auditcare.partitions_dropped',
                dropped,
                tags={'model': model.__name__},
            )


def _get_partitions_for_base_table(db, base_table):
    """Return the names of ``base_table``'s partitions from Postgres"""
    with connections[db].cursor() as cursor:
        cursor.execute(
            'SELECT tablename FROM pg_tables WHERE tablename LIKE %s',
            [f'{base_table}_y%m%'],
        )
        return [row[0] for row in cursor.fetchall()]


def _get_partitions_to_drop(existing_table_names, base_table, cutoff_date):
    """Return partitioned tables whose month and year is older than ``cutoff_date``"""
    table_name_pattern = re.compile(
        rf'^{re.escape(base_table)}_y(\d{{4}})m(\d{{2}})$'
    )
    cutoff_month = date(cutoff_date.year, cutoff_date.month, 1)

    def is_expired(match):
        year, month = int(match.group(1)), int(match.group(2))
        # only strictly older months are dropped
        return date(year, month, 1) < cutoff_month

    matches = (table_name_pattern.match(name) for name in existing_table_names)
    return [match.group(0) for match in matches if match and is_expired(match)]


def _drop_expired_partitions(model, cutoff):
    db = router.db_for_write(model)
    base_table = model._meta.db_table
    partitioned_tables = _get_partitions_for_base_table(db, base_table)
    to_drop = _get_partitions_to_drop(partitioned_tables, base_table, cutoff)
    dropped = 0
    for table_name in sorted(to_drop):
        newest = _get_newest_event_date(db, table_name)
        if newest is not None and newest.date() >= cutoff:
            notify_error(
                f'Refusing to drop auditcare partition {table_name}: its name '
                f'says it predates the {cutoff} retention cutoff but it holds '
                f'rows up to {newest}'
            )
            continue
        with connections[db].cursor() as cursor:
            cursor.execute(
                sql.SQL('DROP TABLE IF EXISTS {}').format(
                    sql.Identifier(table_name)
                )
            )
        log.info(
            'Dropped expired auditcare partition %s (retention cutoff %s)',
            table_name,
            cutoff,
        )
        dropped += 1
    return dropped


def _get_newest_event_date(db, table_name):
    """Return the newest ``event_date`` in the partition, or None if it is empty"""
    with connections[db].cursor() as cursor:
        cursor.execute(
            sql.SQL('SELECT MAX(event_date) FROM {}').format(
                sql.Identifier(table_name)
            )
        )
        return cursor.fetchone()[0]
