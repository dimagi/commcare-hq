from django.conf.urls import url

from corehq.util.metrics.views import prometheus_metrics

urlpatterns = [
    url(r"^metrics$", prometheus_metrics, name="prometheus-django-metrics")
]
