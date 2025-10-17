import datetime
import json
import uuid
from unittest.mock import patch

import attr
import pytest
from celery import Task
from celery import states as celery_states
from celery.exceptions import OperationalError
from django.test import TestCase

from corehq.apps.celery import task
from corehq.apps.celery.models import TaskRecord


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


class TestDurableTask(TestCase):
    """
    Despite running in eager mode, apply_async is still run as usual and this test
    can simulate failures to send the task to the broker.
    """

    def setUp(self):
        super().setUp()

        # setup simulated broker by mocking Task.apply_async
        apply_async_patcher = patch.object(
            Task, 'apply_async', return_value=MockAsyncResult(task_id=uuid.uuid4(), state=celery_states.PENDING)
        )
        self.mock_apply_async = apply_async_patcher.start()
        self.addCleanup(apply_async_patcher.stop)

    def test_task_is_not_tracked(self):
        result = plain_task.delay()
        with pytest.raises(TaskRecord.DoesNotExist):
            TaskRecord.objects.get(task_id=result.task_id)

    def test_task_is_tracked(self):
        result = durable_task.delay()
        record = TaskRecord.objects.get(task_id=result.task_id)
        assert record.sent

    def test_unable_to_send_task_to_broker(self):
        self.mock_apply_async.side_effect = OperationalError
        with pytest.raises(OperationalError):
            durable_task.delay()

        records = TaskRecord.objects.filter(task_id__isnull=True)
        assert len(records) == 1
        assert not records[0].sent
        assert records[0].name == 'corehq.apps.celery.tests.test_durable_task.durable_task'

    def test_args_and_kwargs_are_serialized(self):
        test_id = uuid.uuid4()
        test_data = {
            'id': 12345,
            'properties': {
                'field_one': 'value_one',
                'field_two': 'value_two',
                'created': datetime.datetime(2025, 10, 31),
            },
        }

        result = durable_task_with_args.delay(test_id, test_data=test_data)
        record = TaskRecord.objects.get(task_id=result.task_id)
        deserialized_args = json.loads(record.args)
        deserialized_kwargs = json.loads(record.kwargs)
        assert deserialized_args == [str(test_id)]
        assert deserialized_kwargs == {
            'test_data': {
                'id': 12345,
                'properties': {
                    'field_one': 'value_one',
                    'field_two': 'value_two',
                    'created': '2025-10-31T00:00:00.000000Z',
                },
            }
        }

    def test_durable_flag_not_in_headers_for_regular_task(self):
        plain_task.delay()
        args, kwargs = self.mock_apply_async.call_args
        with pytest.raises(KeyError):
            # attempt to access headers -> durable
            kwargs['headers']['durable']

    def test_durable_task_includes_durable_flag_in_headers(self):
        durable_task.delay()
        args, kwargs = self.mock_apply_async.call_args
        assert kwargs['headers']['durable']
