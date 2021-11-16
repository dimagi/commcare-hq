from contextlib import contextmanager

from django.core.cache import cache

from corehq.const import DEFAULT_PARALLEL_EXECUTION_TIMEOUT
from corehq.util.exceptions import ParallelExecutionError
from corehq.util.soft_assert import soft_assert


@contextmanager
def drop_connected_signals(signal):
    """
    Use as a context manager to temporarily drop signals. Useful in tests.

    with drop_connected_signals(case_post_save):
       case.save()  # signals won't be called
    case.save()  # signals will be called again
    """
    connected_signals = signal.receivers
    signal.receivers = []
    try:
        yield
    finally:
        signal.receivers = connected_signals


@contextmanager
def notify_someone(email, success_message, error_message='Sorry, your HQ task failed!', send=True):
    def send_message_if_needed(message, exception=None):
        if email and send:
            soft_assert(to=email, notify_admins=False, send_to_ops=False)(False, message, exception)
    try:
        yield
        send_message_if_needed(success_message)
    except BaseException as e:
        send_message_if_needed(error_message, e)
        raise


@contextmanager
def catch_signal(signal):
    """Catch django signal and return the mocked call."""
    from unittest.mock import Mock
    handler = Mock()
    signal.connect(handler)
    yield handler
    signal.disconnect(handler)


@contextmanager
def prevent_parallel_execution(cache_key, timeout=DEFAULT_PARALLEL_EXECUTION_TIMEOUT):
    if cache.get(cache_key, False):
        raise ParallelExecutionError
    cache.set(cache_key, True, timeout)
    try:
        yield
    finally:
        cache.set(cache_key, False)
