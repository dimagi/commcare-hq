import os

import prometheus_client
from django.http import HttpResponse
from prometheus_client import multiprocess


def prometheus_metrics(request):
    """Exports /metrics as a Django view.
    """
    if "prometheus_multiproc_dir" in os.environ:
        registry = prometheus_client.CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = prometheus_client.REGISTRY
    metrics_page = prometheus_client.generate_latest(registry)
    return HttpResponse(
        metrics_page, content_type=prometheus_client.CONTENT_TYPE_LATEST
    )
