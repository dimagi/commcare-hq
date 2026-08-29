import glob
import os

preload_app = True
worker_class = 'gevent'
keepalive = 60
timeout = 900
# In the standard production setup, max_requests, max_requests_jitter, and
# graceful_timeout are overridden by command-line arguments in the supervisor
# conf (managed by commcare-cloud), which take precedence over this file.
max_requests = 240
max_requests_jitter = int(max_requests * 0.5)
# defaults to 30 sec, setting to 5 minutes to fight `GreenletExit`s
graceful_timeout = 5*60
# defaults to 4094, increasing to avoid https://manage.dimagi.com/default.asp?283517#1532884
limit_request_line = 4500


def post_fork(server, worker):
    # hacky way to address gunicorn gevent requests hitting django too early before urls are loaded
    # see: https://github.com/benoitc/gunicorn/issues/527#issuecomment-19601046
    from django.urls import resolve
    resolve('/')


def on_starting(server):
    try:
        _remove_prometheus_metric_files()
    except Exception:
        server.log.exception("Error clearing Prometheus metrics")


def _remove_prometheus_metric_files():
    path = os.environ.get('PROMETHEUS_MULTIPROC_DIR')
    if not path:
        return

    for f in glob.glob(os.path.join(path, '*.db')):
        os.remove(f)


def child_exit(server, worker):
    try:
        _mark_prometheus_worker_dead(worker)
    except Exception:
        server.log.exception("Error clearing Prometheus live metrics")


def _mark_prometheus_worker_dead(worker):
    path = os.environ.get('PROMETHEUS_MULTIPROC_DIR')
    if not path:
        return

    from prometheus_client import multiprocess
    multiprocess.mark_process_dead(worker.pid, path)
