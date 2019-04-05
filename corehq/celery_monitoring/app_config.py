from __future__ import absolute_import
from __future__ import unicode_literals
from django.apps import AppConfig


class CeleryMonitoringAppConfig(AppConfig):
    name = 'corehq.celery_monitoring'

    def ready(self):
        # Make sure hooks get registered
        from . import signals  # noqa
