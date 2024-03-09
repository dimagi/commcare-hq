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

.. autoclass:: corehq.util.metrics.metrics_track_errors


Other Notes
===========

* All metrics must use the prefix 'commcare.'
"""
from contextlib import ContextDecorator
from functools import wraps
from typing import Callable, Dict, Iterable

from django.conf import settings

from sentry_sdk import add_breadcrumb

from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function

from corehq import toggles
from corehq.apps.celery import periodic_task
from corehq.util.quickcache import quickcache
from corehq.util.timer import TimingContext

from .const import ALERT_INFO, COMMON_TAGS, MPM_ALL, GATED_DETAILED_TAGS
from .metrics import (
    DEFAULT_BUCKETS,
    DebugMetrics,
    DelegatedMetrics,
    _enforce_prefix,
    metrics_logger,
)
from .utils import (
    DAY_SCALE_TIME_BUCKETS,
    bucket_value,
    make_buckets_from_timedeltas,
)

__all__ = [
    'metrics_counter',
    'metrics_gauge',
    'metrics_histogram',
    'metrics_gauge_task',
    'create_metrics_event',
    'metrics_histogram_timer',
    'make_buckets_from_timedeltas',
    'DAY_SCALE_TIME_BUCKETS',
    'bucket_value',
]


def metrics_counter(name: str, value: float = 1, tags: Dict[str, str] = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.counter(name, value, tags=tags, documentation=documentation)


def metrics_gauge(name: str, value: float, tags: Dict[str, str] = None, documentation: str = '',
                  multiprocess_mode: str = MPM_ALL):
    """
    kwargs:
        multiprocess_mode: See PrometheusMetrics._gauge for documentation. This is only passed
            to PrometheusMetrics since it is one of PrometheusMetrics.accepted_gauge_params
    """
    provider = _get_metrics_provider()
    provider.gauge(name, value, tags=tags, documentation=documentation, multiprocess_mode=multiprocess_mode)


def metrics_histogram(
        name: str, value: float,
        bucket_tag: str, buckets: Iterable[int] = DEFAULT_BUCKETS, bucket_unit: str = '',
        tags: Dict[str, str] = None, documentation: str = ''):
    provider = _get_metrics_provider()
    provider.histogram(
        name, value, bucket_tag,
        buckets=buckets, bucket_unit=bucket_unit, tags=tags, documentation=documentation
    )


def metrics_gauge_task(name, fn, run_every, multiprocess_mode=MPM_ALL):
    """
    Helper for easily registering gauges to run periodically

    To update a gauge on a schedule based on the result of a function
    just add to your app's tasks.py:

    ::

        my_calculation = metrics_gauge_task(
            'commcare.my.metric', my_calculation_function, run_every=crontab(minute=0)
        )

    kwargs:
        multiprocess_mode: See PrometheusMetrics._gauge for documentation.
    """
    _enforce_prefix(name, 'commcare')

    @periodic_task(queue='background_queue', run_every=run_every, acks_late=True, ignore_result=True)
    @wraps(fn)
    def inner():
        from corehq.util.metrics import metrics_gauge
        metrics_gauge(name, fn(), multiprocess_mode=multiprocess_mode)

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
        _get_metrics_provider().create_event(title, text, alert_type, tags, aggregation_key)
    except Exception as e:
        metrics_logger.exception('Error creating metrics event', e)


class metrics_histogram_timer(TimingContext):
    """
    Create a context manager that times and reports to the metric providers as a histogram.
    If the block raises an exception, that will be logged as well.

    Example Usage:

    ::

        timer = metrics_histogram_timer('commcare.some.special.metric', tags={
            'type': type,
        }, timing_buckets=(.001, .01, .1, 1, 10, 100))
        with timer:
            some_special_thing()

    This will result it a call to `metrics_histogram` with the timer value.

    Note: Histograms are implemented differently by each provider. See documentation for details.

    :param metric: Name of the metric (must start with 'commcare.')
    :param tags: metric tags to include
    :param timing_buckets: sequence of numbers representing time thresholds, in seconds
    :param callback: a callable which will be called when exiting the context manager with a single argument
                     of the timer duration
    :return: A context manager that will perform the specified timing
             and send the specified metric
    """

    def __init__(self, metric: str, timing_buckets: Iterable[int], tags: Dict[str, str] = None,
                 callback: Callable = None):
        super().__init__()
        self._metric = metric
        self._timing_buckets = timing_buckets
        self._tags = tags
        self._callback = callback
        self._errored = False

    def stop(self, name=None):
        super().stop(name)
        if self._callback:
            self._callback(self.duration)
        metrics_histogram(
            self._metric, self.duration, bucket_tag='duration',
            buckets=self._timing_buckets, bucket_unit='s', tags=self._tags
        )
        if self._errored:
            metrics_counter(f'{self._metric}.error', tags=self._tags)
        timer_name = self._metric
        if self._metric.startswith('commcare.'):
            timer_name = ".".join(self._metric.split('.')[1:])  # remove the 'commcare.' prefix
        add_breadcrumb(
            category="timing",
            message=f"{timer_name}: {self.duration:0.3f}",
            level="info",
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._errored = exc_type is not None
        super().__exit__(exc_type, exc_val, exc_tb)  # this calls self.stop


class metrics_track_errors(ContextDecorator):
    """Record when something succeeds or errors in the configured metrics provider

    Eg: This code will log to `commcare.myfunction.succeeded` when it completes
    successfully, and to `commcare.myfunction.failed` when an exception is
    raised.

    ::

        @metrics_track_errors('myfunction')
        def myfunction():
            pass
    """

    def __init__(self, name):
        self.succeeded_name = "commcare.{}.succeeded".format(name)
        self.failed_name = "commcare.{}.failed".format(name)

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not exc_type:
            metrics_counter(self.succeeded_name)
        else:
            metrics_counter(self.failed_name)


def limit_domains(domain_name):
    """Return the domain name if it's among a privileged set that get tagged individually

    Else return __other__.  This is used to limit the number of tag combinations sent to datadog.
    """
    if toggles.DETAILED_TAGGING.enabled(domain_name):
        return domain_name
    return '__other__'


def limit_tags(tags: Dict[str, str], domain: str):
    from corehq import toggles
    if toggles.HIGH_COUNT_DETAILED_TAGGING.enabled(domain):
        return tags

    return {k: v for k, v in tags.items() if k not in GATED_DETAILED_TAGS}


@quickcache([], timeout=24 * 60 * 60)
def _domains_to_tag():
    # Only tag big projects individually
    # I expect this implementation may need to evolve
    from corehq.apps.accounting import models
    return set(models.Subscription.visible_objects.filter(
        is_active=True,
        plan_version__plan__edition=models.SoftwarePlanEdition.ENTERPRISE,
        service_type__in=[models.SubscriptionType.IMPLEMENTATION, models.SubscriptionType.SANDBOX],
    ).values_list(
        'subscriber__domain',
        flat=True
    ))


def push_metrics():
    provider = _get_metrics_provider()
    provider.push_metrics()


_metrics = []


def _get_metrics_provider():
    if not _metrics:
        _global_setup()
        providers = []
        for provider_path in settings.METRICS_PROVIDERS:
            try:
                provider = to_function(provider_path, failhard=True)()
                providers.append(provider)
            except Exception:
                notify_exception(None, f"Cannot load {provider_path}")

        if not providers:
            metrics = DebugMetrics()
        elif len(providers) > 1:
            metrics = DelegatedMetrics(providers)
        else:
            metrics = providers[0]
        _metrics.append(metrics)
    return _metrics[-1]


def _global_setup():
    if settings.UNIT_TESTING or settings.SERVER_ENVIRONMENT != 'staging':
        try:
            from ddtrace import tracer
            tracer.enabled = False
        except ImportError:
            pass
