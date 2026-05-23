from unittest.mock import patch

from dimagi.utils.couch import get_redis_lock, release_lock

from corehq.apps.celery.serial import CouldNotAcquireLockError, serial_task
from corehq.apps.celery.tests.utils import run_with_lock_patch
from corehq.tests.pytest_plugins.patches import suspend


def test_celery_specific_kwargs_bind_to_task():
    @serial_task('test', max_retries=5, default_retry_delay=50, queue='custom')
    def task_no_arg():
        pass

    assert task_no_arg.max_retries == 5
    assert task_no_arg.default_retry_delay == 50
    assert task_no_arg.queue == 'custom'


@suspend(run_with_lock_patch)
def test_runs_and_releases_lock():
    task_calls = []

    @serial_task('{arg}')
    def task_with_arg(arg):
        task_calls.append(arg)

    task_with_arg.apply(args=['test'])

    assert task_calls == ['test']
    lock = get_redis_lock(
        'task_with_arg-test', timeout=5, name='task_with_arg'
    )
    assert lock.acquire(blocking=False)
    release_lock(lock, True)


@suspend(run_with_lock_patch)
def test_fails_and_releases_lock():
    @serial_task('test')
    def raising_task():
        raise ValueError('error')

    result = raising_task.apply()
    assert result.failed()

    lock = get_redis_lock('raising_task-test', timeout=5, name='raising_task')
    assert lock.acquire(blocking=False)
    release_lock(lock, True)


@suspend(run_with_lock_patch)
def test_fails_to_acquire_lock():
    task_calls = []

    @serial_task('{arg}')
    def task_with_arg(arg):
        task_calls.append(arg)

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
        assert task_calls == []
    finally:
        release_lock(lock, True)
