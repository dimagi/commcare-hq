import time
from contextlib import ContextDecorator

from corehq.util.datadog import statsd, datadog_logger
from corehq.util.metrics import bucket_value
from corehq.util.soft_assert import soft_assert


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
