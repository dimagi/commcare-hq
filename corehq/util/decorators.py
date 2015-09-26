from functools import wraps
import logging
from corehq.util.global_request import get_request
from dimagi.utils.logging import notify_exception


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
