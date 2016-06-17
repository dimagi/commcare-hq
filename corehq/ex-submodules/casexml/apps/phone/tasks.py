from celery import current_task
from celery.schedules import crontab
from celery.task import periodic_task, task, Task
from casexml.apps.phone.cleanliness import set_cleanliness_flags_for_all_domains


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


@task(queue='async_restore_queue')
def get_async_restore_payload(restore_config):
    """Process an async restore
    """
    current_task.update_state(state="PROGRESS", meta={'done': 50, 'total': 100})
    response = restore_config._get_synchronous_payload()

    return response
    # task should call a subclass of the restore, which also takes a download
    # object and can update status
