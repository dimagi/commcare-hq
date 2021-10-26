from django.apps import AppConfig


class RepeaterAppConfig(AppConfig):
    name = 'corehq.motech.repeaters'

    def ready(self):
        from . import signals  # noqa: disable=unused-import,F401
