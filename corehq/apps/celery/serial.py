from functools import partial

from corehq.apps.celery.concurrent import concurrent_task

serial_task = partial(concurrent_task, concurrency=1)
