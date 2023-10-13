"""Transient utilities needed during the interim of converting HQ Elastic logic
to use the new "client adapter" models.

This module includes tools needed to route the legacy ElasticsearchInterface
logic (corehq.util.es.*) through the new document adapters (corehq.apps.es.*),
and will be completely removed when the code that uses the old "interface" is
refactored to use the new "adapters".
"""

from .client import ElasticDocumentAdapter


def from_dict_with_possible_id(doc):
    """Temporary "common" function for adapters who don't yet own their document
    ``from_python()`` logic.
    """
    if "_id" in doc:
        return doc["_id"], {k: doc[k] for k in doc if k != "_id"}
    return None, doc


def doc_adapter_from_cname(index_cname, for_export=False):
    """Return the document adapter for the provided ``index_cname``.

    :param index_cname: ``str`` canonical name of the index
    :param for_export: ``bool`` used to instantiate the adapter instance
    :returns: instance of an ``ElasticDocumentAdapter`` subclass
    """
    from corehq.apps.es import CANONICAL_NAME_ADAPTER_MAP
    return _get_doc_adapter(CANONICAL_NAME_ADAPTER_MAP[index_cname], for_export)


def doc_adapter_from_index_name(index_name, for_export=False):
    """Return the document adapter for the provided ``index_name``.

    :param index_name: ``str`` name of the index
    :param for_export: ``bool`` used to instantiate the adapter instance
    :returns: instance of an ``ElasticDocumentAdapter`` subclass
    """
    return _get_doc_adapter(_DOC_ADAPTERS_BY_INDEX[index_name], for_export)


def _get_doc_adapter(adapter, for_export):
    """Helper function to keep things DRY. Returns an adapter instance that is
    configured for export (or not).
    """
    return adapter.export_adapter() if for_export else adapter


def iter_doc_adapters():
    from corehq.apps.es import CANONICAL_NAME_ADAPTER_MAP
    yield from CANONICAL_NAME_ADAPTER_MAP.values()


def iter_index_cnames():
    from corehq.apps.es import CANONICAL_NAME_ADAPTER_MAP
    yield from CANONICAL_NAME_ADAPTER_MAP


def populate_doc_adapter_map():
    """Populate "map" dictionaries needed to allow `ElasticsearchInterface`
    instances to acquire adapters by their index names/aliases.

    NOTE: this function is only meant to be used by the Django app's ``ready()``
    method. Do not call this function other places.
    """
    from django.conf import settings
    from .apps import app_adapter
    from .case_search import case_search_adapter
    from .cases import case_adapter
    from .domains import domain_adapter
    from .forms import form_adapter
    from .groups import group_adapter
    from .sms import sms_adapter
    from .users import user_adapter

    # by index
    for doc_adapter in [app_adapter, case_search_adapter, case_adapter,
                       domain_adapter, form_adapter, group_adapter, sms_adapter,
                       user_adapter]:
        assert doc_adapter.index_name not in _DOC_ADAPTERS_BY_INDEX, \
            (doc_adapter.index_name, _DOC_ADAPTERS_BY_INDEX)
        _DOC_ADAPTERS_BY_INDEX[doc_adapter.index_name] = doc_adapter
        mapping_key = (doc_adapter.index_name, doc_adapter.type)
        _DOC_MAPPINGS_BY_INDEX[mapping_key] = doc_adapter.mapping

    if settings.UNIT_TESTING:
        from pillowtop.tests.utils import TEST_ES_TYPE, TEST_ES_MAPPING, TEST_ES_INDEX
        add_dynamic_adapter("PillowTop", TEST_ES_INDEX, TEST_ES_TYPE, TEST_ES_MAPPING)

        from corehq.apps.es.tests.utils import TEST_ES_INFO, TEST_ES_MAPPING
        add_dynamic_adapter("UtilES", TEST_ES_INFO.alias, TEST_ES_INFO.type,
                        TEST_ES_MAPPING)


def add_dynamic_adapter(descriptor, index_, type_, mapping_):

    class Adapter(ElasticDocumentAdapter):
        mapping = mapping_

        @classmethod
        def from_python(cls, doc):
            return from_dict_with_possible_id(doc)

    Adapter.__name__ = f"{descriptor}Test"
    test_adapter = Adapter(index_, type_)
    _DOC_ADAPTERS_BY_INDEX[index_] = test_adapter
    _DOC_MAPPINGS_BY_INDEX[index_] = mapping_


_DOC_ADAPTERS_BY_INDEX = {}
_DOC_MAPPINGS_BY_INDEX = {}
