from django.apps import AppConfig


class RegistryAppConfig(AppConfig):
    name = 'corehq.apps.registry'

    def ready(self):
        # Make sure hooks get registered
        from . import signals  # noqa
