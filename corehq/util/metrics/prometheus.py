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


class PrometheusMetricBase(MetricBase):
    _metric_class = None

    def _init_metric(self):
        super()._init_metric()
        self.name = self.name.replace('.', '_')
        delegate = self._kwargs.get('delegate')
        self._delegate = delegate or self._metric_class(self.name, self.documentation, self.tag_names)

    def _get_tagged_instance(self, tag_values: dict):
        delegate = self._delegate.labels(**tag_values)
        return self.__class__(
            self.name, self.documentation,
            tag_names=self.tag_names, tag_values=tag_values, delegate=delegate, **self._kwargs
        )


class Counter(PrometheusMetricBase, HqCounter):
    """https://prometheus.io/docs/concepts/metric_types/#counter"""
    _metric_class = PCounter

    def _record(self, amount: float):
        self._delegate.inc(amount)


class Gauge(PrometheusMetricBase, HqGauge):
    """https://prometheus.io/docs/concepts/metric_types/#gauge"""
    _metric_class = PGauge

    def _record(self, value: float):
        self._delegate.set(value)


class Histogram(PrometheusMetricBase, HqHistogram):
    """This metric class implements the native Prometheus Histogram type

    https://prometheus.io/docs/concepts/metric_types/#histogram
    """
    def _init_metric(self):
        """Overriding this so that we can pass in the buckets to the Prometheus class"""
        HqHistogram._init_metric(self)  # skip _init_metric on PrometheusMetricBase
        self.name = self.name.replace('.', '_')
        self._delegate = self._kwargs.get('delegate')
        if not self._delegate:
            self._delegate = PHistogram(self.name, self.documentation, self.tag_names, buckets=self._buckets)

    def _record(self, value: float):
        self._delegate.observe(value)


class PrometheusMetrics(HqMetrics):
    _counter_class = Counter
    _gauge_class = Gauge
    _histogram_class = Histogram

    def enabled(self) -> bool:
        return settings.ENABLE_PROMETHEUS_METRICS
