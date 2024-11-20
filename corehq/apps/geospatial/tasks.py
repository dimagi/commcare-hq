from corehq.apps.celery import task
from corehq.apps.geospatial.utils import (
    CeleryTaskTracker,
    get_flag_assigned_cases_config,
    update_cases_owner,
)


@task(queue="background_queue", ignore_result=True)
def geo_cases_reassignment_update_owners(domain, case_owner_updates_dict, task_key):
    try:
        flag_assigned_cases = get_flag_assigned_cases_config(domain)
        update_cases_owner(domain, case_owner_updates_dict, flag_assigned_cases)
    finally:
        celery_task_tracker = CeleryTaskTracker(task_key)
        celery_task_tracker.mark_completed()
