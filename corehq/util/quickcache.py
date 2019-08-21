from __future__ import absolute_import, unicode_literals

import os
from base64 import b64encode

from celery._state import get_current_task
from quickcache import ForceSkipCache
from quickcache.django_quickcache import get_django_quickcache

from corehq.util.global_request import get_request
from corehq.util.soft_assert import soft_assert

quickcache_soft_assert = soft_assert(
    notify_admins=True,
    fail_if_debug=False,
    skip_frames=5,
)


def get_session_key():
    """
    returns a 7 character string that varies with the current "session" (task or request)
    """
    current_task = get_current_task()
    if current_task is not None:
        return _quickcache_id(current_task.request)
    request = get_request()
    if request is not None:
        return _quickcache_id(request)
    # quickcache catches this and skips the cache
    # this happens during tests (outside a fake task/request context)
    # and during management commands
    raise ForceSkipCache("Not part of a session")


def _quickcache_id(obj):
    try:
        value = obj.__quickcache_id
    except AttributeError:
        value = b64encode(os.urandom(5)).decode("ascii").rstrip("=\n")
        obj.__quickcache_id = value
    return value


quickcache = get_django_quickcache(timeout=5 * 60, memoize_timeout=10,
                                   assert_function=quickcache_soft_assert,
                                   session_function=get_session_key)

__all__ = ['quickcache']
