# When celery is launched with `celery -A corehq ...` it automatically
# finds the app at `corehq.celery.app`. This module is for that purpose
# alone, and should not be imported elsewhere.
import os

import django
from django.core.checks import run_checks
from django.core.exceptions import AppRegistryNotReady

from manage import init_hq_python_path, run_patches

init_hq_python_path()
run_patches()

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

django.setup()  # calls corehq.apps.celery.Config.ready()
try:
    run_checks()
except AppRegistryNotReady:
    pass

from corehq.apps.celery import app  # noqa: E402, F401
