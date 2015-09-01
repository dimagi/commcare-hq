from __future__ import absolute_import
import sys
import traceback
import logging

LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG
}


def get_log_level(level):
    return LOG_LEVELS.get(level, logging.INFO)
    

def set_log_level(level):
    loglevel = LOG_LEVELS.get(level, logging.INFO)
    logging.basicConfig(level=loglevel)
    

notify_logger = logging.getLogger('notify')


def notify_error(message):
    notify_logger.error(message)


def notify_exception(request, message=None, details=None):
    """
    :param request: a Django request object
    :param message: message string
    :param details: dict with additional details to be included in the output
    """
    if request is not None:
        message = message or request.path
    notify_logger.error(
        'Notify Exception: %s' % (message
                                  or "No message provided, fix error handler"),
        exc_info=sys.exc_info(),
        extra={
            'status_code': 500,
            'request': request,
            'details': details,
        }
    )


def notify_js_exception(request, message=None, details=None):
    notify_logger.error(
        'Notify JS Exception: {}'.format(message),
        extra={
            'request': request,
            'details': details,
        }
    )


def get_traceback(limit):
    from cStringIO import StringIO
    import traceback
    f = StringIO()
    traceback.print_stack(file=f, limit=15 + limit)
    lines = f.getvalue().strip().split('\n')
    count = 2
    for line in reversed(lines[:-2 * count]):
        if not line.lstrip().startswith("File"):
            continue
        elif '/restkit/' in line or '/couchdbkit/' in line:
            count += 1
        else:
            break

    end = -2 * count
    start = -2 * (count + limit)

    return "{traceback}\n[plus {skipped} other frames]".format(
        traceback='\n'.join(lines[start:end]),
        skipped=count,
    )
