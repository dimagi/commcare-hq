import abc
import logging
import re
from abc import abstractmethod
from collections import namedtuple
from collections.abc import Sequence
from typing import Any, Callable, Iterable, Optional, Protocol

from prometheus_client.utils import INF
from typing_extensions import Concatenate, ParamSpec

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


def _validate_tag_names(tag_names: Iterable[str]) -> set[str]:
    tag_names = set(tag_names or [])
    for l in tag_names:
        if not METRIC_TAG_NAME_RE.match(l):
            raise ValueError('Invalid metric tag name: ' + l)
        if RESERVED_METRIC_TAG_NAME_RE.match(l):
            raise ValueError('Reserved metric tag name: ' + l)
        if l in RESERVED_METRIC_TAG_NAMES:
            raise ValueError('Reserved metric tag name: ' + l)
    return tag_names


class HqMetrics(metaclass=abc.ABCMeta):

    @property
    def accepted_gauge_params(self):
        return []

    def initialize(self):
        pass

    def counter(
        self,
        name: str,
        value: float = 1.0,
        tags: Optional[TagValues] = None,
        documentation: str = '',
    ) -> None:
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        self._counter(name, value, tags, documentation)

    def gauge(
        self,
        name: str,
        value: float,
        tags: Optional[TagValues] = None,
        documentation: str = '',
        **kwargs,
    ) -> None:
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        kwargs = {k: v for (k, v) in kwargs.items() if k in self.accepted_gauge_params}
        self._gauge(name, value, tags, documentation, **kwargs)

    def histogram(
        self,
        name: str,
        value: float,
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
    def _counter(self, name, value, tags, documentation):
        raise NotImplementedError

    @abstractmethod
    def _gauge(self, name, value, tags, documentation, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def _histogram(self, name, value, bucket_tag, buckets, bucket_unit, tags, documentation):
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
    def match_tags(self, tags):
        missing = object()
        return all([
            self.tags.get(tag, missing) == val
            for tag, val in tags.items()
        ])


class MetricsProto(Protocol):
    def counter(self, *args, **kwargs):
        ...

    def gauge(self, *args, **kwargs):
        ...

    def histogram(self, *args, **kwargs):
        ...

    def push_metrics(self) -> Any:
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


P = ParamSpec('P')
CheckFunc = Callable[Concatenate[BucketName, MetricValue, P], None]


class DebugMetrics:
    def __init__(self, capture=False):
        self._capture = capture
        self.metrics = []

    def __getattr__(self, item: str) -> CheckFunc:
        if item in ('counter', 'gauge', 'histogram'):
            def _check(
                name: BucketName,
                value: MetricValue,
                *args: P.args,
                **kwargs: P.kwargs,
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


RecordMetricFunc = Callable[P, None]


class DelegatedMetrics:
    def __init__(self, delegates):
        self.delegates = delegates

    def __getattr__(self, item: str) -> RecordMetricFunc:
        if item in ('counter', 'gauge', 'histogram', 'create_event', 'push_metrics'):
            def _record_metric(*args: P.args, **kwargs: P.kwargs) -> None:
                for delegate in self.delegates:
                    getattr(delegate, item)(*args, **kwargs)
            return _record_metric
        raise AttributeError(item)
