import random
from functools import wraps

from corehq.apps.celery.locking import (
    CouldNotAcquireLockError,
    get_unique_key,
    run_with_lock,
)
from corehq.apps.celery.shared_task import task


def concurrent_task(
    unique_key,
    concurrency,
    default_retry_delay=30,
    timeout=5 * 60,
    max_retries=3,
    queue='background_queue',
    ignore_result=True,
    serializer=None,
    durable=False,
):
    """
    Define a task that allows up to ``concurrency`` simultaneous runs per
    resolved key. If all slots are taken, the task retries after a delay.

    Slots are implemented as ``concurrency`` named Redis locks per key:
    ``{key}:0``, ``{key}:1``, ..., ``{key}:concurrency-1``. Each slot lock
    inherits the same TTL-based crash safety as :func:`serial_task` -- a
    worker killed before releasing its slot will have that slot auto-expire
    after ``timeout``.

    :param unique_key: Format string used to derive the per-call key. May
        reference any of the wrapped function's arguments. See
        :func:`serial_task` for the format string conventions.
    :param concurrency: Maximum number of simultaneous runs allowed per
        resolved key. Must be >= 1.
    :param default_retry_delay: Seconds to wait before retrying when no slot
        is available.
    :param timeout: Lock TTL in seconds. Must exceed the maximum expected
        task duration so a still-running task does not have its slot
        auto-released.

    Usage::

        @concurrent_task("{domain}", concurrency=5, default_retry_delay=10)
        def rebuild_thing(domain, case_id):
            ...
    """
    if concurrency < 1:
        raise ValueError('concurrency must be >= 1')

    task_kwargs = {}
    if serializer:
        task_kwargs['serializer'] = serializer

    def decorator(fn):
        @task(
            bind=True,
            queue=queue,
            ignore_result=ignore_result,
            default_retry_delay=default_retry_delay,
            max_retries=max_retries,
            durable=durable,
            **task_kwargs,
        )
        @wraps(fn)
        def _inner(self, *args, **kwargs):
            key = get_unique_key(unique_key, fn, *args, **kwargs)
            # Randomize starting slot to avoid contention
            start = random.randrange(concurrency)
            for i in range(concurrency):
                slot_index = (start + i) % concurrency
                slot_key = f'{key}:{slot_index}'
                try:
                    return run_with_lock(
                        slot_key, fn, timeout, *args, **kwargs
                    )
                except CouldNotAcquireLockError:
                    if i == concurrency - 1:
                        msg = (
                            "Could not acquire any of {} slots for key '{}' (task '{}')."
                        ).format(concurrency, key, fn.__name__)
                        self.retry(exc=CouldNotAcquireLockError(msg))

        return _inner

    return decorator
