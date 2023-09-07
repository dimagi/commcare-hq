from contextlib import contextmanager
from unittest.mock import patch

from django.conf import settings

_sync_user_to_es_patch = patch('corehq.apps.users.signals._update_user_in_es')


def patch_es_user_signals():
    # Use __enter__ and __exit__ to start/stop so patch.stopall() does not stop it.
    assert settings.UNIT_TESTING
    _sync_user_to_es_patch.__enter__()


@contextmanager
def sync_users_to_es():
    """Contextmanager/decorator to enable sync users to ES

    Usage as decorator:

        @sync_users_to_es()
        def test_something():
            ...  # do thing with users in ES

    Usage as context manager:

        with sync_users_to_es():
            ...  # do thing with users in ES
    """
    assert settings.UNIT_TESTING
    _sync_user_to_es_patch.__exit__(None, None, None)
    try:
        yield
    finally:
        _sync_user_to_es_patch.__enter__()
