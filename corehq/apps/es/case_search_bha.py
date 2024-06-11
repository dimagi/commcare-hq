"""
This code supports a clone of the case search index for a single project.

To support more performant case search queries, we write cases to both the main
case_search index and to this sub-index, when enabled for the case's domain.
Both indices should have identical sets of cases on that domain, as well as
identical mappings, so they can be used interchangeably.

Writes are controlled by settings.CASE_SEARCH_SUB_INDICES, which tells us which
domains to write to this index. This doesn't affect reads, so we can begin
writing to an index and do the backfill without affecting live usage.

Code reads from the new index when directed there by use of the CaseSearchBhaES
class, or by passing the proper index cname to CaseSearchES constructor. Case
search code uses a shared base queryset (QueryHelper.get_base_queryset) which
checks CaseSearchConfig.index_name to see whether to read from a dedicated
index. This is edited in the Django admin, which allows us to easily switch domains
to the dedicated index or back without a deploy.
"""
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
