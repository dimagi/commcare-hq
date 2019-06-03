from __future__ import absolute_import
from __future__ import unicode_literals
import warnings
import hashlib
from quickcache.django_quickcache import get_django_quickcache
from quickcache import ForceSkipCache
from celery._state import get_current_task
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
    session_id = None
    current_task = get_current_task()
    if current_task:
        # at least in tests, current_task may have the same id between different tasks!
        session_id = current_task.request.id
    if not session_id:
        request = get_request()
        if request:
            session_id = str(id(get_request()))
        else:
            session_id = None

    if session_id:
        session_id = session_id.encode('utf-8')
        # hash it so that similar numbers end up very different (esp. because we're truncating)
        return hashlib.md5(session_id).hexdigest()[:7]
    else:
        # quickcache catches this and skips the cache
        # this happens during tests (outside a fake task/request context)
        # and during management commands
        raise ForceSkipCache("Not part of a session")


quickcache = get_django_quickcache(timeout=5 * 60, memoize_timeout=10,
                                   assert_function=quickcache_soft_assert,
                                   session_function=get_session_key)

__all__ = ['quickcache']
