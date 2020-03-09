from django.apps import AppConfig
from django.conf import settings


class DatadogConfig(AppConfig):

    name = 'corehq.util.datadog'
    verbose_name = 'Datadog'

    def ready(self):
        if not settings.DATADOG_API_KEY or not settings.DATADOG_APP_KEY:
            return

        try:
            from datadog import initialize
        except ImportError:
            pass
        else:
            initialize(settings.DATADOG_API_KEY, settings.DATADOG_APP_KEY)

        if settings.UNIT_TESTING or settings.DEBUG or 'ddtrace.contrib.django' not in settings.INSTALLED_APPS:
            try:
                from ddtrace import tracer
                tracer.enabled = False
            except ImportError:
                pass

