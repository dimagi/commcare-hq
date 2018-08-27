from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

import django
from django.core.checks import run_checks
from django.core.exceptions import AppRegistryNotReady

from manage import init_hq_python_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
init_hq_python_path()
django.setup()
try:
    run_checks()
except AppRegistryNotReady:
    pass

app = Celery()
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
