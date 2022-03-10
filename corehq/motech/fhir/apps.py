from django.apps import AppConfig


class FHIRAppConfig(AppConfig):
    name = 'corehq.motech.fhir'

    def ready(self):
        from . import signals  # noqa # pylint: disable=unused-import
        from . import serializers  # noqa # pylint: disable=unused-import
