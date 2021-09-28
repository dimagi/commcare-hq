from threading import Lock
from typing import Dict, List

from django.conf import settings

from prometheus_client import CollectorRegistry, REGISTRY
from prometheus_client import Counter as PCounter
from prometheus_client import Gauge as PGauge
from prometheus_client import Histogram as PHistogram
from prometheus_client import pushadd_to_gateway

from corehq.util.metrics.metrics import HqMetrics
from corehq.util.soft_assert import soft_assert

from .const import MPM_ALL

prometheus_soft_assert = soft_assert(to=[
    f'{name}@dimagi.com'
    for name in ['skelly', 'rkumar']
])


class NullLock:
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class PrometheusMetrics(HqMetrics):
    """Prometheus Metrics Provider"""

    def __init__(self):
        self._metrics = {}
        self._additional_kwargs = {}
        self._push_gateway_host = getattr(settings, 'PROMETHEUS_PUSHGATEWAY_HOST', None)
        if self._push_gateway_host:
            self._lock = Lock()
            self._registry = CollectorRegistry()
        else:
            self._lock = NullLock()
            self._registry = REGISTRY

    @property
    def accepted_gauge_params(self):
        return ['multiprocess_mode']

    def _counter(self, name: str, value: float = 1, tags: Dict[str, str] = None, documentation: str = ''):
        """See https://prometheus.io/docs/concepts/metric_types/#counter"""
        try:
            self._get_metric(PCounter, name, tags, documentation).inc(value)
        except ValueError:
            pass

    def _gauge(self, name: str, value: float, tags: Dict[str, str]=None, documentation: str = '',
               multiprocess_mode: str = MPM_ALL):
        """
        See https://prometheus.io/docs/concepts/metric_types/#histogram

        multiprocess_mode: can be one of below values
            'all': Default. Return a timeseries per process alive or dead.
            'liveall': Return a timeseries per process that is still alive.
            'livesum': Return a single timeseries that is the sum of the values of alive processes.
            'max': Return a single timeseries that is the maximum of the values of all processes, alive or dead.
            'min': Return a single timeseries that is the minimum of the values of all processes, alive or dead.
        """
        try:
            self._get_metric(PGauge, name, tags, documentation, multiprocess_mode=multiprocess_mode).set(value)
        except ValueError:
            pass

    def _histogram(self, name: str, value: float, bucket_tag: str, buckets: List[int], bucket_unit: str = '',
                  tags: Dict[str, str] = None, documentation: str = ''):
        """
        A cumulative histogram with a base metric name of <name> exposes multiple time series
        during a scrape:

        * cumulative counters for the observation buckets, exposed as
          `<name>_bucket{le="<upper inclusive bound>"}`
        * the total sum of all observed values, exposed as `<name>_sum`
        * the count of events that have been observed, exposed as `<name>_count`
          (identical to `<name>_bucket{le="+Inf"}` above)

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

        See https://prometheus.io/docs/concepts/metric_types/#histogram"""
        try:
            self._get_metric(PHistogram, name, tags, documentation, buckets=buckets).observe(value)
        except ValueError:
            pass

    def _get_metric(self, metric_type, name, tags, documentation, **kwargs):
        name = name.replace('.', '_')
        if isinstance(metric_type, PCounter) and name.endswith('_total'):
            # this suffix get's added to counter metrics by the Prometheus client
            name = name[:-6]
        with self._lock:
            metric = self._metrics.get(name)
            if not metric:
                tags = tags or {}
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

    def push_metrics(self):
        if self._push_gateway_host:
            with self._lock:
                registry = self._registry
                self._metrics.clear()
                self._registry = CollectorRegistry()

            try:
                pushadd_to_gateway(self._push_gateway_host, job='celery', registry=registry)
            except Exception:
                prometheus_soft_assert(False, 'Prometheus metric error while pushing to gateway')
