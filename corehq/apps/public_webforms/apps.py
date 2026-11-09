from django.apps import AppConfig


class PublicWebformsAppConfig(AppConfig):
    name = 'corehq.apps.public_webforms'

    def ready(self):
        from . import signals  # noqa: F401
