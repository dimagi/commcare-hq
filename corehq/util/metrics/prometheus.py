from collections.abc import Sequence
from threading import Lock
from types import TracebackType
from typing import Any, Literal, Optional, Protocol, Type, Union

from django.conf import settings

from prometheus_client import REGISTRY, CollectorRegistry
from prometheus_client import Counter as PCounter
from prometheus_client import Gauge as PGauge
from prometheus_client import Histogram as PHistogram
from prometheus_client import pushadd_to_gateway

from corehq.util.soft_assert import soft_assert

from .const import MPM_ALL
from .metrics import HqMetrics
from .typing import (
    Bucket,
    MetricValue,
    PrometheusMultiprocessModeStr,
    TagValues,
)

prometheus_soft_assert = soft_assert(to=[
    f'{name}@dimagi.com'
    for name in ['skelly', 'rkumar']
])


PMetric = Union[PCounter, PGauge, PHistogram]


class Lockable(Protocol):
    def __enter__(self) -> bool:
        ...

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Optional[bool]:
        ...


class NullLock:
    def __enter__(self) -> bool:
        return True

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Literal[False]:
        return False


class PrometheusMetrics(HqMetrics):
    """Prometheus Metrics Provider"""

    def __init__(self) -> None:
        self._metrics: dict[str, PMetric] = {}
        self._additional_kwargs: dict[str, Any] = {}
        self._push_gateway_host = getattr(settings, 'PROMETHEUS_PUSHGATEWAY_HOST', None)
        self._lock: Lockable
        if self._push_gateway_host:
            self._lock = Lock()
            self._registry = CollectorRegistry()
        else:
            self._lock = NullLock()
            self._registry = REGISTRY

    @property
    def accepted_gauge_params(self) -> list[str]:
        return ['multiprocess_mode']

    def _counter(
        self,
        name: str,
        value: MetricValue = 1,
        tags: Optional[TagValues] = None,
        documentation: str = '',
    ) -> None:
        """
        See https://prometheus.io/docs/concepts/metric_types/#counter
        """
        try:
            self._get_metric(PCounter, name, tags, documentation).inc(value)
        except ValueError:
            pass

    def _gauge(
        self,
        name: str,
        value: MetricValue,
        tags: Optional[TagValues] = None,
        documentation: str = '',
        multiprocess_mode: PrometheusMultiprocessModeStr = MPM_ALL,
        **kwargs: Any,
    ) -> None:
        """
        See https://prometheus.io/docs/concepts/metric_types/#histogram
        """
        try:
            self._get_metric(PGauge, name, tags, documentation, multiprocess_mode=multiprocess_mode).set(value)
        except ValueError:
            pass

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
        """
        A cumulative histogram with a base metric name of ``name``
        exposes multiple time series during a scrape:

        * cumulative counters for the observation buckets, exposed as
          ``<name>_bucket{le="<upper inclusive bound>"}``
        * the total sum of all observed values, exposed as
          ``<name>_sum``
        * the count of events that have been observed, exposed as
          ``<name>_count`` (identical to `<name>_bucket{le="+Inf"}`
          above)

        For example
        ::

            h = metrics_histogram(
                'commcare.request_duration', 1.4,
                bucket_tag='duration', buckets=[1,2,3], bucket_units='ms',
                tags=tags
            )

            # resulting metrics
            # commcare_request_duration_bucket{...tags..., le="1.0"} 0.0
            # commcare_request_duration_bucket{...tags..., le="2.0"} 1.0
            # commcare_request_duration_bucket{...tags..., le="3.0"} 1.0
            # commcare_request_duration_bucket{...tags..., le="+Inf"} 1.0
            # commcare_request_duration_sum{...tags...} 1.4
            # commcare_request_duration_count{...tags...} 1.0

        See https://prometheus.io/docs/concepts/metric_types/#histogram
        """
        try:
            self._get_metric(PHistogram, name, tags, documentation, buckets=buckets).observe(value)
        except ValueError:
            pass

    def _get_metric(
        self,
        metric_type: Type[PMetric],
        name: str,
        tags_values: Optional[TagValues],
        documentation: str,
        **kwargs: Any,
    ) -> PMetric:
        name = name.replace('.', '_')
        tags = tags_values or {}
        if isinstance(metric_type, PCounter) and name.endswith('_total'):
            # this suffix gets added to counter metrics by the Prometheus client
            name = name[:-6]
        with self._lock:
            metric = self._metrics.get(name)
            if not metric:
                metric = metric_type(
                    name, documentation, labelnames=tags.keys(), registry=self._registry, **kwargs
                )
                self._metrics[name] = metric
            else:
                assert metric.__class__ == metric_type
        try:
            return metric.labels(**tags) if tags else metric
        except ValueError as e:
            prometheus_soft_assert(False, 'Prometheus metric error', {
                'error': e,
                'metric_name': name,
                'tags': tags,
                'expected_tags': metric._labelnames
            })
            raise

    def push_metrics(self) -> None:
        if self._push_gateway_host:
            with self._lock:
                registry = self._registry
                self._metrics.clear()
                self._registry = CollectorRegistry()

            try:
                pushadd_to_gateway(self._push_gateway_host, job='celery', registry=registry)
            except Exception:
                prometheus_soft_assert(False, 'Prometheus metric error while pushing to gateway')
