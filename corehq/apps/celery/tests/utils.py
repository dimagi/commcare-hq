from unittest.mock import patch

from django.conf import settings


def _bypass_run_with_lock(key, fn, timeout, *args, **kwargs):
    return fn(*args, **kwargs)


run_with_lock_patch = patch(
    'corehq.apps.celery.locking.run_with_lock', _bypass_run_with_lock
)


def patch_serial_task():
    """Setup @serial_task for tests

    - Do not acquire and release locks in tests
    """
    # Use __enter__ and __exit__ to start/stop so patch.stopall() does not stop it.
    assert settings.UNIT_TESTING
    run_with_lock_patch.__enter__()
