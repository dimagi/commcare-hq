from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.elastic import es_index
from corehq.pillows.mappings.utils import mapping_from_json
from pillowtop.es_utils import ElasticsearchIndexInfo

APP_INDEX = es_index("hqapps_2019-01-23")
APP_MAPPING = mapping_from_json('app_mapping.json')
APP_ES_ALIAS = "hqapps"
APP_ES_TYPE = "app"

APP_INDEX_INFO = ElasticsearchIndexInfo(
    index=APP_INDEX,
    alias=APP_ES_ALIAS,
    type=APP_ES_TYPE,
    mapping=APP_MAPPING
)
