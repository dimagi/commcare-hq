from celery import states
from celery.result import AsyncResult

from corehq.apps.celery import task
from corehq.apps.geospatial.utils import update_cases_owner


@task(queue="background_queue", ignore_result=False)
def geo_cases_reassignment_update_owners(domain, case_id_to_owner_id):
    update_cases_owner(domain, case_id_to_owner_id)


def is_task_invoked_and_not_completed(task_id):
    """Returns True if a task is invoked and is executing or waiting to be executed.
    NOTE: Only works for tasks that store results i.e. ignore_result must be False.
    NOTE: Celery states.PENDING is a bit ambiguous as it could mean two things one, task was never invoked and two
    task was invoked but still waiting to picked up.
    However, in HQ we set state to `SENT` as soon as it is invoked.
    See 'casexml.apps.phone.tasks.update_celery_state'
    """
    result = AsyncResult(task_id)
    return result.state not in [states.PENDING, states.SUCCESS, states.FAILURE, states.REVOKED]
