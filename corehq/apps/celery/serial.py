import inspect
from functools import wraps

from django.conf import settings

from corehq.apps.celery.shared_task import task


def serial_task(
    unique_key,
    default_retry_delay=30,
    timeout=5 * 60,
    max_retries=3,
    queue='background_queue',
    ignore_result=True,
    serializer=None,
):
    """
    Define a task to be executed one at a time.  If another serial_task with
    the same unique_key is currently in process, this will retry after a delay.

    :param unique_key: string used to lock the task.  There will be one lock
        per unique value.  You may use any arguments that will be passed to the
        function.  See example.
    :param default_retry_delay: seconds to wait before retrying if a lock is
        encountered
    :param timeout: timeout on the lock (in seconds).  Normally the lock should
        be released when the task completes, but you should also define a
        timeout in case something goes wrong.  This must be greater than the
        maximum length of the task.

    Usage:
        @serial_task("{user.username}-{from}", default_retry_delay=2)
        def greet(user, from="Dimagi"):
            ...

        greet.delay(joeshmoe)
        # Locking key used would be "greet-joeshmoe@test.commcarehq.org-Dimagi"
    """

    task_kwargs = {}
    if serializer:
        task_kwargs['serializer'] = serializer

    def decorator(fn):
        # register task with celery.  Note that this still happens on import
        from dimagi.utils.couch import get_redis_lock, release_lock

        @task(
            bind=True,
            queue=queue,
            ignore_result=ignore_result,
            default_retry_delay=default_retry_delay,
            max_retries=max_retries,
            **task_kwargs,
        )
        @wraps(fn)
        def _inner(self, *args, **kwargs):
            if settings.UNIT_TESTING:  # Don't depend on redis
                return fn(*args, **kwargs)

            key = _get_unique_key(unique_key, fn, *args, **kwargs)
            lock = get_redis_lock(key, timeout=timeout, name=fn.__name__)
            if lock.acquire(blocking=False):
                try:
                    return fn(*args, **kwargs)
                finally:
                    release_lock(lock, True)
            else:
                msg = "Could not acquire lock '{}' for task '{}'.".format(
                    key, fn.__name__
                )
                self.retry(exc=CouldNotAcquireLockError(msg))

        return _inner

    return decorator


# Sorry this is so magic
def _get_unique_key(format_str, fn, *args, **kwargs):
    """
    Lines args and kwargs up with those specified in the definition of fn and
    passes the result to `format_str.format()`.
    """
    callargs = inspect.getcallargs(fn, *args, **kwargs)
    return ("{}-" + format_str).format(fn.__name__, **callargs)


class CouldNotAcquireLockError(Exception):
    """Used when a serial_task is unable to obtain lock to run"""
