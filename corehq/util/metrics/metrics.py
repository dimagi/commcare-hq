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
    tag_names = set(tag_names)
    for l in tag_names:
        if not METRIC_TAG_NAME_RE.match(l):
            raise ValueError('Invalid metric tag name: ' + l)
        if RESERVED_METRIC_TAG_NAME_RE.match(l):
            raise ValueError('Reserved metric tag name: ' + l)
        if l in RESERVED_METRIC_TAG_NAMES:
            raise ValueError('Reserved metric tag name: ' + l)
    return tag_names


class MetricBase:
    def __init__(self, name: str, documentation: str, tag_names: Iterable = ()):
        self.name = name
        if not METRIC_NAME_RE.match(name):
            raise ValueError('Invalid metric name: ' + name)
        _enforce_prefix(name, 'commcare')
        self.documentation = documentation
        self.tag_names = _validate_tag_names(tag_names)
        self._init_metric()

    def _init_metric(self):
        pass

    def _validate_tags(self, tag_values: dict):
        if self.tag_names and not tag_values:
            raise Exception('Metric has missing tag values.')

        if tag_values:
            assert isinstance(tag_values, dict)
            if tag_values.keys() != self.tag_names:
                raise ValueError('Incorrect tag names')

    def _record(self, value: float, tags: dict):
        raise NotImplementedError


class HqCounter(MetricBase):
    def inc(self, amount: float = 1, **tags):
        """Increment the counter by the given amount."""
        self._validate_tags(tags)
        self._record(amount, tags)


class HqGauge(MetricBase):
    def set(self, value: float, **tags):
        """Set gauge to the given value."""
        self._validate_tags(tags)
        self._record(value, tags)


DEFAULT_BUCKETS = (.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, INF)


class HqHistogram(MetricBase):

    def __init__(self, name: str, documentation: str,
                  bucket_tag: str, buckets: List[int] = DEFAULT_BUCKETS, bucket_unit: str = '',
                  tag_names: Iterable = ()):
        self._bucket_tag = bucket_tag
        self._buckets = buckets
        self._bucket_unit = bucket_unit
        if self._bucket_tag in tag_names:
            tag_names = tuple(name for name in tag_names if name != bucket_tag)
        super().__init__(name, documentation, tag_names)

    def observe(self, value: float, **tags):
        """Update histogram with the given value."""
        self._validate_tags(tags)
        self._record(value, tags)


class HqMetrics(metaclass=abc.ABCMeta):
    _counter_class = None
    _gauge_class = None
    _histogram_class = None

    @abstractmethod
    def enabled(self) -> bool:
        raise NotImplementedError

    def counter(self, name: str, documentation: str, tag_names: Iterable = ()) -> HqCounter:
        return self._counter_class(name, documentation, tag_names)

    def gauge(self, name: str, documentation: str, tag_names: Iterable = ()) -> HqGauge:
        return self._gauge_class(name, documentation, tag_names)

    def histogram(self, name: str, documentation: str,
                  bucket_tag: str, buckets: List[int] = DEFAULT_BUCKETS, bucket_unit: str = '',
                  tag_names: Iterable = ()) -> HqHistogram:
        """Create a histogram metric. Histogram implementations differ between provider. See provider
        implementations for details.
        """
        return self._histogram_class(
            name, documentation, bucket_tag, buckets=buckets, bucket_unit=bucket_unit, tag_names=tag_names
        )


class DummyMetric:
    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, item):
        if item in ('inc', 'set', 'observe'):
            return lambda *args, **kwargs: None
        raise AttributeError


class DummyMetrics(HqMetrics):
    _counter_class = DummyMetric
    _gauge_class = DummyMetric
    _histogram_class = DummyMetric

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

    def __getattr__(self, item):
        if item == self._record_fn_name:
            def record(*args, **kwargs):
                for metric in self._delegates:
                    getattr(metric, item)(*args, **kwargs)
            return record

        raise AttributeError
