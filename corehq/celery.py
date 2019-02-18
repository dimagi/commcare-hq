from __future__ import absolute_import, unicode_literals
import os

from celery import Celery

from manage import init_hq_python_path

init_hq_python_path()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
app = Celery()
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
