import logging
from contextlib import contextmanager
from datetime import datetime
from functools import wraps

import gevent
from gevent.pool import Pool
from greenlet import GreenletExit

from dimagi.utils.parsing import ISO_DATETIME_FORMAT

log = logging.getLogger(__name__)


def get_ids_from_string_or_file(ids):
    if ids.startswith(("./", "/")):
        log.info("loading ids from file: %s", ids)
        with open(ids, encoding="utf-8") as fh:
            return [x.rstrip("\n") for x in fh if x.strip()]
    return [x for x in ids.split(",") if x]


def str_to_datetime(value):
    try:
        return datetime.strptime(value, ISO_DATETIME_FORMAT)
    except ValueError:
        sans_micros = ISO_DATETIME_FORMAT.replace(".%f", "")
        return datetime.strptime(value, sans_micros)


@contextmanager
def worker_pool(size=10):
    pool = Pool(size)
    try:
        yield pool
    finally:
        while not pool.join(timeout=10):
            log.info('Waiting on {} docs'.format(len(pool)))


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
