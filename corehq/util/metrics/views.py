import os

from django.http import HttpResponse, HttpResponseNotFound

import prometheus_client
import settings
from prometheus_client import multiprocess


def prometheus_metrics(request):
    """Exports /metrics as a Django view. Only available in DEBUG mode.
    """
    if not settings.DEBUG:
        return HttpResponseNotFound()

    # DEPRECATED: prometheus_multiproc_dir has been replaced by PROMETHEUS_MULTIPROC_DIR
    if "PROMETHEUS_MULTIPROC_DIR" in os.environ or "prometheus_multiproc_dir" in os.environ:
        registry = prometheus_client.CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = prometheus_client.REGISTRY
    metrics_page = prometheus_client.generate_latest(registry)
    return HttpResponse(
        metrics_page, content_type=prometheus_client.CONTENT_TYPE_LATEST
    )
