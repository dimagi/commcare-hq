from django.apps import AppConfig


class ElasticAppConfig(AppConfig):

    name = 'corehq.apps.es'

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.document_adapters = {}

    def ready(self):
        from .transient_util import populate_doc_adapter_map
        populate_doc_adapter_map()
        self.verify_indexes()

    def verify_indexes(self):
        for adapter in _adapters_at_startup:
            value = self.document_adapters.setdefault(adapter.index_name, adapter)
            if value is not adapter:
                raise RegistryError(
                    f"multiple document adapters registered for the same "
                    f"index: {value}, {adapter}"
                )
        # TODO: perform index verification


def register_document_adapter(adapter):
    _adapters_at_startup.append(adapter)


class RegistryError(Exception):
    pass


_adapters_at_startup = []
