import datetime
import uuid
from unittest.mock import patch

import attr
import kombu.utils.json as kombu_json
import pytest
from celery import Task
from celery import states as celery_states
from celery.exceptions import OperationalError
from django.test import TestCase

from corehq.apps.celery import task
from corehq.apps.celery.durable import UnsupportedSerializationError, delete_task_record
from corehq.apps.celery.models import TaskRecord
from corehq.util.test_utils import generate_cases


class TestDurableTaskApplyAsync(TestCase):
    """
    Despite running in eager mode, DurableTask.apply_async is still run as usual
    and this test can simulate failures to send the task to the broker.
    """

    def setUp(self):
        super().setUp()

        # setup simulated broker by mocking Task.apply_async
        apply_async_patcher = patch.object(
            Task,
            'apply_async',
            side_effect=lambda *a, **k: MockAsyncResult(
                task_id=k.get('task_id', str(uuid.uuid4())), state=celery_states.PENDING
            ),
        )
        self.mock_apply_async = apply_async_patcher.start()
        self.addCleanup(apply_async_patcher.stop)

    def test_task_is_not_tracked(self):
        result = plain_task.delay()
        with pytest.raises(TaskRecord.DoesNotExist):
            TaskRecord.objects.get(task_id=result.task_id)

    def test_explicitly_not_durable_task_is_not_tracked(self):
        @task(durable=False)
        def explicitly_not_durable_task():
            pass

        result = explicitly_not_durable_task.delay()
        with pytest.raises(TaskRecord.DoesNotExist):
            TaskRecord.objects.get(task_id=result.task_id)

    def test_task_is_tracked(self):
        result = durable_task.delay()
        TaskRecord.objects.get(task_id=result.task_id)  # should not raise

    def test_unable_to_send_task_to_broker(self):
        self.mock_apply_async.side_effect = OperationalError("failed to send to broker")
        with pytest.raises(OperationalError):
            durable_task.delay()

        (record,) = TaskRecord.objects.all()
        assert record.name == 'corehq.apps.celery.tests.test_durable_task.durable_task'
        assert record.error == 'OperationalError: failed to send to broker'

    def test_args_and_kwargs_are_serialized(self):
        test_uuid = uuid.uuid4()
        test_datetime = datetime.datetime(2025, 10, 31, 11, 5)
        test_data = {
            'id': 12345,
            'properties': {
                'field_one': 'value_one',
                'created': test_datetime,
            },
        }

        result = durable_task_with_args.delay(test_uuid, test_data=test_data)
        record = TaskRecord.objects.get(task_id=result.task_id)

        assert kombu_json.loads(record.args) == [test_uuid]
        assert kombu_json.loads(record.kwargs) == {'test_data': test_data}

    def test_existing_record_is_updated_on_retry(self):
        task_id = str(uuid.uuid4())
        TaskRecord.objects.create(
            task_id=task_id, name=durable_task_with_args.__name__, args='["abc123"]', kwargs='{}'
        )
        self.mock_apply_async.return_value = MockAsyncResult(task_id=task_id, state=celery_states.PENDING)

        retry_args = ['def456']
        retry_kwargs = {'a': 1}
        # simulate retry by calling apply_async with task_id directly
        durable_task_with_args.apply_async(task_id=task_id, args=retry_args, kwargs=retry_kwargs)

        record = TaskRecord.objects.get(task_id=task_id)
        assert kombu_json.loads(record.args) == retry_args
        assert kombu_json.loads(record.kwargs) == retry_kwargs


class TestDurableTaskAfterReturn(TestCase):

    def test_plain_task_does_not_call_delete(self):
        with patch('corehq.apps.celery.durable.delete_task_record') as mock_delete:
            plain_task.after_return(celery_states.SUCCESS, None, str(uuid.uuid4()))
            mock_delete.assert_not_called()

    @generate_cases([
        (celery_states.SUCCESS,),
        (celery_states.FAILURE,),
    ])
    def test_durable_task_record_is_deleted_when_in_complete_state(self, ready_state):
        task_id = str(uuid.uuid4())
        TaskRecord.objects.create(task_id=task_id, name='app.test_task', args={}, kwargs={})
        durable_task.after_return(ready_state, None, task_id)
        with pytest.raises(TaskRecord.DoesNotExist):
            TaskRecord.objects.get(task_id=task_id)

    @generate_cases([
        (celery_states.PENDING,),
        (celery_states.RECEIVED,),
        (celery_states.STARTED,),
        (celery_states.REJECTED,),
        (celery_states.RETRY,),
        (celery_states.REVOKED,),
    ])
    def test_durable_task_record_is_not_deleted_when_in_incomplete_state(self, unready_state):
        task_id = str(uuid.uuid4())
        TaskRecord.objects.create(task_id=task_id, name='app.test_task', args={}, kwargs={})
        with patch('corehq.apps.celery.durable.notify_error') as mock_notify:
            delete_task_record(task_id=task_id, state=unready_state)
            mock_notify.assert_called()
        TaskRecord.objects.get(task_id=task_id)  # should not raise


class TestDurableTaskMisc(TestCase):
    def test_durable_task_with_pickling_raises_exception(self):
        with pytest.raises(UnsupportedSerializationError):

            @task(durable=True, serializer='pickle')
            def durable_task_with_pickling(test_id):
                pass

    def test_celery_uses_uuid4(self):
        # durable tasks create their own uuid prior to sending to the broker
        # so want to ensure it stays in sync with celery's behavior with non-durable tasks
        result = plain_task.delay()
        task_uuid = uuid.UUID(result.task_id)
        assert task_uuid.version == 4


@task()
def plain_task():
    pass


@task(durable=True)
def durable_task():
    pass


@task(durable=True)
def durable_task_with_args(test_id, test_data=None):
    pass


@attr.s(auto_attribs=True)
class MockAsyncResult:
    task_id: str
    state: str
