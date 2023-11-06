import abc
import logging
import re
from abc import abstractmethod
from collections import namedtuple
from typing import List, Dict

from corehq.util.metrics.const import ALERT_INFO
from prometheus_client.utils import INF

METRIC_NAME_RE = re.compile(r'^[a-zA-Z_:.][a-zA-Z0-9_:.]*$')
METRIC_TAG_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
RESERVED_METRIC_TAG_NAME_RE = re.compile(r'^__.*$')
RESERVED_METRIC_TAG_NAMES = ['quantile', 'le']


metrics_logger = logging.getLogger('commcare.metrics')


def _enforce_prefix(name, prefix):
    from corehq.util.soft_assert import soft_assert
    soft_assert(fail_if_debug=True).call(
        not prefix or name.startswith(prefix),
        "Did you mean to call your metric 'commcare.{}'? ".format(name))


def _validate_tag_names(tag_names):
    tag_names = set(tag_names or [])
    for tag_name in tag_names:
        if not METRIC_TAG_NAME_RE.match(tag_name):
            raise ValueError('Invalid metric tag name: ' + tag_name)
        if RESERVED_METRIC_TAG_NAME_RE.match(tag_name):
            raise ValueError('Reserved metric tag name: ' + tag_name)
        if tag_name in RESERVED_METRIC_TAG_NAMES:
            raise ValueError('Reserved metric tag name: ' + tag_name)
    return tag_names


DEFAULT_BUCKETS = (.005, .01, .025, .05, .075, .1, .25, .5, .75, 1.0, 2.5, 5.0, 7.5, 10.0, INF)


class HqMetrics(metaclass=abc.ABCMeta):

    @property
    def accepted_gauge_params(self):
        return []

    def initialize(self):
        pass

    def counter(self, name: str, value: float = 1, tags: Dict[str, str] = None, documentation: str = ''):
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        self._counter(name, value, tags, documentation)

    def gauge(self, name: str, value: float, tags: Dict[str, str] = None, documentation: str = '', **kwargs):
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        kwargs = {k: v for (k, v) in kwargs.items() if k in self.accepted_gauge_params}
        self._gauge(name, value, tags, documentation, **kwargs)

    def histogram(self, name: str, value: float,
                  bucket_tag: str, buckets: List[int] = DEFAULT_BUCKETS, bucket_unit: str = '',
                  tags: Dict[str, str] = None, documentation: str = ''):
        """Create a histogram metric. Histogram implementations differ between provider. See provider
        implementations for details.
        """
        _enforce_prefix(name, 'commcare')
        _validate_tag_names(tags)
        self._histogram(name, value, bucket_tag, buckets, bucket_unit, tags, documentation)

    def create_event(self, title: str, text: str, alert_type: str = ALERT_INFO,
                     tags: Dict[str, str] = None, aggregation_key: str = None):
        _validate_tag_names(tags)
        self._create_event(title, text, alert_type, tags, aggregation_key)

    def push_metrics(self):
        pass

    @abstractmethod
    def _counter(self, name, value, tags, documentation):
        raise NotImplementedError

    @abstractmethod
    def _gauge(self, name, value, tags, documentation):
        raise NotImplementedError

    @abstractmethod
    def _histogram(self, name, value, bucket_tag, buckets, bucket_unit, tags, documentation):
        raise NotImplementedError

    def _create_event(self, title: str, text: str, alert_type: str = ALERT_INFO,
                     tags: Dict[str, str] = None, aggregation_key: str = None):
        """Optional API to implement"""
        pass


class Sample(namedtuple('Sample', ['type', 'name', 'tags', 'value'])):
    def match_tags(self, tags):
        missing = object()
        return all([
            self.tags.get(tag, missing) == val
            for tag, val in tags.items()
        ])


class DebugMetrics:
    def __init__(self, capture=False):
        self._capture = capture
        self.metrics = []

    def __getattr__(self, item):
        if item in ('counter', 'gauge', 'histogram'):
            def _check(name, value, *args, **kwargs):
                tags = kwargs.get('tags') or {}
                _enforce_prefix(name, 'commcare')
                _validate_tag_names(tags)
                metrics_logger.debug("[%s] %s %s %s", item, name, tags, value)
                if self._capture:
                    self.metrics.append(Sample(item, name, tags, value))
            return _check
        raise AttributeError(item)

    def push_metrics(self):
        pass

    def create_event(self, title: str, text: str, alert_type: str = ALERT_INFO,
                     tags: Dict[str, str] = None, aggregation_key: str = None):
        _validate_tag_names(tags)
        metrics_logger.debug('Metrics event: (%s) %s\n%s\n%s', alert_type, title, text, tags)


class DelegatedMetrics:
    def __init__(self, delegates):
        self.delegates = delegates

    def __getattr__(self, item):
        if item in ('counter', 'gauge', 'histogram', 'create_event', 'push_metrics'):
            def _record_metric(*args, **kwargs):
                for delegate in self.delegates:
                    getattr(delegate, item)(*args, **kwargs)
            return _record_metric
        raise AttributeError(item)
