"""
Metrics collection
******************

.. contents::
   :local:

This package exposes functions and utilities to record metrics in CommCare. These metrics
are exported / exposed to the configured metrics providers. Supported providers are:

    * Datadog
    * Prometheus

Providers are enabled using the `METRICS_PROVIDER` setting. Multiple providers can be
enabled concurrently:

::

    METRICS_PROVIDERS = [
        'corehq.util.metrics.prometheus.PrometheusMetrics',
        'corehq.util.metrics.datadog.DatadogMetrics',
    ]

If no metrics providers are configured CommCare will log all metrics to the `commcare.metrics` logger
at the DEBUG level.

Metric tagging
==============
Metrics may be tagged by passing a dictionary of tag names and values. Tags should be used
to add dimensions to a metric e.g. request type, response status.

Tags should not originate from unbounded sources or sources with high dimensionality such as
timestamps, user IDs, request IDs etc. Ideally a tag should not have more than 10 possible values.

Read more about tagging:

* https://prometheus.io/docs/practices/naming/#labels
* https://docs.datadoghq.com/tagging/

Metric Types
============

Counter metric
''''''''''''''

A counter is a cumulative metric that represents a single monotonically increasing counter
whose value can only increase or be reset to zero on restart. For example, you can use a
counter to represent the number of requests served, tasks completed, or errors.

Do not use a counter to expose a value that can decrease. For example, do not use a counter
for the number of currently running processes; instead use a gauge.

::

    metrics_counter('commcare.case_import.count', 1, tags={'domain': domain})


Gauge metric
''''''''''''

A gauge is a metric that represents a single numerical value that can arbitrarily go up and down.

Gauges are typically used for measured values like temperatures or current memory usage,
but also "counts" that can go up and down, like the number of concurrent requests.

::

    metrics_gauge('commcare.case_import.queue_length', queue_length)

For regular reporting of a gauge metric there is the `metrics_gauge_task` function:

.. autofunction:: corehq.util.metrics.metrics_gauge_task

Histogram metric
''''''''''''''''

A histogram samples observations (usually things like request durations or response sizes)
and counts them in configurable buckets.

::

    metrics_histogram(
        'commcare.case_import.duration', timer_duration,
        bucket_tag='size', buckets=[10, 50, 200, 1000], bucket_unit='s',
        tags={'domain': domain}
    )

Histograms are recorded differently in the different providers.

.. automethod:: corehq.util.metrics.datadog.DatadogMetrics._histogram

.. automethod:: corehq.util.metrics.prometheus.PrometheusMetrics._histogram


Utilities
=========

.. autofunction:: corehq.util.metrics.create_metrics_event

.. autofunction:: corehq.util.metrics.metrics_gauge_task

.. autofunction:: corehq.util.metrics.metrics_histogram_timer


Other Notes
===========

* All metrics must use the prefix 'commcare.'
"""
from functools import wraps
from typing import Iterable, Callable, Dict

from celery.task import periodic_task

import settings
from corehq.util.timer import TimingContext
from dimagi.utils.modules import to_function
from .const import COMMON_TAGS, ALERT_INFO
from .metrics import (
    DebugMetrics,
    DelegatedMetrics,
    DEFAULT_BUCKETS,
    _enforce_prefix,
    metrics_logger
)

__all__ = [
    'metrics_counter',
    'metrics_gauge',
    'metrics_histogram',
    'metrics_gauge_task',
    'create_metrics_event',
    'metrics_histogram_timer',
]

_metrics = []


def _get_metrics_provider():
    if not _metrics:
        providers = []
        for provider_path in settings.METRICS_PROVIDERS:
            provider = to_function(provider_path)()
            providers.append(provider)

        if not providers:
            metrics = DebugMetrics()
        elif len(providers) > 1:
            metrics = DelegatedMetrics(providers)
        else:
            metrics = providers[0]
        _metrics.append(metrics)
    return _metrics[-1]


def metrics_counter(name: str, value: float = 1, tags: Dict[str, str] = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.counter(name, value, tags=tags, documentation=documentation)


def metrics_gauge(name: str, value: float, tags: Dict[str, str] = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.gauge(name, value, tags=tags, documentation=documentation)


def metrics_histogram(
        name: str, value: float,
        bucket_tag: str, buckets: Iterable[int] = DEFAULT_BUCKETS, bucket_unit: str = '',
        tags: Dict[str, str] = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.histogram(
        name, value, bucket_tag,
        buckets=buckets, bucket_unit=bucket_unit, tags=tags, documentation=documentation
    )


def metrics_gauge_task(name, fn, run_every):
    """
    Helper for easily registering gauges to run periodically

    To update a gauge on a schedule based on the result of a function
    just add to your app's tasks.py:

    ::

        my_calculation = metrics_gauge_task(
            'commcare.my.metric', my_calculation_function, run_every=crontab(minute=0)
        )

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


def create_metrics_event(title: str, text: str, alert_type: str = ALERT_INFO,
                         tags: Dict[str, str] = None, aggregation_key: str = None):
    """
    Send an event record to the monitoring provider.

    Currently only implemented by the Datadog provider.

    :param title: Title of the event
    :param text: Event body
    :param alert_type: Event type. One of 'success', 'info', 'warning', 'error'
    :param tags: Event tags
    :param aggregation_key: Key to use to group multiple events
    """
    tags = COMMON_TAGS.update(tags or {})
    try:
        _get_metrics_provider().create_event(title, text, tags, alert_type, aggregation_key)
    except Exception as e:
        metrics_logger.exception('Error creating metrics event', e)


def metrics_histogram_timer(metric: str, timing_buckets: Iterable[int], tags: Dict[str, str] = None,
                            bucket_tag: str = 'duration', callback: Callable = None):
    """
    Create a context manager that times and reports to the metric providers as a histogram

    Example Usage:

    ::

        timer = metrics_histogram_timer('commcare.some.special.metric', tags={
            'type': type,
        ], timing_buckets=(.001, .01, .1, 1, 10, 100))
        with timer:
            some_special_thing()

    This will result it a call to `metrics_histogram` with the timer value.

    Note: Histograms are implemented differently by each provider. See documentation for details.

    :param metric: Name of the metric (must start with 'commcare.')
    :param tags: metric tags to include
    :param timing_buckets: sequence of numbers representing time thresholds, in seconds
    :param bucket_tag: The name of the bucket tag to use (if used by the underlying provider)
    :param callback: a callable which will be called when exiting the context manager with a single argument
                     of the timer duratio
    :return: A context manager that will perform the specified timing
             and send the specified metric

    """
    timer = TimingContext()
    original_stop = timer.stop

    def new_stop(name=None):
        original_stop(name)
        if callback:
            callback(timer.duration)
        metrics_histogram(
            metric, timer.duration,
            bucket_tag=bucket_tag, buckets=timing_buckets, bucket_unit='s',
            tags=tags
        )

    timer.stop = new_stop
    return timer
