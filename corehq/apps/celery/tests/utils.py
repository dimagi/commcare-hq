from unittest.mock import patch

from django.conf import settings


def _bypass_run_with_lock(key, fn, timeout, *args, **kwargs):
    return fn(*args, **kwargs)


run_with_lock_patch = patch(
    'corehq.apps.celery.locking.run_with_lock', _bypass_run_with_lock
)

# Suppress legacy_lock_still_held by default; tests that exercise the
# legacy-key path should @suspend(legacy_lock_check_patch). Remove this
# alongside legacy_lock_still_held.
legacy_lock_check_patch = patch(
    'corehq.apps.celery.concurrent.legacy_lock_still_held',
    return_value=False,
)


def patch_serial_task():
    """Setup @serial_task for tests

    - Do not acquire and release locks in tests
    - Skip the legacy-key check unless a test opts in
    """
    # Use __enter__ and __exit__ to start/stop so patch.stopall() does not stop it.
    assert settings.UNIT_TESTING
    run_with_lock_patch.__enter__()
    legacy_lock_check_patch.__enter__()
