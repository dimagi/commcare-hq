from django.conf.urls import re_path as url

from corehq.util.metrics.views import prometheus_metrics, datadog_histogram_metrics

urlpatterns = [
    url(r"^metrics$", prometheus_metrics, name="prometheus-django-metrics"),
    url(r"^metrics_datadog$", datadog_histogram_metrics, name="datadog_histogram_metrics"),
]
