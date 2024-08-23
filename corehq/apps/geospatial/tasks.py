from corehq.apps.celery import task
from corehq.apps.geospatial.utils import update_cases_owner
from celery.result import AsyncResult
from celery import states


@task(queue="background_queue", ignore_result=False)
def geo_cases_reassignment_update_owners(domain, case_id_to_owner_id):
    from time import sleep
    sleep(30)
    update_cases_owner(domain, case_id_to_owner_id)


def is_task_active(task_id):
    """Returns True is a task is invoked and is executing or waiting to be executed.
    NOTE: Only works for tasks that store results i.e ignore_result must be False
    """
    result = AsyncResult(task_id)
    # states.PENDING here means the given task was never invoked.
    # Once invoked, we mark the status as sent in casexml.apps.phone.tasks.update_celery_state
    return result.status not in [states.PENDING, states.SUCCESS, states.FAILURE, states.REVOKED]
