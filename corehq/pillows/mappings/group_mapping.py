from pillowtop.es_utils import GROUP_HQ_INDEX_NAME, ElasticsearchIndexInfo

from corehq.apps.es.client import Tombstone
from corehq.apps.es.groups import group_adapter
from corehq.pillows.core import DATE_FORMATS_ARR
from corehq.util.elastic import prefix_for_tests

GROUP_INDEX = group_adapter.index_name
GROUP_ES_ALIAS = prefix_for_tests('hqgroups')
GROUP_MAPPING = {
    "_meta": {
        "comment": "Ethan updated on 2014-04-02",
        "created": None
    },
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,
    "dynamic": False,
    "properties": {
        "case_sharing": {
            "type": "boolean"
        },
        "doc_type": {
            "type": "keyword"
        },
        "domain": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        "name": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        "path": {
            "type": "text"
        },
        "removed_users": {
            "type": "text"
        },
        "reporting": {
            "type": "boolean"
        },
        "users": {
            "type": "text"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}


GROUP_INDEX_INFO = ElasticsearchIndexInfo(
    index=GROUP_INDEX,
    alias=GROUP_ES_ALIAS,
    type=group_adapter.type,
    mapping=GROUP_MAPPING,
    hq_index_name=GROUP_HQ_INDEX_NAME
)
