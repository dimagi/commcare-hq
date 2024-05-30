from corehq.apps.es.case_search import CaseSearchES, ElasticCaseSearch

from .cases import case_adapter
from .client import create_document_adapter
from .const import (
    HQ_CASE_SEARCH_INDEX_CANONICAL_NAME,
    HQ_CASE_SEARCH_BHA_INDEX_CANONICAL_NAME,
    HQ_CASE_SEARCH_BHA_INDEX_NAME,
    HQ_CASE_SEARCH_BHA_SECONDARY_INDEX_NAME,
)
from .index.settings import IndexSettingsKey


class CaseSearchBhaES(CaseSearchES):
    index = HQ_CASE_SEARCH_BHA_INDEX_CANONICAL_NAME


class ElasticCaseSearchBha(ElasticCaseSearch):

    settings_key = IndexSettingsKey.CASE_SEARCH_BHA
    canonical_name = HQ_CASE_SEARCH_BHA_INDEX_CANONICAL_NAME
    parent_index_cname = HQ_CASE_SEARCH_INDEX_CANONICAL_NAME

    def index(self, doc, refresh=False):
        """
        A ripoff of the `index` method in `ElasticDocumentAdapter`.
        This is necessary because `ElasticCaseSearch` index is overridden
        to index into both bha case search and the standard case search index.
        """
        doc_id, source = self.from_python(doc)
        self._verify_doc_id(doc_id)
        self._verify_doc_source(source)
        self._index(doc_id, source, refresh)


case_search_bha_adapter = create_document_adapter(
    ElasticCaseSearchBha,
    HQ_CASE_SEARCH_BHA_INDEX_NAME,
    case_adapter.type,
    secondary=HQ_CASE_SEARCH_BHA_SECONDARY_INDEX_NAME,
)
