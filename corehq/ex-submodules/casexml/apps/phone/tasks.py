from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import date, timedelta
from celery import current_task, current_app
from celery.schedules import crontab
from celery.task import periodic_task, task
from celery.signals import after_task_publish
from django.conf import settings
from casexml.apps.phone.cleanliness import set_cleanliness_flags_for_all_domains
from casexml.apps.phone.utils import delete_sync_logs


ASYNC_RESTORE_QUEUE = 'async_restore_queue'
ASYNC_RESTORE_SENT = "SENT"


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


@task(queue=ASYNC_RESTORE_QUEUE)
def get_async_restore_payload(restore_config):
    """Process an async restore
    """
    response = restore_config.generate_payload(async_task=current_task)

    # delete the task id from the task, since the payload can now be fetched from the cache
    restore_config.async_restore_task_id_cache.invalidate()

    return response


@after_task_publish.connect
def update_celery_state(sender=None, body=None, **kwargs):
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

    backend.store_result(body['id'], None, ASYNC_RESTORE_SENT)


@periodic_task(
    run_every=crontab(hour="1", minute="0"),
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
)
def prune_synclogs():
    prune_date = date.today() - timedelta(days=30)
    num_deleted = delete_sync_logs(prune_date)
    while num_deleted != 0:
        num_deleted = delete_sync_logs(prune_date)
