from django.utils.functional import SimpleLazyObject

from corehq.util.metrics.datadog import DatadogMetrics
from corehq.util.metrics.metrics import DummyMetrics, DelegatedMetrics, HqMetrics
from corehq.util.metrics.prometheus import PrometheusMetrics


def _get_metrics():
    enabled = list(filter(lambda m: m.enabled(), [DatadogMetrics(), PrometheusMetrics()]))
    if not enabled:
        return [DummyMetrics()]
    return enabled


metrics = DelegatedMetrics(SimpleLazyObject(_get_metrics))  # singleton/global
