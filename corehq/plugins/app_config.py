from django.apps import AppConfig
from django.conf import settings


class PluginAppConfig(AppConfig):
    name = 'corehq.plugins'

    def ready(self):
        from corehq.plugins import extension_points, plugin_manager  # noqa
        plugin_manager.load_plugins(settings.COMMCARE_PLUGINS)
