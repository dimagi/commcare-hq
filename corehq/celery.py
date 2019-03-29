from __future__ import absolute_import, unicode_literals

import datetime
import os

import django
from celery.signals import after_task_publish, task_prerun
from django.core.cache import cache
from django.core.checks import run_checks
from django.core.exceptions import AppRegistryNotReady

from celery import Celery

from manage import init_hq_python_path, run_patches

init_hq_python_path()
run_patches()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

app = Celery()
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

django.setup()
try:
    run_checks()
except AppRegistryNotReady:
    pass


@after_task_publish.connect
def celery_add_time_sent(headers=None, body=None, **kwargs):
    info = headers if 'task' in headers else body
    task_id = info['id']
    cache.set('task.{}.time_sent'.format(task_id), datetime.datetime.utcnow())


@task_prerun.connect
def celery_record_time_to_start(task_id=None, task=None, **kwargs):
    from corehq.util.datadog.gauges import datadog_gauge, datadog_counter
    time_sent = cache.get('task.{}.time_sent'.format(task_id))
    tags = [
        'celery_task_name:{}'.format(task.name),
        'celery_queue:{}'.format(task.queue),
    ]
    if time_sent:
        time_to_start = (datetime.datetime.utcnow() - time_sent).total_seconds()
        datadog_gauge('commcare.celery.task.time_to_start', time_to_start, tags=tags)
    else:
        datadog_counter('commcare.celery.task.time_to_start_unavailable', tags=tags)
