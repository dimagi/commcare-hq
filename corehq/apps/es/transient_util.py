"""Transient utilities needed during the interim of converting HQ Elastic logic
to use the new "client adapter" models.

This module includes tools needed to route the legacy ElasticsearchInterface
logic (corehq.util.es.*) through the new document adapters (corehq.apps.es.*),
and will be completely removed when the code that uses the old "interface" is
refactored to use the new "adapters".
"""

from .client import ElasticDocumentAdapter
from .registry import get_registry


def get_adapter_mapping(adapter):
    """Temporary function for fetching the Elastic mapping (still defined in
    pillowtop module) for an adapter.
    """
    return _DOC_MAPPINGS_BY_INDEX[(adapter.index_name, adapter.type)]


def from_dict_with_possible_id(doc):
    """Temporary "common" function for adapters who don't yet own their document
    ``from_python()`` logic.
    """
    if "_id" in doc:
        return doc["_id"], {k: doc[k] for k in doc if k != "_id"}
    return None, doc


def doc_adapter_from_info(index_info, for_export=False):
    """Return the document adapter for the provided ``index_info`` object.

    :param index_info: instance of a pillowtop ``ElasticsearchIndexInfo`` object
    :param for_export: ``bool`` used to instantiate the adapter instance
    :returns: instance of an ``ElasticDocumentAdapter`` subclass
    """
    return _get_doc_adapter(_DOC_ADAPTERS_BY_INDEX[index_info.index], for_export)


def doc_adapter_from_alias(index_alias, for_export=False):
    """Return the document adapter for the provided ``index_alias``.

    :param index_alias: ``str`` name of a valid alias assigned to an index
    :param for_export: ``bool`` used to instantiate the adapter instance
    :returns: instance of an ``ElasticDocumentAdapter`` subclass
    """
    return _get_doc_adapter(_DOC_ADAPTERS_BY_ALIAS[index_alias], for_export)


def _get_doc_adapter(adapter, for_export):
    """Helper function to keep things DRY. Returns an adapter instance that is
    configured for export (or not).
    """
    if for_export:
        return adapter.export_adapter()
    return adapter


def report_and_fail_on_shard_failures(search_result):
    ElasticDocumentAdapter._report_and_fail_on_shard_failures(search_result)


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
    # aliases and mappings
    for index_info in get_registry().values():
        _DOC_ADAPTERS_BY_ALIAS[index_info.alias] = _DOC_ADAPTERS_BY_INDEX[index_info.index]
        mapping_key = (index_info.index, index_info.type)
        _DOC_MAPPINGS_BY_INDEX[mapping_key] = index_info.mapping

    if settings.UNIT_TESTING:
        from pillowtop.tests.utils import TEST_INDEX_INFO
        _add_test_adapter("PillowTop", TEST_INDEX_INFO.index,
                        TEST_INDEX_INFO.type, TEST_INDEX_INFO.mapping,
                        TEST_INDEX_INFO.alias)

        from corehq.apps.es.tests.utils import TEST_ES_INFO, TEST_ES_MAPPING
        _add_test_adapter("UtilES", TEST_ES_INFO.alias, TEST_ES_INFO.type,
                        TEST_ES_MAPPING, TEST_ES_INFO.alias)


def _add_test_adapter(descriptor, index_, type_, mapping_, alias):

    class Adapter(ElasticDocumentAdapter):
        mapping = mapping_

        @classmethod
        def from_python(cls, doc):
            return from_dict_with_possible_id(doc)

    Adapter.__name__ = f"{descriptor}Test"
    test_adapter = Adapter(index_, type_)
    _DOC_ADAPTERS_BY_INDEX[index_] = test_adapter
    _DOC_ADAPTERS_BY_ALIAS[alias] = test_adapter
    _DOC_MAPPINGS_BY_INDEX[index_] = mapping_


_DOC_ADAPTERS_BY_INDEX = {}
_DOC_ADAPTERS_BY_ALIAS = {}
_DOC_MAPPINGS_BY_INDEX = {}
