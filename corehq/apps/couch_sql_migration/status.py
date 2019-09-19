import gevent
from gevent.event import Event


def run_status_logger(log_status, get_status, status_interval):
    """Start a status logger loop in a greenlet

    Log status every `status_interval` seconds unless it evaluates to
    false, in which case the loop is not started.

    :param log_status: a status logging function.
    :param get_status: a function returning a status object to be logged.
    :param status_interval: number of seconds between status logging.
    :returns: A function that stops the logger loop.
    """
    def status_logger():
        while not exit.wait(timeout=status_interval):
            log_status(get_status())
        log_status(get_status())

    def stop():
        exit.set()
        loop.join()

    if status_interval:
        exit = Event()
        loop = gevent.spawn(status_logger)
        return stop
    return lambda: None
