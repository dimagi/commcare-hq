from django.apps import AppConfig


class PillowsAppConfig(AppConfig):
    name = 'corehq.pillows'

    def ready(self):
        from corehq.apps.es.registry import register
        from .mappings import CANONICAL_NAME_INFO_MAP
        for cname, info in CANONICAL_NAME_INFO_MAP.items():
            register(info, cname)
