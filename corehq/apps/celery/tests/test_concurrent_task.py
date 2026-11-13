import pytest
from unittest.mock import patch
from unmagic import fixture, use

from dimagi.utils.couch import get_redis_lock, release_lock

from corehq.apps.celery.locking import CouldNotAcquireLockError
from corehq.apps.celery.concurrent import concurrent_task
from corehq.apps.celery.tests.utils import run_with_lock_patch
from corehq.tests.pytest_plugins.patches import suspend

_task_calls = []


@concurrent_task('test', 2)
def task_with_concurrency(arg):
    _task_calls.append(arg)


@fixture
def task_calls():
    yield _task_calls
    _task_calls.clear()


def test_celery_specific_kwargs_bind_to_task():
    @concurrent_task(
        'test', 2, max_retries=5, default_retry_delay=50, queue='custom'
    )
    def task_no_arg():
        pass

    assert task_no_arg.max_retries == 5
    assert task_no_arg.default_retry_delay == 50
    assert task_no_arg.queue == 'custom'


def test_concurrency_minimum():
    with pytest.raises(ValueError):

        @concurrent_task('test', 0)
        def too_little_concurrency():
            pass


@use(task_calls)
@suspend(run_with_lock_patch)
def test_runs_and_releases_lock():
    task_with_concurrency.apply(args=['test'])
    assert _task_calls == ['test']
    # check both slots since initial call could select either
    for i in range(2):
        lock = get_redis_lock(
            f'task_with_concurrency-test:{i}',
            timeout=5,
            name='task_with_concurrency',
        )
        assert lock.acquire(blocking=False)
        release_lock(lock, True)


@suspend(run_with_lock_patch)
def test_fails_and_releases_lock():
    @concurrent_task('test', 2)
    def raising_task():
        raise ValueError('error')

    result = raising_task.apply()
    assert result.failed()

    # check both slots since initial call could select either
    for i in range(2):
        lock = get_redis_lock(
            f'raising_task-test:{i}', timeout=5, name='raising_task'
        )
        assert lock.acquire(blocking=False)
        release_lock(lock, True)


@use(task_calls)
@suspend(run_with_lock_patch)
def test_acquires_lock_if_slot_available():
    lock = get_redis_lock(
        'task_with_concurrency-test:0', timeout=5, name='task_with_concurrency'
    )
    assert lock.acquire(blocking=False)

    try:
        with patch(
            'dimagi.utils.couch.get_redis_lock', wraps=get_redis_lock
        ) as mock_get_lock:
            task_with_concurrency.apply(args=['test'])
            keys_requested = [
                call.args[0] for call in mock_get_lock.call_args_list
            ]
            assert 'task_with_concurrency-test:1' in keys_requested
    finally:
        release_lock(lock, True)


@use(task_calls)
@suspend(run_with_lock_patch)
def test_fails_to_acquire_lock():
    lock1 = get_redis_lock(
        'task_with_concurrency-test:0', timeout=5, name='task_with_concurrency'
    )
    assert lock1.acquire(blocking=False)

    lock2 = get_redis_lock(
        'task_with_concurrency-test:1', timeout=5, name='task_with_concurrency'
    )
    assert lock2.acquire(blocking=False)

    try:
        with patch.object(task_with_concurrency, 'retry') as retry:
            task_with_concurrency.apply(args=['test'])
        assert retry.called
        exc = retry.call_args.kwargs['exc']
        assert isinstance(exc, CouldNotAcquireLockError)
        assert _task_calls == []
    finally:
        release_lock(lock1, True)
        release_lock(lock2, True)
