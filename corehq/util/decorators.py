import logging
import warnings
from contextlib import ContextDecorator, contextmanager
from functools import wraps

from django.conf import settings

import requests

from dimagi.utils.logging import notify_exception

from corehq.apps.celery import task
from corehq.util.global_request import get_request


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
    # indirectly causes Django settings access on import
    from corehq.util.metrics import metrics_counter

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


enterprise_skip = run_only_when(lambda: not settings.ENTERPRISE_MODE)


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
