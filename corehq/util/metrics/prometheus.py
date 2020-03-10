from typing import Iterable

import settings
from corehq.util.metrics.metrics import (
    HqCounter,
    HqGauge,
    HqMetrics,
    MetricBase,
)
from prometheus_client import Counter as PCounter
from prometheus_client import Gauge as PGauge


class PrometheusMetricBase(MetricBase):
    _metric_class = None

    def __init__(self, name: str, documentation: str, tag_names: Iterable=tuple(), tag_values=None, delegate=None):
        name = name.replace('.', '_')
        super().__init__(name, documentation, tag_names, tag_values)
        self._delegate = delegate or self._metric_class(name, documentation, tag_names, labelvalues=tag_values)

    def _get_tagged_instance(self, tag_values):
        delegate = self._delegate.labels(dict(zip(self.tag_names, tag_values)))
        return self.__class__(self.name, self.documentation, self.tag_names, self.tag_values, delegate)


class Counter(PrometheusMetricBase, HqCounter):
    _metric_class = PCounter

    def _inc(self, amount=1):
        self._delegate.inc(amount)


class Gauge(PrometheusMetricBase, HqGauge):
    _metric_class = PGauge

    def _set(self, value: float):
        self._delegate.set(value)


class PrometheusMetrics(HqMetrics):
    _counter_class = Counter
    _gauge_class = Gauge

    def enabled(self) -> bool:
        return settings.ENABLE_PROMETHEUS_METRICS
