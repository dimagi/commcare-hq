from django.apps import AppConfig


class HqAdminModule(AppConfig):
    name = 'corehq.apps.hqadmin'

    def ready(self):
        from corehq.apps.hqadmin import signals  # noqa
