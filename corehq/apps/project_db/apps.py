from django.apps import AppConfig


class ProjectDBAppConfig(AppConfig):
    name = 'corehq.apps.project_db'

    def ready(self):
        from . import signals  # noqa: F401
