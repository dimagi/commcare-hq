from functools import wraps
from celery.task import periodic_task
from corehq.util.datadog import statsd, datadog_logger
from corehq.util.soft_assert import soft_assert


def datadog_gauge_task(name, fn, run_every, enforce_prefix='commcare'):
    """
    helper for easily registering datadog gauges to run periodically

    To update a datadog gauge on a schedule based on the result of a function
    just add to your app's tasks.py:

        my_calculation = datadog_gauge_task('my.datadog.metric', my_calculation_function,
                                            run_every=crontab(minute=0))

    """
    _enforce_prefix(name, enforce_prefix)

    datadog_gauge = _DatadogGauge(name, fn, run_every)
    return datadog_gauge.periodic_task()


def datadog_gauge(name, value, enforce_prefix='commcare', tags=None):
    _datadog_record(statsd.gauge, name, value, enforce_prefix, tags)


def datadog_counter(name, enforce_prefix='commcare', tags=None):
    _datadog_record(statsd.increment, name, 1, enforce_prefix, tags)


def _datadog_record(fn, name, value, enforce_prefix='commcare', tags=None):
    _enforce_prefix(name, enforce_prefix)
    try:
        fn(name, value, tags=tags)
    except Exception:
        datadog_logger.exception('Unable to record Datadog stats')


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


def _enforce_prefix(name, prefix):
    soft_assert(fail_if_debug=True).call(
        not prefix or name.split('.')[0] == prefix,
        "Did you mean to call your gauge 'commcare.{}'? "
        "If you're sure you want to forgo the prefix, you can "
        "pass enforce_prefix=None".format(name))
