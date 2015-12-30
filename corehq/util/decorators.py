from functools import wraps
import logging
from corehq.util.global_request import get_request
from dimagi.utils.logging import notify_exception
from django.conf import settings


class ContextDecorator(object):
    """
    A base class that enables a context manager to also be used as a decorator.
    https://docs.python.org/3/library/contextlib.html#contextlib.ContextDecorator
    """
    def __call__(self, fn):
        @wraps(fn)
        def decorated(*args, **kwds):
            with self:
                return fn(*args, **kwds)
        return decorated


def handle_uncaught_exceptions(mail_admins=True):
    """Decorator to log uncaught exceptions and prevent them from
    bubbling up the call chain.
    """
    def _outer(fn):
        @wraps(fn)
        def _handle_exceptions(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                msg = "Uncaught exception from {}.{}".format(fn.__module__, fn.__name__)
                if mail_admins:
                    notify_exception(get_request(), msg)
                else:
                    logging.exception(msg)

        return _handle_exceptions
    return _outer


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


class require_debug_true(ContextDecorator):
    def __enter__(self):
        if not settings.DEBUG:
            raise Exception("This can only be called in DEBUG mode.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
