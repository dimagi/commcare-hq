from unittest.mock import patch
from unmagic import fixture, use

from dimagi.utils.couch import get_redis_lock, release_lock

from corehq.apps.celery.locking import CouldNotAcquireLockError
from corehq.apps.celery.serial import serial_task
from corehq.apps.celery.tests.utils import (
    legacy_lock_check_patch,
    run_with_lock_patch,
)
from corehq.tests.pytest_plugins.patches import suspend

_task_calls = []


@serial_task('{arg}')
def task_with_arg(arg):
    _task_calls.append(arg)


@fixture
def task_calls():
    yield _task_calls
    _task_calls.clear()


def test_celery_specific_kwargs_bind_to_task():
    @serial_task('test', max_retries=5, default_retry_delay=50, queue='custom')
    def task_no_arg():
        pass

    assert task_no_arg.max_retries == 5
    assert task_no_arg.default_retry_delay == 50
    assert task_no_arg.queue == 'custom'


@use(task_calls)
@suspend(run_with_lock_patch)
def test_runs_and_releases_lock():
    with patch(
        'dimagi.utils.couch.get_redis_lock', wraps=get_redis_lock
    ) as mock_get_lock:
        task_with_arg.apply(args=['test'])
        keys_requested = [
            call.args[0] for call in mock_get_lock.call_args_list
        ]
        assert keys_requested == ['task_with_arg-test:0']

    assert _task_calls == ['test']
    lock = get_redis_lock(
        'task_with_arg-test:0', timeout=5, name='task_with_arg'
    )
    assert lock.acquire(blocking=False)
    release_lock(lock, True)


@suspend(run_with_lock_patch)
def test_fails_and_releases_lock():
    @serial_task('test')
    def raising_task():
        raise ValueError('error')

    with patch(
        'dimagi.utils.couch.get_redis_lock', wraps=get_redis_lock
    ) as mock_get_lock:
        result = raising_task.apply()
        assert result.failed()
        keys_requested = [
            call.args[0] for call in mock_get_lock.call_args_list
        ]
        assert keys_requested == ['raising_task-test:0']

    lock = get_redis_lock(
        'raising_task-test:0', timeout=5, name='raising_task'
    )
    assert lock.acquire(blocking=False)
    release_lock(lock, True)


@use(task_calls)
@suspend(run_with_lock_patch)
def test_fails_to_acquire_lock():
    lock = get_redis_lock(
        'task_with_arg-test:0', timeout=5, name='task_with_arg'
    )
    assert lock.acquire(blocking=False)

    try:
        with patch.object(task_with_arg, 'retry') as retry:
            task_with_arg.apply(args=['test'])
        assert retry.called
        exc = retry.call_args.kwargs['exc']
        assert isinstance(exc, CouldNotAcquireLockError)
        assert _task_calls == []
    finally:
        release_lock(lock, True)


# ---- Remove this test once old format is no longer supported ----
@use(task_calls)
@suspend(run_with_lock_patch)
@suspend(legacy_lock_check_patch)
def test_lock_with_old_format_is_respected():
    # legacy format does not append ":0" to the key
    lock = get_redis_lock(
        'task_with_arg-test', timeout=5, name='task_with_arg'
    )
    assert lock.acquire(blocking=False)

    try:
        with patch.object(task_with_arg, 'retry') as retry:
            task_with_arg.apply(args=['test'])
        assert retry.called
        exc = retry.call_args.kwargs['exc']
        assert isinstance(exc, CouldNotAcquireLockError)
        assert _task_calls == []
    finally:
        release_lock(lock, True)
