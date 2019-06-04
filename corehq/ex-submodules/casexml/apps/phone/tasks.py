from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from django.db.models import Min
import logging

from celery import current_task, current_app
from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.signals import after_task_publish
from django.conf import settings
from casexml.apps.phone.cleanliness import set_cleanliness_flags_for_all_domains
from casexml.apps.phone.models import SyncLogSQL
from corehq.form_processor.backends.sql.dbaccessors import get_cursor


ASYNC_RESTORE_QUEUE = 'async_restore_queue'
ASYNC_RESTORE_SENT = "SENT"
SYNCLOG_RETENTION_DAYS = 9 * 7  # 63 days


@periodic_task(run_every=crontab(hour="2", minute="0", day_of_week="1"),
               queue='background_queue')
def update_cleanliness_flags():
    """
    Once a week go through all cleanliness flags and see if any dirty ones have become clean
    """
    set_cleanliness_flags_for_all_domains(force_full=False)


@periodic_task(run_every=crontab(hour="4", minute="0", day_of_month="5"),
               queue='background_queue')
def force_update_cleanliness_flags():
    """
    Once a month, go through all cleanliness flags without using hints
    """
    # the only reason this task is run is to use the soft_assert to validate
    # that there are no bugs in the weekly task.
    # If we haven't seen any issues by the end of 2015 (so 6 runs) we should remove this.
    set_cleanliness_flags_for_all_domains(force_full=True)


@task(serializer='pickle', queue=ASYNC_RESTORE_QUEUE)
def get_async_restore_payload(restore_config, domain=None, username=None):
    """
    Process an async restore
    domain and username: added for displaying restore request details on flower
    """
    logging.info('RestoreConfig in get_async_restore_payload task: {msg}'.format(
        msg=repr(restore_config)
    ))

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
    Drops all partition tables containing data that's older than 63 days (7 weeks)
    """
    oldest_synclog = SyncLogSQL.objects.aggregate(Min('date'))['date__min']
    while oldest_synclog and (datetime.today() - oldest_synclog).days > SYNCLOG_RETENTION_DAYS:
        year, week, _ = oldest_synclog.isocalendar()
        table_name = "{base_name}_y{year}w{week}".format(
            base_name=SyncLogSQL._meta.db_table,
            year=year,
            week="%02d" % week
        )
        drop_query = "DROP TABLE IF EXISTS {}".format(table_name)
        get_cursor(SyncLogSQL).execute(drop_query)
        oldest_synclog = SyncLogSQL.objects.aggregate(Min('date'))['date__min']
