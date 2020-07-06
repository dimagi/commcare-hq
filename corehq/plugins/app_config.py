from django.apps import AppConfig


class PluginAppConfig(AppConfig):
    name = 'corehq.plugins'

    def ready(self):
        from corehq.plugins import extension_points  # noqa
