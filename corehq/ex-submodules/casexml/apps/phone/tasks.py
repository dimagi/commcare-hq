from celery import current_task
from celery.schedules import crontab
from celery.task import periodic_task, task
from casexml.apps.phone.cleanliness import set_cleanliness_flags_for_all_domains


ASYNC_RESTORE_QUEUE = 'async_restore_queue'


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
    response = restore_config.generate_payload()

    # delete the task id from the task, since the cached_payload can be fetched from the cache
    # TODO: figure out how to do this properly
    # restore_config.cache.delete(restore_config._async_cache_key)

    return response
