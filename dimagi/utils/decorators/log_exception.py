import functools
import logging

class log_exception(object):
    """
    A decorator that can be used to log an exception stack trace and then
    reraise it.
    """

    def __call__(self, fn):
        @functools.wraps(fn)
        def decorated(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception, e:
                logging.exception('something went wrong calling {fn}: {msg}'.format(
                    fn=fn.__name__,
                    msg=str(e),
                ))
                raise
        return decorated
