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
    
# DEPRECATED: use logging.exception() instead
def log_exception(e=None, extra_info=""):
    """Log an exception, with a stacktrace"""
    # you don't actually need the exception, since we rely on exc_info
    # left as an optional param because of existing code calling it
    # TODO: remove extra info, it's a relic of bhoma stuff
    if extra_info: 
        logging.error(extra_info)
    exc_type, value, tb = sys.exc_info()
    if e is not None:
        # if they passed in an exception use it.  this should be always
        # the same, otherwise the stack trace will be wrong.
        value = e
        exc_type = type(e)
    traceback_string = "".join(traceback.format_tb(tb))
    logging.error("%s: %s" % (exc_type, value))
    logging.error(traceback_string)
    #exception_logged.send(sender="logutil", exc_info=(exc_type, value, tb), extra_info=extra_info)

notify_logger = logging.getLogger('notify')

def notify_exception(request, message=None):
    notify_logger.error('Notify Exception: %s' % (message or request.path),
        exc_info=sys.exc_info(),
        extra={
            'status_code': 500,
            'request':request
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
