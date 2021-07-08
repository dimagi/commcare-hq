from django.apps import AppConfig


class COWINAppConfig(AppConfig):
    name = 'custom.cowin'

    def ready(self):
        from . import signals  # noqa


default_app_config = 'custom.cowin.COWINAppConfig'
