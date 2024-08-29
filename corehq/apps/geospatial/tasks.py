from celery import states
from celery.result import AsyncResult

from corehq.apps.celery import task
from corehq.apps.geospatial.utils import update_cases_owner


@task(queue="background_queue", ignore_result=False)
def geo_cases_reassignment_update_owners(domain, case_id_to_owner_id):
    update_cases_owner(domain, case_id_to_owner_id)


def is_task_invoked_and_not_completed(task_id):
    """
    NOTE: Only works for tasks that store results i.e. ignore_result must be False.
    Returns True if a task is invoked and is executing or waiting to be executed.
    NOTE: In case the task with a given task_id is not invoked (i.e. does not exist in results backend), the state
    returned is PENDING.
    The state is also PENDING if the task was invoked and still waiting to be picked up. However, in HQ we set the
    state to `SENT` as soon as it is invoked. See 'casexml.apps.phone.tasks.update_celery_state'.
    Read more about Celery State at https://docs.celeryq.dev/en/stable/reference/celery.states.html
    """
    result = AsyncResult(task_id)
    return result.state not in [states.PENDING, states.SUCCESS, states.FAILURE, states.REVOKED]
