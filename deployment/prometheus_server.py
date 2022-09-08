"""
Simple WSGI server that exposes Prometheus metrics.

Environment variable `PROMETHEUS_MULTIPROC_DIR` must be set and match
the value used by Django.
"""
import os
from wsgiref.simple_server import make_server

from prometheus_client import CollectorRegistry, make_wsgi_app, multiprocess
from prometheus_client.exposition import _SilentHandler

# DEPRECATED: prometheus_multiproc_dir has been replaced by PROMETHEUS_MULTIPROC_DIR
multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR") or os.environ.get("prometheus_multiproc_dir")
if not multiproc_dir:
    raise Exception("Environment variable 'PROMETHEUS_MULTIPROC_DIR' is not set")

print(f"Exposing metrics from '{multiproc_dir}'")

registry = CollectorRegistry()
multiprocess.MultiProcessCollector(registry)

app = make_wsgi_app(registry)
httpd = make_server('', 9011, app, handler_class=_SilentHandler)
httpd.serve_forever()
