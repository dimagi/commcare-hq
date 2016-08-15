from django.apps import AppConfig


class ZapierConfig(AppConfig):

    name = 'corehq.apps.zapier'
    verbose_name = 'Zapier'

    def ready(self):
        from .signals import receivers  # noqa
