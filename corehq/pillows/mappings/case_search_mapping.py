from django.conf import settings
from corehq.pillows.mappings.case_mapping import CASE_ES_TYPE
from corehq.pillows.mappings.utils import mapping_from_json
from corehq.util.elastic import prefix_for_tests
from pillowtop.es_utils import ElasticsearchIndexInfo, CASE_SEARCH_HQ_INDEX_NAME


CASE_SEARCH_INDEX = prefix_for_tests(settings.ES_CASE_SEARCH_INDEX_NAME)
CASE_SEARCH_ALIAS = prefix_for_tests('case_search')
CASE_SEARCH_MAPPING = mapping_from_json('case_search_mapping.json')


CASE_SEARCH_INDEX_INFO = ElasticsearchIndexInfo(
    index=CASE_SEARCH_INDEX,
    alias=CASE_SEARCH_ALIAS,
    type=CASE_ES_TYPE,
    mapping=CASE_SEARCH_MAPPING,
    hq_index_name=CASE_SEARCH_HQ_INDEX_NAME,
)
