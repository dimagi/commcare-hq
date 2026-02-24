import datetime
from io import StringIO
from unittest.mock import MagicMock, patch

import kombu.utils.json as kombu_json
import pytest
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone
from time_machine import travel

from corehq.apps.celery.models import TaskRecord

TASK_NAME = 'myapp.tasks.my_task'
OTHER_TASK_NAME = 'myapp.tasks.other_task'

PATCH_CURRENT_APP = patch(
    'corehq.apps.celery.management.commands.requeue_task_records.current_app'
)


class TestRequeueTaskRecords(TestCase):

    def setUp(self):
        super().setUp()
        self.mock_task = MagicMock()
        self.mock_app = PATCH_CURRENT_APP.start()
        self.mock_app.tasks = {TASK_NAME: self.mock_task}
        self.addCleanup(PATCH_CURRENT_APP.stop)

    def _requeue_task_records(self, **kwargs):
        out, err = StringIO(), StringIO()
        call_command('requeue_task_records', stdout=out, stderr=err, **kwargs)
        return out.getvalue(), err.getvalue()

    # --- argument validation ---

    def test_no_filter_raises_error(self):
        with pytest.raises(CommandError):
            self._requeue_task_records()

    def test_invalid_start_raises_error(self):
        with pytest.raises(CommandError):
            self._requeue_task_records(requeue_all=True, start='not-a-date')

    def test_invalid_end_raises_error(self):
        with pytest.raises(CommandError):
            self._requeue_task_records(requeue_all=True, end='not-a-date')

    # --- dry run ---

    def test_dry_run_does_not_requeue(self):
        make_record()
        self._requeue_task_records(requeue_all=True)
        self.mock_task.apply_async.assert_not_called()

    # --- requeue behaviour ---

    def test_no_matching_records(self):
        out, _ = self._requeue_task_records(requeue_all=True, commit=True)
        assert 'No matching' in out
        self.mock_task.apply_async.assert_not_called()

    def test_requeue_all(self):
        make_record()
        make_record()
        self._requeue_task_records(requeue_all=True, commit=True)
        assert self.mock_task.apply_async.call_count == 2

    def test_task_id_is_preserved_on_requeue(self):
        record = make_record()
        self._requeue_task_records(requeue_all=True, commit=True)
        self.mock_task.apply_async.assert_called_once_with(
            args=[], kwargs={}, task_id=str(record.task_id)
        )

    def test_args_and_kwargs_are_deserialized(self):
        args = [1, 'hello']
        kwargs = {'key': 'value'}
        record = make_record(args=args, kwargs=kwargs)
        self._requeue_task_records(requeue_all=True, commit=True)
        self.mock_task.apply_async.assert_called_once_with(
            args=args, kwargs=kwargs, task_id=str(record.task_id)
        )

    # --- filtering ---

    def test_filter_by_task_name(self):
        record = make_record(name=TASK_NAME)
        other_mock = MagicMock()
        self.mock_app.tasks[OTHER_TASK_NAME] = other_mock
        make_record(name=OTHER_TASK_NAME)

        self._requeue_task_records(task_name=TASK_NAME, commit=True)

        self.mock_task.apply_async.assert_called_once_with(
            args=[], kwargs={}, task_id=str(record.task_id)
        )
        other_mock.apply_async.assert_not_called()

    def test_filter_by_start(self):
        old = timezone.now() - datetime.timedelta(days=2)
        recent = timezone.now() - datetime.timedelta(hours=1)
        with travel(old, tick=False):
            make_record()
        with travel(recent, tick=False):
            recent_record = make_record()

        cutoff = (timezone.now() - datetime.timedelta(days=1)).isoformat()
        self._requeue_task_records(requeue_all=True, start=cutoff, commit=True)

        self.mock_task.apply_async.assert_called_once_with(
            args=[], kwargs={}, task_id=str(recent_record.task_id)
        )

    def test_filter_by_end(self):
        old = timezone.now() - datetime.timedelta(days=2)
        recent = timezone.now() - datetime.timedelta(hours=1)
        with travel(old, tick=False):
            old_record = make_record()
        with travel(recent, tick=False):
            make_record()
        make_record(date_created=recent)

        cutoff = (timezone.now() - datetime.timedelta(days=1)).isoformat()
        self._requeue_task_records(requeue_all=True, end=cutoff, commit=True)

        self.mock_task.apply_async.assert_called_once_with(
            args=[], kwargs={}, task_id=str(old_record.task_id)
        )

    # --- error handling ---

    def test_unregistered_task_is_skipped(self):
        make_record(name='unregistered.task')
        self.mock_app.tasks = {}
        _, err = self._requeue_task_records(requeue_all=True, commit=True)
        self.mock_task.apply_async.assert_not_called()
        assert 'not registered' in err

    def test_requeue_error_is_reported(self):
        make_record()
        self.mock_task.apply_async.side_effect = Exception("broker down")
        _, err = self._requeue_task_records(requeue_all=True, commit=True)
        assert 'broker down' in err


def make_record(name=TASK_NAME, args=None, kwargs=None, date_created=None):
    record = TaskRecord.objects.create(
        name=name,
        args=kombu_json.dumps(args or []),
        kwargs=kombu_json.dumps(kwargs or {}),
    )
    return record
