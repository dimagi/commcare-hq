import abc
import re
from abc import abstractmethod
from typing import Iterable, List

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
    tag_names = tuple(tag_names)
    for l in tag_names:
        if not METRIC_TAG_NAME_RE.match(l):
            raise ValueError('Invalid metric tag name: ' + l)
        if RESERVED_METRIC_TAG_NAME_RE.match(l):
            raise ValueError('Reserved metric tag name: ' + l)
        if l in RESERVED_METRIC_TAG_NAMES:
            raise ValueError('Reserved metric tag name: ' + l)
    return tag_names


class MetricBase:
    def __init__(self, name: str, documentation: str, tag_names: Iterable = tuple(), **kwargs):
        self.name = name
        if not METRIC_NAME_RE.match(name):
            raise ValueError('Invalid metric name: ' + name)
        _enforce_prefix(name, 'commcare')
        self.documentation = documentation
        self.tag_names = _validate_tag_names(tag_names)
        self.tag_values = kwargs.pop('tag_values', None)
        self._kwargs = kwargs
        self._init_metric()

    def _init_metric(self):
        pass

    def tag(self, **tag_kwargs):
        if sorted(tag_kwargs) != sorted(self.tag_names):
            raise ValueError('Incorrect tag names')

        tag_values = tuple(str(tag_kwargs[t]) for t in self.tag_names)
        return self._get_tagged_instance(tag_values)

    def _get_tagged_instance(self, tag_values):
        return self.__class__(
            self.name, self.documentation, tag_names=self.tag_names, tag_values=tag_values, **self._kwargs
        )

    def _validate_tags(self):
        if self.tag_names and not self.tag_values:
            raise Exception('Metric has missing tag values.')

    def _record(self, value: float):
        raise NotImplementedError


class HqCounter(MetricBase):
    def inc(self, amount: float = 1):
        """Increment the counter by the given amount."""
        self._validate_tags()
        self._record(amount)


class HqGauge(MetricBase):
    def set(self, value: float):
        """Set gauge to the given value."""
        self._validate_tags()
        self._record(value)


DEFAULT_BUCKETS = (.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, INF)


class HqHistogram(MetricBase):

    def _init_metric(self):
        self._buckets = self._kwargs.get('buckets') or DEFAULT_BUCKETS
        self._bucket_unit = self._kwargs.get('bucket_unit', '')
        self._bucket_tag = self._kwargs.get('bucket_tag')
        if self._bucket_tag in self.tag_names:
            self.tag_names = tuple([name for name in self.tag_names if name != self._bucket_tag])

    def observe(self, value: float):
        """Update histogram with the given value."""
        self._validate_tags()
        self._record(value)


class HqMetrics(metaclass=abc.ABCMeta):
    _counter_class = None
    _gauge_class = None
    _histogram_class = None

    @abstractmethod
    def enabled(self) -> bool:
        raise NotImplementedError

    def counter(self, name: str, documentation: str, tag_names: Iterable = tuple()) -> HqCounter:
        return self._counter_class(name, documentation, tag_names)

    def gauge(self, name: str, documentation: str, tag_names: Iterable = tuple()) -> HqGauge:
        return self._gauge_class(name, documentation, tag_names)

    def histogram(self, name: str, documentation: str,
                  bucket_tag: str, buckets: List[int] = DEFAULT_BUCKETS, bucket_unit: str = '',
                  tag_names: Iterable = tuple()) -> HqHistogram:
        """Create a histogram metric. Histogram implementations differ between provider. See provider
        implementations for details.
        """
        return self._histogram_class(
            name, documentation, tag_names, bucket_tag=bucket_tag, buckets=buckets, bucket_unit=bucket_unit
        )


class DummyMetrics(HqMetrics):
    _counter_class = HqCounter
    _gauge_class = HqGauge

    def enabled(self) -> bool:
        return True


class DelegatedMetrics:
    """This class makes the metric class instantiation lazy and
    also multiple metrics providers to be used."""
    def __init__(self, delegates):
        self.delegates = delegates
        self._types = {
            'counter': 'inc',
            'gauge': 'set',
            'histogram': 'observe',
        }

    def __getattr__(self, item):
        if item in self._types:
            def _make_type(*args, **kwargs):
                return SimpleLazyObject(lambda: DelegatingMetric([
                    getattr(d, item)(*args, **kwargs) for d in self.delegates
                ], self._types[item]))
            return _make_type
        raise AttributeError


class DelegatingMetric:
    def __init__(self, delegates, record_fn_name):
        self._delegates = delegates
        self._record_fn_name = record_fn_name

    def tag(self, *args, **kwargs):
        return self.__class__([d.tag(*args, **kwargs) for d in self._delegates])

    def __getattr__(self, item):
        if item == self._record_fn_name:
            def record(*args, **kwargs):
                for metric in self._delegates:
                    getattr(metric, item)(*args, **kwargs)
            return record

        raise AttributeError
