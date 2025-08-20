from django.urls import re_path as url

from corehq.util.metrics.views import prometheus_metrics

urlpatterns = [
    url(r"^metrics$", prometheus_metrics, name="prometheus-django-metrics")
]
