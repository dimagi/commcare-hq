from django.apps import AppConfig


class COWINAppConfig(AppConfig):
    name = 'corehq.apps.cowin'

    def ready(self):
        from . import signals  # noqa


default_app_config = 'corehq.apps.cowin.COWINAppConfig'
