import settings
from corehq.util.metrics.metrics import (
    HqCounter,
    HqGauge,
    HqHistogram,
    HqMetrics,
    MetricBase,
)
from prometheus_client import Counter as PCounter
from prometheus_client import Gauge as PGauge
from prometheus_client import Histogram as PHistogram


class Counter(HqCounter):
    """https://prometheus.io/docs/concepts/metric_types/#counter"""

    def _init_metric(self):
        self.name = self.name.replace('.', '_')
        self._delegate = PCounter(self.name, self.documentation, self.tag_names)

    def _record(self, amount: float, tags):
        _get_labeled(self._delegate, tags).inc(amount)


class Gauge(HqGauge):
    """https://prometheus.io/docs/concepts/metric_types/#gauge"""

    def _init_metric(self):
        self.name = self.name.replace('.', '_')
        self._delegate = PGauge(self.name, self.documentation, self.tag_names)

    def _record(self, value: float, tags):
        _get_labeled(self._delegate, tags).set(value)


class Histogram(HqHistogram):
    """This metric class implements the native Prometheus Histogram type

    https://prometheus.io/docs/concepts/metric_types/#histogram
    """
    def _init_metric(self):
        self.name = self.name.replace('.', '_')
        self._delegate = PHistogram(self.name, self.documentation, self.tag_names, buckets=self._buckets)

    def _record(self, value: float, tags: dict):
        _get_labeled(self._delegate, tags).observe(value)


def _get_labeled(metric, labels):
    return metric.labels(**labels) if labels else metric


class PrometheusMetrics(HqMetrics):
    _counter_class = Counter
    _gauge_class = Gauge
    _histogram_class = Histogram

    def enabled(self) -> bool:
        return settings.ENABLE_PROMETHEUS_METRICS
