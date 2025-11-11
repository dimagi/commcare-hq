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
from corehq.apps.celery.durable import UnsupportedSerializationError, update_task_record
from corehq.apps.celery.models import TaskRecord
from corehq.util.test_utils import generate_cases


class TestDurableTask(TestCase):
    """
    Despite running in eager mode, apply_async is still run as usual and this test
    can simulate failures to send the task to the broker.
    """

    def setUp(self):
        super().setUp()

        # setup simulated broker by mocking Task.apply_async
        apply_async_patcher = patch.object(
            Task,
            'apply_async',
            return_value=MockAsyncResult(task_id=str(uuid.uuid4()), state=celery_states.PENDING),
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

        (record,) = TaskRecord.objects.filter(task_id__isnull=True)
        assert not record.sent
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

        deserialized_args = kombu_json.loads(record.args)
        assert deserialized_args == [test_uuid]
        deserialized_kwargs = kombu_json.loads(record.kwargs)
        assert deserialized_kwargs == {'test_data': test_data}

    def test_empty_headers_for_regular_task(self):
        plain_task.delay()
        args, kwargs = self.mock_apply_async.call_args
        assert 'headers' not in kwargs

    def test_durable_task_includes_durable_flag_in_headers(self):
        durable_task.delay()
        args, kwargs = self.mock_apply_async.call_args
        assert kwargs['headers']['durable']

    def test_durable_task_with_pickling_raises_exception(self):
        with pytest.raises(UnsupportedSerializationError):

            @task(durable=True, serializer='pickle')
            def durable_task_with_pickling(test_id):
                pass

    def test_existing_record_is_updated_on_retry(self):
        task_id = str(uuid.uuid4())
        TaskRecord.objects.create(
            task_id=task_id, name=durable_task_with_args.__name__, args='["abc123"]', kwargs='{}', sent=True
        )
        self.mock_apply_async.return_value = MockAsyncResult(task_id=task_id, state=celery_states.PENDING)

        # calls apply_async directly to pass in the task_id kwarg, which isn't possible via .delay()
        retry_args = ['def456']
        retry_kwargs = {'a': 1}
        durable_task_with_args.apply_async(task_id=task_id, args=retry_args, kwargs=retry_kwargs)

        record = TaskRecord.objects.get(task_id=task_id)
        assert kombu_json.loads(record.args) == retry_args
        assert kombu_json.loads(record.kwargs) == retry_kwargs

    def test_retry_wins_in_race_condition(self):
        task_id = str(uuid.uuid4())
        retry_args = ['def456']
        retry_kwargs = {'a': 1}

        def race_apply_async(*args, **kwargs):
            # simulate celery worker creating a TaskRecord before the original apply_async does
            TaskRecord.objects.create(
                task_id=task_id,
                name=durable_task_with_args.__name__,
                args=kombu_json.dumps(retry_args),
                kwargs=kombu_json.dumps(retry_kwargs),
                sent=True,
            )
            return MockAsyncResult(task_id=task_id, state=celery_states.PENDING)

        self.mock_apply_async.side_effect = race_apply_async

        durable_task_with_args.delay("abc123", test_data={"old": "old arg"})

        record = TaskRecord.objects.get(task_id=task_id)
        assert kombu_json.loads(record.args) == retry_args
        assert kombu_json.loads(record.kwargs) == retry_kwargs


class TestUpdateTaskRecord(TestCase):
    def test_empty_task_does_not_raise_error(self):
        update_task_record(task={}, state=celery_states.SUCCESS)  # should not raise

    def test_task_without_durable_flag(self):
        task = MockTask(request=MockRequest(id=uuid.uuid4(), headers={}))
        update_task_record(task=task, state=celery_states.SUCCESS)  # should not raise

    @generate_cases([
        (celery_states.SUCCESS,),
        (celery_states.FAILURE,),
        (celery_states.REVOKED,),
    ])
    def test_durable_task_record_is_deleted_when_in_ready_state(self, ready_state):
        # ready_states as defined by celery (v5.4.0)
        task_id = uuid.uuid4()
        TaskRecord.objects.create(task_id=task_id, name='app.test_task', sent=True, args={}, kwargs={})
        task = MockTask(request=MockRequest(id=task_id, headers={'durable': True}))
        update_task_record(task=task, state=ready_state)
        with pytest.raises(TaskRecord.DoesNotExist):
            TaskRecord.objects.get(task_id=task_id)

    @generate_cases([
        (celery_states.PENDING,),
        (celery_states.RECEIVED,),
        (celery_states.STARTED,),
        (celery_states.REJECTED,),
        (celery_states.RETRY,),
    ])
    def test_durable_task_record_is_not_deleted_when_in_unready_state(self, unready_state):
        # unready_states as defined by celery (v5.4.0)
        task_id = uuid.uuid4()
        TaskRecord.objects.create(task_id=task_id, name='app.test_task', sent=True, args={}, kwargs={})
        task = MockTask(request=MockRequest(id=task_id, headers={'durable': True}))
        update_task_record(task=task, state=unready_state)
        TaskRecord.objects.get(task_id=task_id)  # should not raise


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


@attr.s(auto_attribs=True)
class MockRequest:
    id: str
    headers: dict


@attr.s(auto_attribs=True)
class MockTask:
    request: MockRequest
