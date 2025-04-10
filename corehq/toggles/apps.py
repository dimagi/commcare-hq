from django.apps import AppConfig


class TogglesAppConfig(AppConfig):
    name = 'corehq.toggles'

    def ready(self):
        from .sql_models import ToggleEditPermission   # noqa
