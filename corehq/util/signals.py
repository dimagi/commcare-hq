from __future__ import absolute_import
from __future__ import unicode_literals
from dimagi.utils.logging import notify_exception
from celery.signals import task_failure
import signal


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
        if type(signals) is not list:
            signals = [signals]
        if not all(type(sig) is int for sig in signals):
            raise TypeError()

        self.signals = signals
        self.handler = handler
        self.default_handler = default_handler

    def __enter__(self):
        for sig in self.signals:
            signal.signal(sig, self.handler)

    def __exit__(self, *args, **kwargs):
        for sig in self.signals:
            signal.signal(sig, self.default_handler)
