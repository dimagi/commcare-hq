import os
from typing import Union

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotFound

import prometheus_client
from prometheus_client import multiprocess


def prometheus_metrics(
    request: HttpRequest,
) -> Union[HttpResponse, HttpResponseNotFound]:
    """Exports /metrics as a Django view. Only available in DEBUG mode.
    """
    if not settings.DEBUG:
        return HttpResponseNotFound()

    if "prometheus_multiproc_dir" in os.environ:
        registry = prometheus_client.CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = prometheus_client.REGISTRY
    metrics_page = prometheus_client.generate_latest(registry)
    return HttpResponse(
        metrics_page, content_type=prometheus_client.CONTENT_TYPE_LATEST
    )
