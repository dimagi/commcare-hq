import collections
import signal
from functools import wraps

from django.dispatch import Signal

from celery.signals import task_failure

from dimagi.utils.logging import notify_exception


@task_failure.connect
def log_celery_task_exception(task_id, exception, traceback, einfo, *args, **kwargs):
    notify_exception('Celery task failure', exec_info=einfo.exc_info)


class SignalHandlerContext(object):
    """ Used to clean up long running processes gracefully on unexpected exits

    :param <int|list<ints>> signals: the signals to handle. each should be sourced from the signal module
    :param <lambda> handler: the handler to field the signals
    :param <int> default_handler: the default handler. don't touch if you need more explanation
    """

    def __init__(self, signals, handler, default_handler=signal.SIG_DFL):
        if not isinstance(signals, collections.Iterable):
            signals = [signals]
        for sig in signals:
            if not isinstance(sig, int):
                raise TypeError("bad signals: {} in {}".format(sig, signals))

        self.signals = signals
        self.handler = handler
        self.default_handler = default_handler

    def __enter__(self):
        for sig in self.signals:
            signal.signal(sig, self.handler)

    def __exit__(self, *args, **kwargs):
        for sig in self.signals:
            signal.signal(sig, self.default_handler)


pre_command = Signal(providing_args=["args", "kwargs"])
post_command = Signal(providing_args=["args", "kwargs", "outcome"])


def signalcommand(func):
    """Python decorator for management command handle defs that sends out a pre/post signal."""

    @wraps(func)
    def inner(self, *args, **kwargs):
        pre_command.send(self.__class__, args=args, kwargs=kwargs)
        try:
            ret = func(self, *args, **kwargs)
        except BaseException as e:
            post_command.send(self.__class__, args=args, kwargs=kwargs, outcome=e)
            raise

        post_command.send(self.__class__, args=args, kwargs=kwargs, outcome=ret)
        return ret
    return inner
