from celery.states import ALL_STATES

from corehq.apps.celery.models import TaskRecordState


def test_task_record_states():
    # only expect the SENT state to be different, since we add that ourselves
    task_record_states = set(TaskRecordState.values)
    diff = task_record_states - ALL_STATES
    assert diff == {TaskRecordState.SENT}
