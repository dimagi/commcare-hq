import glob
import os

preload_app = True
worker_class = 'gevent'
keepalive = 60
timeout = 900
max_requests = 240
max_requests_jitter = int(max_requests * 0.5)
# defaults to 30 sec, setting to 5 minutes to fight `GreenletExit`s
graceful_timeout = 5*60
# defaults to 4094, increasing to avoid https://manage.dimagi.com/default.asp?283517#1532884
limit_request_line = 4500


def post_fork(server, worker):
    from manage import run_patches
    run_patches()

    # hacky way to address gunicorn gevent requests hitting django too early before urls are loaded
    # see: https://github.com/benoitc/gunicorn/issues/527#issuecomment-19601046
    from django.urls import resolve
    resolve('/')


def on_starting(server):
    """Wipe hte metrics from previous processes"""
    path = os.environ.get('prometheus_multiproc_dir')
    for f in glob.glob(os.path.join(path, '*.db')):
        os.remove(f)


def child_exit(server, worker):
    from prometheus_client import multiprocess
    multiprocess.mark_process_dead(worker.pid)
