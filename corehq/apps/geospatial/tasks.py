from corehq.apps.celery import task
from corehq.apps.geospatial.utils import update_cases_owner, CeleryTaskExistenceHelper


@task(queue="background_queue", ignore_result=False)
def geo_cases_reassignment_update_owners(domain, case_id_to_owner_id, task_key):
    try:
        update_cases_owner(domain, case_id_to_owner_id)
    finally:
        task_existence_helper = CeleryTaskExistenceHelper(task_key)
        task_existence_helper.mark_inactive()
