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
