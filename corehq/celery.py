from __future__ import absolute_import, unicode_literals
import os

import django
from django.core.checks import run_checks
from django.core.exceptions import AppRegistryNotReady

from celery import Celery

from manage import init_hq_python_path, run_patches

init_hq_python_path()
run_patches()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

from django.conf import settings  # noqa

app = Celery('corehq')
app.config_from_object('django.conf:settings')
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

django.setup()
try:
    run_checks()
except AppRegistryNotReady:
    pass
