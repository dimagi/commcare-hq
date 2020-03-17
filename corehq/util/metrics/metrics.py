import abc
import re
from abc import abstractmethod
from functools import wraps
from typing import Iterable, List

from celery.task import periodic_task
from django.utils.functional import SimpleLazyObject

from corehq.util.soft_assert import soft_assert
from prometheus_client.utils import INF

METRIC_NAME_RE = re.compile(r'^[a-zA-Z_:.][a-zA-Z0-9_:.]*$')
METRIC_TAG_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
RESERVED_METRIC_TAG_NAME_RE = re.compile(r'^__.*$')
RESERVED_METRIC_TAG_NAMES = ['quantile', 'le']


def _enforce_prefix(name, prefix):
    soft_assert(fail_if_debug=True).call(
        not prefix or name.startswith(prefix),
        "Did you mean to call your metric 'commcare.{}'? ".format(name))


def _validate_tag_names(tag_names):
    tag_names = set(tag_names)
    for l in tag_names:
        if not METRIC_TAG_NAME_RE.match(l):
            raise ValueError('Invalid metric tag name: ' + l)
        if RESERVED_METRIC_TAG_NAME_RE.match(l):
            raise ValueError('Reserved metric tag name: ' + l)
        if l in RESERVED_METRIC_TAG_NAMES:
            raise ValueError('Reserved metric tag name: ' + l)
    return tag_names


DEFAULT_BUCKETS = (.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, INF)


class HqMetrics(metaclass=abc.ABCMeta):
    def initialize(self):
        pass

    def counter(self, name: str, value: float = 1, tags: dict = None, documentation: str = ''):
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        self._counter(name, value, tags, documentation)

    def gauge(self, name: str, value: float, tags: dict = None, documentation: str = ''):
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        self._gauge(name, value, tags, documentation)

    def histogram(self, name: str, value: float,
                  bucket_tag: str, buckets: List[int] = DEFAULT_BUCKETS, bucket_unit: str = '',
                  tags: dict = None, documentation: str = ''):
        """Create a histogram metric. Histogram implementations differ between provider. See provider
        implementations for details.
        """
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        self._histogram(name, value, bucket_tag, buckets, bucket_unit, tags, documentation)

    @abstractmethod
    def _counter(self, name, value, tags, documentation):
        raise NotImplementedError

    @abstractmethod
    def _gauge(self, name, value, tags, documentation):
        pass

    @abstractmethod
    def _histogram(self, name, value, bucket_tag, buckets, bucket_unit, tags, documentation):
        pass


class DummyMetrics:
    def __getattr__(self, item):
        if item in ('counter', 'gauge', 'histogram'):
            def _check(name, documentation, tags, *args, **kwargs):
                _enforce_prefix(name, 'commcare')
                _validate_tag_names(tags)
            return _check
        raise AttributeError


class DelegatedMetrics:
    def __init__(self, delegates):
        self.delegates = delegates

    def __getattr__(self, item):
        if item in ('counter', 'gauge', 'histogram'):
            def _record_metric(*args, **kwargs):
                for delegate in self.delegates:
                    getattr(delegate, item)(*args, **kwargs)
            return _record_metric
        raise AttributeError


def metrics_gauge_task(name, fn, run_every):
    """
    helper for easily registering gauges to run periodically

    To update a gauge on a schedule based on the result of a function
    just add to your app's tasks.py:

        my_calculation = metrics_gauge_task('commcare.my.metric', my_calculation_function,
                                            run_every=crontab(minute=0))

    """
    _enforce_prefix(name, 'commcare')

    @periodic_task(serializer='pickle', queue='background_queue', run_every=run_every,
                   acks_late=True, ignore_result=True)
    @wraps(fn)
    def inner(*args, **kwargs):
        from corehq.util.metrics import metrics_gauge
        # TODO: make this use prometheus push gateway
        metrics_gauge(name, fn(*args, **kwargs))

    return inner
