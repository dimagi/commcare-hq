import json
import os
from corehq.pillows.base import DEFAULT_META

from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.pillows.mappings.case_mapping import CASE_ES_TYPE
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo


CASE_SEARCH_INDEX = es_index("case_search_2016-03-15")
CASE_SEARCH_ALIAS = "case_search"
CASE_SEARCH_MAX_RESULTS = 10


def _CASE_SEARCH_MAPPING():
    with open(os.path.join(os.path.dirname(__file__), 'case_search_mapping.json')) as f:
        data = (f.read()
                .replace('"__DATE_FORMATS_STRING__"', json.dumps(DATE_FORMATS_STRING))
                .replace('"__DATE_FORMATS_ARR__"', json.dumps(DATE_FORMATS_ARR)))
        mapping = json.loads(data)
    return mapping

CASE_SEARCH_MAPPING = _CASE_SEARCH_MAPPING()


CASE_SEARCH_INDEX_INFO = ElasticsearchIndexInfo(
    index=CASE_SEARCH_INDEX,
    alias=CASE_SEARCH_ALIAS,
    type=CASE_ES_TYPE,
    meta=DEFAULT_META,
    mapping=CASE_SEARCH_MAPPING,
)
