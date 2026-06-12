import inspect


class CouldNotAcquireLockError(Exception):
    """Raised when a serial_task or concurrent_task can't acquire its lock."""


def get_unique_key(format_str, fn, *args, **kwargs):
    """
    Builds a unique key from the function name and ``format_str``.

    Binds args and kwargs to the function's signature which enables
    referencing any arg or kwarg by name in ``format_str``

    See corehq.apps.celery.tests.test_get_unique_key for more details.
    """
    bound = inspect.signature(fn).bind(*args, **kwargs)
    bound.apply_defaults()  # ensures bound.arguments includes default values
    return f'{fn.__name__}-{format_str.format(**bound.arguments)}'


def run_with_lock(key, fn, timeout, *args, **kwargs):
    from dimagi.utils.couch import get_redis_lock, release_lock

    lock = get_redis_lock(key, timeout=timeout, name=fn.__name__)
    if lock.acquire(blocking=False):
        try:
            return fn(*args, **kwargs)
        finally:
            release_lock(lock, True)
    else:
        msg = f"Could not acquire lock '{key}' for task '{fn.__name__}'"
        raise CouldNotAcquireLockError(msg)


def legacy_lock_still_held(concurrency, key):
    """Detect locks written before the slot-suffix format.

    Can be removed 36 hours after the new format is deployed
    """
    if concurrency != 1:
        return False

    from dimagi.utils.couch import get_redis_client

    return bool(get_redis_client().client.get_client().exists(key))
