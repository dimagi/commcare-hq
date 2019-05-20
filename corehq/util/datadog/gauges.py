from __future__ import absolute_import
from __future__ import unicode_literals

import time
from functools import wraps

from celery.task import periodic_task
from corehq.util.datadog import statsd, datadog_logger
from corehq.util.decorators import ContextDecorator
from corehq.util.soft_assert import soft_assert
from corehq.util.datadog.utils import bucket_value
from corehq.util.timer import TimingContext


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


def datadog_histogram(name, value, enforce_prefix='commcare', tags=None):
    """
    Usage: Used to track the statistical distribution of a set of values over a statsd flush period.
    Actually submits as multiple metrics:
    """
    _datadog_record(statsd.histogram, name, value, enforce_prefix, tags)


def datadog_gauge(name, value, enforce_prefix='commcare', tags=None):
    """
    Stored as a GAUGE type in the datadog web application. Each value in the stored timeseries
    is the last gauge value submitted for that metric during the statsd flush period.
    """
    _datadog_record(statsd.gauge, name, value, enforce_prefix, tags)


def datadog_counter(name, value=1, enforce_prefix='commcare', tags=None):
    """
    Usage: Used to increment a counter of events.
    Stored as a RATE type in the datadog web application. Each value in the stored timeseries
    is a time-normalized delta of the counter's value over that statsd flush period.
    """
    _datadog_record(statsd.increment, name, value, enforce_prefix, tags)


def _datadog_record(fn, name, value, enforce_prefix='commcare', tags=None):
    _enforce_prefix(name, enforce_prefix)
    try:
        fn(name, value, tags=tags)
    except Exception:
        datadog_logger.exception('Unable to record Datadog stats')


def datadog_bucket_timer(metric, tags, timing_buckets, callback=None):
    """
    create a context manager that times and reports to datadog using timing buckets

    adds a 'duration' tag specifying which predefined timing bucket the timing fell into,
    see the `bucket_value` function for more info.

    Example Usage:

        timer = datadog_bucket_timer('commcare.some.special.metric', tags=[
            'type:{}'.format(type),
        ], timing_buckets=(.001, .01, .1, 1, 10, 100))
        with timer:
            some_special_thing()

    This will result it a datadog counter metric with a 'duration' tag, with the possible values
    lt_0.001, lt_0.01, lt_0.1, lt_001, lt_010, lt_100, and over_100.

    :param metric: Name of the datadog metric (must start with 'commcare.')
    :param tags: Datadog tags to include
    :param timing_buckets: sequence of numbers representing time thresholds, in seconds
    :return: A context manager that will perform the specified timing
             and send the specified metric

    """
    timer = TimingContext()
    original_stop = timer.stop

    def new_stop(name=None):
        original_stop(name)
        if callback:
            callback(timer.duration)
        datadog_counter(
            metric,
            tags=list(tags) + ['duration:%s' % bucket_value(timer.duration, timing_buckets, 's')]
        )

    timer.stop = new_stop
    return timer


class _DatadogGauge(object):

    def __init__(self, name, fn, run_every):
        self.name = name
        self.fn = fn
        self.run_every = run_every

    def periodic_task(self):
        @periodic_task(serializer='pickle', queue='background_queue', run_every=self.run_every,
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


class datadog_track_errors(ContextDecorator):
    """Record when something succeeds or errors in datadog

    Eg: This code will log to commcare.myfunction.succeeded when it completes
    successfully, and to commcare.myfunction.failed when an exception is
    raised.

        @datadog_track_errors('myfunction')
        def myfunction():
            pass
    """

    def __init__(self, name, duration_buckets=None):
        self.succeeded_name = "commcare.{}.succeeded".format(name)
        self.failed_name = "commcare.{}.failed".format(name)
        self.duration_buckets = duration_buckets
        self.timer_start = None

    def __enter__(self):
        if self.duration_buckets:
            self.timer_start = time.time()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.duration_buckets:
            duration = time.time() - self.timer_start
            duration_value = bucket_value(duration, self.duration_buckets, unit='s')
            tags = ['duration:{}'.format(duration_value)]
        else:
            tags = None
        if not exc_type:
            datadog_counter(self.succeeded_name, tags=tags)
        else:
            datadog_counter(self.failed_name, tags=tags)
