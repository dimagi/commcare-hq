from corehq.apps.celery import task
from corehq.apps.geospatial.utils import CeleryTaskTracker, update_cases_owner


@task(queue="background_queue", ignore_result=True)
def geo_cases_reassignment_update_owners(domain, case_owner_updates_dict, task_key):
    try:
        update_cases_owner(domain, case_owner_updates_dict)
    finally:
        task_existence_helper = CeleryTaskTracker(task_key)
        task_existence_helper.mark_completed()
