from __future__ import absolute_import
from __future__ import unicode_literals
import sys
import logging
from corehq.util.global_request import get_request


notify_logger = logging.getLogger('notify')


def notify_error(message, details=None):
    notify_logger.error(message, extra=details)


def notify_exception(request, message=None, details=None, exec_info=None):
    """
    :param request: a Django request object
    :param message: message string
    :param details: dict with additional details to be included in the output
    """
    if request is None:
        request = get_request()
    if request is not None:
        message = message or request.path
    if isinstance(message, bytes):
        try:
            message = message.decode('utf-8')
        except UnicodeDecodeError:
            message = repr(message)

    message = 'Notify Exception: %s' % (
        message or "No message provided, fix error handler"
    )

    notify_logger.error(
        message,
        exc_info=exec_info or sys.exc_info(),
        extra={
            'status_code': 500,
            'request': request,
            'details': details,
        }
    )


def log_signal_errors(signal_results, message, details):
    has_errors = False
    for result in signal_results:
        # Second argument is None if there was no error
        return_val = result[1]
        if return_val and isinstance(return_val, Exception):
            notify_exception(
                None,
                message=message % return_val.__class__.__name__,
                details=details,
                exec_info=(type(return_val), return_val, return_val.__traceback__)
            )
            has_errors = True
    return has_errors
