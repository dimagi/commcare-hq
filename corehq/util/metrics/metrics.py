import abc
import logging
import re
from abc import abstractmethod
from collections import namedtuple
from collections.abc import Sequence
from typing import Any, Callable, Optional, Protocol, Union

from prometheus_client.utils import INF

from .const import ALERT_INFO
from .typing import AlertStr, Bucket, BucketName, MetricValue, TagValues

METRIC_NAME_RE = re.compile(r'^[a-zA-Z_:.][a-zA-Z0-9_:.]*$')
METRIC_TAG_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
RESERVED_METRIC_TAG_NAME_RE = re.compile(r'^__.*$')
RESERVED_METRIC_TAG_NAMES = ['quantile', 'le']
DEFAULT_BUCKETS: Sequence[Bucket] = (
    .005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, INF
)


metrics_logger = logging.getLogger('commcare.metrics')


def _enforce_prefix(name: str, prefix: str) -> None:
    from corehq.util.soft_assert import soft_assert
    soft_assert(fail_if_debug=True).call(
        not prefix or name.startswith(prefix),
        "Did you mean to call your metric 'commcare.{}'? ".format(name))


def _validate_tag_names(tag_values: Optional[TagValues]) -> set[str]:
    tag_names = set(tag_values or [])
    for tag_name in tag_names:
        if not METRIC_TAG_NAME_RE.match(tag_name):
            raise ValueError('Invalid metric tag name: ' + tag_name)
        if RESERVED_METRIC_TAG_NAME_RE.match(tag_name):
            raise ValueError('Reserved metric tag name: ' + tag_name)
        if tag_name in RESERVED_METRIC_TAG_NAMES:
            raise ValueError('Reserved metric tag name: ' + tag_name)
    return tag_names


class HqMetrics(metaclass=abc.ABCMeta):

    @property
    def accepted_gauge_params(self) -> list[str]:
        return []

    def initialize(self) -> None:
        pass

    def counter(
        self,
        name: str,
        value: MetricValue = 1,
        tags: Optional[TagValues] = None,
        documentation: str = '',
    ) -> None:
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        self._counter(name, value, tags, documentation)

    def gauge(
        self,
        name: str,
        value: MetricValue,
        tags: Optional[TagValues] = None,
        documentation: str = '',
        **kwargs: Any,
    ) -> None:
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        kwargs = {k: v for (k, v) in kwargs.items() if k in self.accepted_gauge_params}
        self._gauge(name, value, tags, documentation, **kwargs)

    def histogram(
        self,
        name: str,
        value: MetricValue,
        bucket_tag: str,
        buckets: Sequence[Bucket] = DEFAULT_BUCKETS,
        bucket_unit: str = '',
        tags: Optional[TagValues] = None,
        documentation: str = '',
    ) -> None:
        """Create a histogram metric. Histogram implementations differ between provider. See provider
        implementations for details.
        """
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        self._histogram(name, value, bucket_tag, buckets, bucket_unit, tags, documentation)

    def create_event(
        self,
        title: str,
        text: str,
        alert_type: AlertStr = ALERT_INFO,
        tags: Optional[TagValues] = None,
        aggregation_key: Optional[str] = None,
    ) -> None:
        _validate_tag_names(tags)
        self._create_event(title, text, alert_type, tags, aggregation_key)

    def push_metrics(self) -> None:
        pass

    @abstractmethod
    def _counter(
        self,
        name: str,
        value: MetricValue,
        tags: Optional[TagValues] = None,
        documentation: str = '',
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def _gauge(
        self,
        name: str,
        value: MetricValue,
        tags: Optional[TagValues] = None,
        documentation: str = '',
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def _histogram(
        self,
        name: str,
        value: MetricValue,
        bucket_tag: str,
        buckets: Sequence[Bucket],
        bucket_unit: str = '',
        tags: Optional[TagValues] = None,
        documentation: str = '',
    ) -> None:
        raise NotImplementedError

    def _create_event(
        self,
        title: str,
        text: str,
        alert_type: AlertStr = ALERT_INFO,
        tags: Optional[TagValues] = None,
        aggregation_key: Optional[str] = None,
    ) -> None:
        """Optional API to implement"""
        pass


class Sample(namedtuple('Sample', ['type', 'name', 'tags', 'value'])):
    def match_tags(self, tags: TagValues) -> bool:
        missing = object()
        return all([
            self.tags.get(tag, missing) == val
            for tag, val in tags.items()
        ])


class MetricsProto(Protocol):
    def counter(
        self,
        name: str,
        value: MetricValue = ...,
        tags: Optional[TagValues] = ...,
        documentation: str = ...,
    ) -> None:
        ...

    def gauge(
        self,
        name: str,
        value: MetricValue,
        tags: Optional[TagValues] = ...,
        documentation: str = ...,
        **kwargs: Any,
    ) -> None:
        ...

    def histogram(
        self,
        name: str,
        value: MetricValue,
        bucket_tag: str,
        buckets: Sequence[Bucket] = ...,
        bucket_unit: str = ...,
        tags: Optional[TagValues] = ...,
        documentation: str = ...,
    ) -> None:
        ...

    def push_metrics(self) -> None:
        ...

    def create_event(
        self,
        title: str,
        text: str,
        alert_type: AlertStr = ...,
        tags: Optional[TagValues] = ...,
        aggregation_key: Optional[str] = ...,
    ) -> None:
        ...


CheckFunc = Callable[..., None]


class DebugMetrics:
    def __init__(self, capture: bool = False) -> None:
        self._capture = capture
        self.metrics: list[Sample] = []

    def __getattr__(self, item: str) -> CheckFunc:
        if item in ('counter', 'gauge', 'histogram'):
            def _check(
                name: BucketName,
                value: MetricValue,
                *args: Any,
                **kwargs: Any,
            ) -> None:
                tags = kwargs.get('tags') or {}
                _enforce_prefix(name, 'commcare')
                _validate_tag_names(tags)
                metrics_logger.debug("[%s] %s %s %s", item, name, tags, value)
                if self._capture:
                    self.metrics.append(Sample(item, name, tags, value))
            return _check
        raise AttributeError(item)

    def push_metrics(self) -> None:
        pass

    def create_event(
        self,
        title: str,
        text: str,
        alert_type: AlertStr = ALERT_INFO,
        tags: Optional[TagValues] = None,
        aggregation_key: Optional[str] = None,
    ) -> None:
        _validate_tag_names(tags)
        metrics_logger.debug('Metrics event: (%s) %s\n%s\n%s', alert_type, title, text, tags)


RecordMetricFunc = Callable[..., None]


class DelegatedMetrics:
    def __init__(self, delegates: Sequence[MetricsProto]) -> None:
        self.delegates = delegates

    def __getattr__(self, item: str) -> RecordMetricFunc:
        if item in ('counter', 'gauge', 'histogram', 'create_event', 'push_metrics'):
            def _record_metric(*args: Any, **kwargs: Any) -> None:
                for delegate in self.delegates:
                    getattr(delegate, item)(*args, **kwargs)
            return _record_metric
        raise AttributeError(item)
