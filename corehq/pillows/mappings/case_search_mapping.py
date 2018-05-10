from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.pillows.mappings.case_mapping import CASE_ES_TYPE
from corehq.pillows.mappings.utils import mapping_from_json
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo


CASE_SEARCH_INDEX = es_index("case_search_2018-04-27")
CASE_SEARCH_ALIAS = "case_search"
CASE_SEARCH_MAX_RESULTS = 100
CASE_SEARCH_MAPPING = mapping_from_json('case_search_mapping.json')


CASE_SEARCH_INDEX_INFO = ElasticsearchIndexInfo(
    index=CASE_SEARCH_INDEX,
    alias=CASE_SEARCH_ALIAS,
    type=CASE_ES_TYPE,
    mapping=CASE_SEARCH_MAPPING,
)
