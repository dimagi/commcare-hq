from functools import wraps

import gevent


def exit_on_error(func):
    @wraps(func)
    def wrapper(*args, **kw):
        try:
            func(*args, **kw)
        except gevent.get_hub().SYSTEM_ERROR:
            raise
        except BaseException as err:
            raise UnhandledError(err) from err
    return wrapper


class UnhandledError(SystemExit):
    pass
