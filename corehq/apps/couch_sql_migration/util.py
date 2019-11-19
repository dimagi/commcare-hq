import logging
from contextlib import contextmanager
from functools import wraps

import gevent
from greenlet import GreenletExit

log = logging.getLogger(__name__)


def exit_on_error(func):
    @wraps(func)
    def wrapper(*args, **kw):
        try:
            return func(*args, **kw)
        except gevent.get_hub().SYSTEM_ERROR:
            raise
        except GreenletExit:
            raise
        except BaseException as err:
            raise UnhandledError(err) from err
    return wrapper


def wait_for_one_task_to_complete(pool):
    if not pool:
        raise ValueError("pool is empty")
    with gevent.iwait(pool) as completed:
        next(completed)


@contextmanager
def gipc_process_error_handler():
    try:
        yield
    except (BrokenPipeError, EOFError) as err:
        def is_crash(err):
            return (
                isinstance(err, BrokenPipeError)
                or "the other pipe end is closed." in str(err)
            )
        if is_crash(err):
            log.error("process error: %s: %s", type(err).__name__, err)
            raise ProcessError(1)
        raise


class UnhandledError(SystemExit):
    pass


class ProcessError(SystemExit):
    pass
