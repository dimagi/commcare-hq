from django.apps import AppConfig


class FHIRAppConfig(AppConfig):
    name = 'corehq.motech.fhir'

    def ready(self):
        from . import signals  # noqa: F401
        from . import serializers  # noqa: F401
