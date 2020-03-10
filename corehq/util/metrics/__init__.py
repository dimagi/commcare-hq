from corehq.util.metrics.datadog import DatadogMetrics
from corehq.util.metrics.metrics import DummyMetrics, DelegatedMetrics, HqMetrics
from corehq.util.metrics.prometheus import PrometheusMetrics

_metrics = None  # singleton/global


def get_metrics() -> HqMetrics:
    global _metrics
    if not _metrics:
        enabled = list(filter(lambda m: m.enabled(), [DatadogMetrics(), PrometheusMetrics()]))
        if not enabled:
            _metrics = DummyMetrics()

        if len(enabled) > 1:
            _metrics = DelegatedMetrics(enabled)

        _metrics = enabled[0]
    return _metrics
