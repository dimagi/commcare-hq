import abc
import re
from abc import abstractmethod
from typing import Iterable

from corehq.util.soft_assert import soft_assert

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
    def __init__(self, name: str, documentation: str, tag_names: Iterable=tuple(), tag_values=None):
        self.name = name
        if not METRIC_NAME_RE.match(name):
            raise ValueError('Invalid metric name: ' + name)
        _enforce_prefix(name, 'commcare')
        self.documentation = documentation
        self.tag_names = _validate_tag_names(tag_names)
        self.tag_values = tag_values

    def tag(self, **tag_kwargs):
        if sorted(tag_kwargs) != sorted(self.tag_names):
            raise ValueError('Incorrect tag names')

        tag_values = tuple(str(tag_kwargs[t]) for t in self.tag_names)
        return self._get_tagged_instance(tag_values)

    def _get_tagged_instance(self, tag_values):
        return self.__class__(self.name, self.documentation, self.tag_names, tag_values)

    def _validate_tags(self):
        if self.tag_names and not self.tag_values:
            raise Exception('Metric has missing tag values.')


class HqCounter(MetricBase):
    def inc(self, amount: float = 1):
        """Increment the counter by the given amount."""
        self._validate_tags()
        self._inc(amount)

    def _inc(self, amount: float = 1):
        """Override this method to record the metric"""
        pass


class HqGauge(MetricBase):
    def set(self, value: float):
        """Set gauge to the given value."""
        self._validate_tags()
        self._set(value)

    def _set(self, value: float):
        """Override this method to record the metric"""
        pass


class HqMetrics(metaclass=abc.ABCMeta):
    _counter_class = None
    _gauge_class = None

    @abstractmethod
    def enabled(self) -> bool:
        raise NotImplementedError

    def counter(self, name: str, documentation: str, tag_names: Iterable=tuple()) -> HqCounter:
        return self._counter_class(name, documentation, tag_names)

    def gauge(self, name: str, documentation: str, tag_names: Iterable=tuple()) -> HqGauge:
        return self._gauge_class(name, documentation, tag_names)


class DummyMetrics(HqMetrics):
    _counter_class = HqCounter
    _gauge_class = HqGauge

    def enabled(self) -> bool:
        return True


class DelegatedMetrics(HqMetrics):
    def __init__(self, delegates):
        self.delegates = delegates

    def enabled(self) -> bool:
        return True

    def counter(self, name: str, documentation: str, tag_names: Iterable=tuple()):
        return DelegatingCounter([
            d.counter(name, documentation, tag_names) for d in self.delegates
        ])

    def gauge(self, name: str, documentation: str, tag_names: Iterable=tuple()):
        return DelegatingGauge([
            d.gauge(name, documentation, tag_names) for d in self.delegates
        ])


class DelegatingMetric:
    def __init__(self, delegates):
        self._delegates = delegates

    def tag(self, **tag_kwargs):
        return self.__class__([
            d.tag(**tag_kwargs) for d in self._delegates
        ])


class DelegatingCounter(DelegatingMetric):
    def inc(self, amount: float = 1):
        for d in self._delegates:
            d.inc(amount)


class DelegatingGauge(DelegatingMetric):
    def set(self, value: float):
        for d in self._delegates:
            d.set(value)
