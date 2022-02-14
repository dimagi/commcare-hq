"""Transient utilities needed during the interim of converting HQ Elastic logic
to use the new "client adapter" models."""

from .client import ElasticDocumentAdapter
from .registry import get_registry


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


def _populate_doc_adapter_map(is_test):
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
        assert DocAdapter.index not in _DOC_ADAPTERS_BY_INDEX, \
            (DocAdapter.index, _DOC_ADAPTERS_BY_INDEX)
        _DOC_ADAPTERS_BY_INDEX[DocAdapter.index] = DocAdapter
    # by alias
    for index_info in get_registry().values():
        _DOC_ADAPTERS_BY_ALIAS[index_info.alias] = _DOC_ADAPTERS_BY_INDEX[index_info.index]

    if is_test:
        # for pillowtop tests
        _add_ptop_test_adapter()


def _add_ptop_test_adapter():
    from pillowtop.tests.utils import TEST_ES_ALIAS, TEST_ES_INDEX, TEST_ES_TYPE

    class PillowTopTest(ElasticDocumentAdapter):
        index = TEST_ES_INDEX
        type = TEST_ES_TYPE

    _DOC_ADAPTERS_BY_INDEX[PillowTopTest.index] = PillowTopTest
    _DOC_ADAPTERS_BY_ALIAS[TEST_ES_ALIAS] = PillowTopTest


_DOC_ADAPTERS_BY_INDEX = {}
_DOC_ADAPTERS_BY_ALIAS = {}
