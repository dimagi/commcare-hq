from typing import Iterable

import settings
from corehq.util.metrics.metrics import DummyMetrics, DelegatedMetrics, DEFAULT_BUCKETS
from dimagi.utils.modules import to_function

_metrics = None


def _get_metrics_provider():
    global _metrics
    if not _metrics:
        providers = []
        for provider_path in settings.METRICS_PROVIDERS:
            provider = to_function(provider_path)()
            provider.initialize()
            providers.append(provider)

        if not providers:
            _metrics = DummyMetrics()
        elif len(providers) > 1:
            _metrics = DelegatedMetrics(providers)
        else:
            _metrics = providers[0]
    return _metrics


def metrics_counter(name: str, value: float = 1, tags: dict = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.counter(name, value, tags, documentation)


def metrics_gauge(name: str, value: float, tags: dict = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.gauge(name, value, tags, documentation)


def metrics_histogram(
        name: str, value: float,
        bucket_tag: str, buckets: Iterable[int] = DEFAULT_BUCKETS, bucket_unit: str = '',
        tags: dict = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.histogram(name, value, bucket_tag, buckets, bucket_unit, tags, documentation)
