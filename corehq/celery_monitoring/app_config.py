from django.apps import AppConfig


class CeleryMonitoringAppConfig(AppConfig):
    name = 'corehq.celery_monitoring'

    def ready(self):
        # Make sure hooks get registered
        from . import signals  # noqa
