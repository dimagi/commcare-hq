from functools import wraps
from celery.task import periodic_task
from corehq.util.datadog import statsd


def datadog_gauge_task(name, fn, run_every):
    """"
    helper for easily registering datadog gauges to run periodically

    To update a datadog gauge on a schedule based on the result of a function
    just add to your app's tasks.py:

        my_calculation = datadog_gauge_task('my.datadog.metric', my_calculation_function,
                                            run_every=crontab(minute=0))

    """

    datadog_gauge = _DatadogGauge(name, fn, run_every)
    return datadog_gauge.periodic_task()


class _DatadogGauge(object):

    def __init__(self, name, fn, run_every):
        self.name = name
        self.fn = fn
        self.run_every = run_every

    def periodic_task(self):
        @periodic_task('background_queue', run_every=self.run_every,
                       acks_late=True, ignore_result=True)
        @wraps(self.fn)
        def inner(*args, **kwargs):
            statsd.gauge(self.name, self.fn(*args, **kwargs))

        return inner
