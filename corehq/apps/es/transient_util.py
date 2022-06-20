"""Transient utilities needed during the interim of converting HQ Elastic logic
to use the new "client adapter" models.
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
    return _DOC_ADAPTERS_BY_INDEX[index_info.index](for_export=for_export)


def doc_adapter_from_alias(index_alias, for_export=False):
    """Return the document adapter for the provided ``index_alias``.

    :param index_alias: ``str`` name of a valid alias assigned to an index
    :param for_export: ``bool`` used to instantiate the adapter instance
    :returns: instance of an ``ElasticDocumentAdapter`` subclass
    """
    return _DOC_ADAPTERS_BY_ALIAS[index_alias](for_export=for_export)


def report_and_fail_on_shard_failures(search_result):
    ElasticDocumentAdapter._report_and_fail_on_shard_failures(search_result)


def populate_doc_adapter_map():
    """Populate "map" dictionaries needed to allow `ElasticsearchInterface`
    instances to acquire adapters by their index names/aliases.

    NOTE: this function is only meant to be used by the Django app's ``ready()``
    method. Do not call this function other places.
    """
    from django.conf import settings
    from .apps import ElasticApp
    from .case_search import ElasticCaseSearch
    from .cases import ElasticCase, ElasticReportCase
    from .domains import ElasticDomain
    from .forms import ElasticForm, ElasticReportForm
    from .groups import ElasticGroup
    from .sms import ElasticSMS
    from .users import ElasticUser

    # by index
    for DocAdapter in [ElasticApp, ElasticCaseSearch, ElasticCase,
                       ElasticReportCase, ElasticDomain, ElasticForm,
                       ElasticReportForm, ElasticGroup, ElasticSMS,
                       ElasticUser]:
        assert DocAdapter.index_name not in _DOC_ADAPTERS_BY_INDEX, \
            (DocAdapter.index_name, _DOC_ADAPTERS_BY_INDEX)
        _DOC_ADAPTERS_BY_INDEX[DocAdapter.index_name] = DocAdapter
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
        index_name = index_  # override the classproperty
        type = type_
        mapping = mapping_

        @classmethod
        def from_python(cls, doc):
            return from_dict_with_possible_id(doc)

    Adapter.__name__ = f"{descriptor}Test"
    _DOC_ADAPTERS_BY_INDEX[index_] = Adapter
    _DOC_ADAPTERS_BY_ALIAS[alias] = Adapter
    _DOC_MAPPINGS_BY_INDEX[index_] = mapping_


_DOC_ADAPTERS_BY_INDEX = {}
_DOC_ADAPTERS_BY_ALIAS = {}
_DOC_MAPPINGS_BY_INDEX = {}
