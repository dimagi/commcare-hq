from django.apps import AppConfig

from corehq import plugins


class IcdsAppConfig(AppConfig):
    name = 'custom.icds'

    def ready(self):
        from custom.icds.commcare_plugin import CommCarePlugin
        plugins.register_plugin(CommCarePlugin())
