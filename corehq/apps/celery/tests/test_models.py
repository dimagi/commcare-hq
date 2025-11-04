from celery.states import ALL_STATES

from corehq.apps.celery.models import TaskRecordState


def test_task_record_states():
    task_record_states = set(TaskRecordState.values)
    diff = task_record_states - ALL_STATES
    # only expect the following states to be different
    # REJECTED - celery doesn't include this in ALL_STATES, but sets it when unable to process a message
    # SENT - we add this in commcare code
    assert diff == {TaskRecordState.REJECTED, TaskRecordState.SENT}
