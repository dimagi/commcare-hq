import abc
import logging
import re
from abc import abstractmethod
from collections import namedtuple
from typing import List

from corehq.util.soft_assert import soft_assert
from prometheus_client.utils import INF

METRIC_NAME_RE = re.compile(r'^[a-zA-Z_:.][a-zA-Z0-9_:.]*$')
METRIC_TAG_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
RESERVED_METRIC_TAG_NAME_RE = re.compile(r'^__.*$')
RESERVED_METRIC_TAG_NAMES = ['quantile', 'le']


logger = logging.getLogger('commcare.metrics')


def _enforce_prefix(name, prefix):
    soft_assert(fail_if_debug=True).call(
        not prefix or name.startswith(prefix),
        "Did you mean to call your metric 'commcare.{}'? ".format(name))


def _validate_tag_names(tag_names):
    tag_names = set(tag_names or [])
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
        raise NotImplementedError

    @abstractmethod
    def _histogram(self, name, value, bucket_tag, buckets, bucket_unit, tags, documentation):
        raise NotImplementedError


Sample = namedtuple('Sample', ['type', 'name', 'tags', 'value'])


class DebugMetrics:
    def __init__(self, capture=False):
        self._capture = capture
        self.metrics = []

    def __getattr__(self, item):
        if item in ('counter', 'gauge', 'histogram'):
            def _check(name, value, *args, **kwargs):
                tags = kwargs.get('tags', {})
                _enforce_prefix(name, 'commcare')
                _validate_tag_names(tags)
                logger.debug("[%s] %s %s %s", item, name, tags, value)
                if self._capture:
                    self.metrics.append(Sample(item, name, tags, value))
            return _check
        raise AttributeError(item)


class DelegatedMetrics:
    def __init__(self, delegates):
        self.delegates = delegates

    def __getattr__(self, item):
        if item in ('counter', 'gauge', 'histogram'):
            def _record_metric(*args, **kwargs):
                for delegate in self.delegates:
                    getattr(delegate, item)(*args, **kwargs)
            return _record_metric
        raise AttributeError(item)
