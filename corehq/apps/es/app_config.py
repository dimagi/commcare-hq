from django.apps import AppConfig
from django.conf import settings


class ElasticAppConfig(AppConfig):

    name = 'corehq.apps.es'

    def ready(self):
        from .transient_util import _populate_doc_adapter_map
        _populate_doc_adapter_map(is_test=settings.UNIT_TESTING)
