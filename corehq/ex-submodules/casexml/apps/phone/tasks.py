import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import connections, router
from django.db.models import Min

from celery import current_app, current_task
from celery.schedules import crontab
from celery.signals import after_task_publish

from casexml.apps.phone.models import SyncLogSQL
from dimagi.utils.logging import notify_exception

from corehq.apps.celery import periodic_task, task
from corehq.util.metrics import metrics_gauge

log = logging.getLogger(__name__)

ASYNC_RESTORE_QUEUE = 'async_restore_queue'
ASYNC_RESTORE_SENT = "SENT"
SYNCLOG_RETENTION_DAYS = 9 * 7  # 63 days


@task(serializer='pickle', queue=ASYNC_RESTORE_QUEUE)
def get_async_restore_payload(restore_config, domain=None, username=None):
    """
    Process an async restore
    domain and username: added for displaying restore request details on flower
    """
    try:
        repr(restore_config)
        log.info('RestoreConfig after get_async_restore_payload task is created: %r', restore_config)
    except Exception as e:
        notify_exception(
            None,
            'Something went wrong with RestoreConfig.__repr__()',
            details={'error': str(e)}
        )

    response = restore_config.generate_payload(async_task=current_task)

    # delete the task id from the task, since the payload can now be fetched from the cache
    restore_config.async_restore_task_id_cache.invalidate()

    return response.name


@after_task_publish.connect
def update_celery_state(sender=None, headers=None, **kwargs):
    """Updates the celery task progress to "SENT"

    When fetching an task from celery using the form AsyncResponse(task_id), if
    task_id never exists, celery will not throw an error, it will just hang.
    This function updates each task sent to celery to have a progress value of "SENT",
    which means we can check that a task exists with the following pattern:
    `AsyncResponse(task_id).status == "SENT"`

    See
    http://stackoverflow.com/questions/9824172/find-out-whether-celery-task-exists/10089358
    for more info

    """

    task = current_app.tasks.get(sender)
    backend = task.backend if task else current_app.backend

    backend.store_result(headers['id'], None, ASYNC_RESTORE_SENT)


@periodic_task(
    run_every=crontab(hour="1", minute="0"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
)
def prune_synclogs():
    """
    Drops all partition tables containing data that's older than 63 days (9 weeks)
    """
    db = router.db_for_write(SyncLogSQL)
    oldest_date = SyncLogSQL.objects.aggregate(Min('date'))['date__min']
    while oldest_date and (datetime.today() - oldest_date).days > SYNCLOG_RETENTION_DAYS:
        year, week, _ = oldest_date.isocalendar()
        table_name = "{base_name}_y{year}w{week}".format(
            base_name=SyncLogSQL._meta.db_table,
            year=year,
            week="%02d" % week
        )
        drop_query = "DROP TABLE IF EXISTS {}".format(table_name)
        with connections[db].cursor() as cursor:
            cursor.execute(drop_query)
        oldest_date += timedelta(weeks=1)

    # find and log synclogs for which the trigger did not function properly
    with connections[db].cursor() as cursor:
        cursor.execute("select count(*) from only phone_synclogsql")
        orphaned_synclogs = cursor.fetchone()[0]
        metrics_gauge('commcare.orphaned_synclogs', orphaned_synclogs)
