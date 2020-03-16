from typing import List, Iterable

from corehq.util.metrics.datadog import DatadogMetrics
from corehq.util.metrics.metrics import DummyMetrics, DelegatedMetrics, DEFAULT_BUCKETS
from corehq.util.metrics.prometheus import PrometheusMetrics

_metrics = None


def _get_metrics_provider():
    global _metrics
    if not _metrics:
        enabled = list(filter(lambda m: m.enabled(), [DatadogMetrics(), PrometheusMetrics()]))
        if not enabled:
            _metrics = DummyMetrics()
        elif len(enabled) > 1:
            _metrics = DelegatedMetrics(enabled)
        else:
            _metrics = enabled[0]
    return _metrics


def metrics_counter(name: str, value: float = 1, tags: dict = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.counter(name, value, tags, documentation)


def metrics_gauge(name: str, value: float, tags: dict = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.gauge(name, value, tags, documentation)


def metrics_histogram(name: str, value: float,
                  bucket_tag: str, buckets: Iterable[int] = DEFAULT_BUCKETS, bucket_unit: str = '',
                  tags: dict = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.histogram(name, value, bucket_tag, buckets, bucket_unit, tags, documentation)
