from corehq.util.elastic import prefix_for_tests
from corehq.pillows.mappings.utils import mapping_from_json
from pillowtop.es_utils import ElasticsearchIndexInfo, APP_HQ_INDEX_NAME

APP_INDEX = prefix_for_tests("hqapps_2020-02-26")
APP_MAPPING = mapping_from_json('app_mapping.json')
APP_ES_ALIAS = prefix_for_tests("hqapps")
APP_ES_TYPE = "app"

APP_INDEX_INFO = ElasticsearchIndexInfo(
    index=APP_INDEX,
    alias=APP_ES_ALIAS,
    type=APP_ES_TYPE,
    mapping=APP_MAPPING,
    hq_index_name=APP_HQ_INDEX_NAME
)
