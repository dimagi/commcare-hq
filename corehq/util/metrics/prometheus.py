from typing import List, Dict

from django.conf import settings
from prometheus_client import Counter as PCounter
from prometheus_client import Gauge as PGauge
from prometheus_client import Histogram as PHistogram
from prometheus_client import CollectorRegistry, multiprocess, push_to_gateway

from corehq.util.soft_assert import soft_assert
from corehq.util.metrics.metrics import HqMetrics

prometheus_soft_assert = soft_assert(to=[
    f'{name}@dimagi.com'
    for name in ['skelly', 'rkumar', 'sreddy']
])


class PrometheusMetrics(HqMetrics):
    """Prometheus Metrics Provider"""

    def __init__(self):
        self._metrics = {}

    def _counter(self, name: str, value: float = 1, tags: Dict[str, str] = None, documentation: str = ''):
        """See https://prometheus.io/docs/concepts/metric_types/#counter"""
        try:
            self._get_metric(PCounter, name, tags, documentation).inc(value)
        except ValueError:
            pass

    def _gauge(self, name: str, value: float, tags: Dict[str, str] = None, documentation: str = ''):
        """See https://prometheus.io/docs/concepts/metric_types/#histogram"""
        try:
            self._get_metric(PGauge, name, tags, documentation).set(value)
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
        metric = self._metrics.get(name)
        if not metric:
            tags = tags or {}
            metric = metric_type(name, documentation, labelnames=tags.keys(), **kwargs)
            self._metrics[name] = metric
        else:
            assert metric.__class__ == metric_type
        try:
            if getattr(settings, 'PUSHGATEWAY_HOST', None):
                self._push_to_gateway()
            return metric.labels(**tags) if tags else metric
        except ValueError:
            prometheus_soft_assert(False, 'Prometheus metric error', {
                'metric_name': name,
                'tags': list(tags),
                'expected_tags': metric._labelnames
            })
            raise

    def _push_to_gateway(self):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        host = getattr(settings, 'PUSHGATEWAY_HOST')
        try:
            push_to_gateway(host, job='batch_mode', registry=registry)
        except Exception:
            # Could get a URLOpenerror if Pushgateway is not running
            prometheus_soft_assert(False, 'Prometheus metric error while pushing to gateway')
