import inspect
import logging
import warnings
from contextlib import ContextDecorator, contextmanager
from functools import wraps

from django.conf import settings

import requests

from dimagi.utils.logging import notify_exception

from corehq.apps.celery import task
from corehq.util.global_request import get_request
from corehq.util.metrics import metrics_counter


def handle_uncaught_exceptions(mail_admins=True):
    """Decorator to log uncaught exceptions and prevent them from
    bubbling up the call chain.
    """
    def _outer(fn):
        @wraps(fn)
        def _handle_exceptions(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                msg = "Uncaught exception from {}.{}".format(fn.__module__, fn.__name__)
                if mail_admins:
                    notify_exception(get_request(), msg)
                else:
                    logging.exception(msg)

        return _handle_exceptions
    return _outer


@contextmanager
def silence_and_report_error(message, metric_name):
    """
    Prevent a piece of code from ever causing 500s if it errors

    Instead, report the issue to sentry and track the overall count as a metric
    """

    try:
        yield
    except Exception:
        notify_exception(None, message)
        metrics_counter(metric_name)
        if settings.UNIT_TESTING:
            raise


def run_only_when(condition):
    def outer(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            condition_ = condition() if callable(condition) else condition
            if condition_:
                return fn(*args, **kwargs)
        return inner
    return outer


enterprise_skip = run_only_when(not settings.ENTERPRISE_MODE)


class change_log_level(ContextDecorator):
    """
    Temporarily change the log level of a specific logger.
    Can be used as either a context manager or decorator.
    """

    def __init__(self, logger, level):
        self.logger = logging.getLogger(logger)
        self.new_level = level
        self.original_level = self.logger.level

    def __enter__(self):
        self.logger.setLevel(self.new_level)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.setLevel(self.original_level)


@contextmanager
def ignore_warning(warning_class):
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', warning_class)
        yield


class require_debug_true(ContextDecorator):

    def __enter__(self):
        if not settings.DEBUG:
            raise Exception("This can only be called in DEBUG mode.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class CouldNotAqcuireLock(Exception):
    pass


# Sorry this is so magic
def _get_unique_key(format_str, fn, *args, **kwargs):
    """
    Lines args and kwargs up with those specified in the definition of fn and
    passes the result to `format_str.format()`.
    """
    callargs = inspect.getcallargs(fn, *args, **kwargs)
    return ("{}-" + format_str).format(fn.__name__, **callargs)


def serial_task(unique_key, default_retry_delay=30, timeout=5 * 60, max_retries=3,
                queue='background_queue', ignore_result=True, serializer=None):
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

        @task(bind=True, queue=queue, ignore_result=ignore_result, default_retry_delay=default_retry_delay,
              max_retries=max_retries, **task_kwargs)
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
                msg = "Could not aquire lock '{}' for task '{}'.".format(
                    key, fn.__name__)
                self.retry(exc=CouldNotAqcuireLock(msg))
        return _inner
    return decorator


def analytics_task(default_retry_delay=10, max_retries=3, queue='analytics_queue', serializer='json'):
    '''
        defines a task that posts data to one of our analytics endpoints. It retries the task
        up to 3 times if the post returns with a status code indicating an error with the post
        that is not our fault.
    '''
    def decorator(func):
        @task(bind=True, queue=queue, ignore_result=True, acks_late=True,
              default_retry_delay=default_retry_delay, max_retries=max_retries, serializer=serializer)
        @wraps(func)
        def _inner(self, *args, **kwargs):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.HTTPError as e:
                # if its a bad request, raise the exception because it is our fault
                res = e.response
                status_code = res.status_code if isinstance(res, requests.models.Response) else res.status
                if status_code == 400:
                    raise
                else:
                    self.retry(exc=e)
        return _inner
    return decorator


def hqnottest(func):
    func.__test__ = False
    return func
