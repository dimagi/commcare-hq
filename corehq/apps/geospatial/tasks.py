from celery import states
from celery.result import AsyncResult

from corehq.apps.celery import task
from corehq.apps.geospatial.utils import CeleryTaskTracker, update_cases_owner


@task(queue="background_queue", ignore_result=True)
def geo_cases_reassignment_update_owners(domain, case_owner_updates_dict, task_key):
    try:
        update_cases_owner(domain, case_owner_updates_dict)
    finally:
        celery_task_tracker = CeleryTaskTracker(task_key)
        celery_task_tracker.mark_completed()
