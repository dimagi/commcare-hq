from django.apps import AppConfig


class HqWebAppConfig(AppConfig):
    name = 'corehq.apps.hqwebapp'

    def ready(self):
        # Ensure the login signal handlers have been loaded
        from . import login_handlers, signals  # noqa
