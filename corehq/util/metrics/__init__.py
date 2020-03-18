from functools import wraps
from typing import Iterable

from celery.task import periodic_task

import settings
from corehq.util.metrics.metrics import DebugMetrics, DelegatedMetrics, DEFAULT_BUCKETS, _enforce_prefix
from dimagi.utils.modules import to_function

__all__ = [
    'metrics_counter',
    'metrics_gauge',
    'metrics_histogram',
]

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
            _metrics = DebugMetrics()
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
