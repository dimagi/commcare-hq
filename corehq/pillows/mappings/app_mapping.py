from corehq.apps.es.apps import ElasticApp
from corehq.util.elastic import prefix_for_tests
from corehq.pillows.mappings.utils import mapping_from_json
from pillowtop.es_utils import ElasticsearchIndexInfo, APP_HQ_INDEX_NAME

APP_INDEX = ElasticApp.index_name
APP_ES_TYPE = ElasticApp.type
APP_ES_ALIAS = prefix_for_tests("hqapps")
APP_MAPPING = mapping_from_json('app_mapping.json')

APP_INDEX_INFO = ElasticsearchIndexInfo(
    index=APP_INDEX,
    alias=APP_ES_ALIAS,
    type=APP_ES_TYPE,
    mapping=APP_MAPPING,
    hq_index_name=APP_HQ_INDEX_NAME
)
