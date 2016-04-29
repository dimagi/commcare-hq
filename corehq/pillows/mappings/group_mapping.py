from corehq.pillows.base import DEFAULT_META
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo

GROUP_INDEX = es_index("hqgroups_20150403_1501")
GROUP_MAPPING = {
    "date_formats": [
        "yyyy-MM-dd",
        "yyyy-MM-dd'T'HH:mm:ssZZ",
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'",
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        "yyyy-MM-dd'T'HH:mm:ssZ",
        "yyyy-MM-dd'T'HH:mm:ssZZ'Z'",
        "yyyy-MM-dd'T'HH:mm:ss.SSSZZ",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd' 'HH:mm:ss",
        "yyyy-MM-dd' 'HH:mm:ss.SSSSSS",
        "mm/dd/yy' 'HH:mm:ss"
    ],
    "dynamic": False,
    "_meta": {
        "comment": "Ethan updated on 2014-04-02",
        "created": None
    },
    "date_detection": False,
    "properties": {
        "doc_type": {
            "index": "not_analyzed",
            "type": "string"
        },
        "domain": {
            "fields": {
                "domain": {
                    "index": "analyzed",
                    "type": "string"
                },
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "multi_field"
        },
        "name": {
            "fields": {
                "exact": {
                    "index": "analyzed",
                    "type": "string",
                    "analyzer": "sortable_exact"
                },
                "name": {
                    "index": "analyzed",
                    "type": "string"
                }
            },
            "type": "multi_field"
        },
        "reporting": {"type": "boolean"},
        "path": {"type": "string"},
        "case_sharing": {"type": "boolean"},
        "users": {"type": "string"},
    }
}


GROUP_INDEX_INFO = ElasticsearchIndexInfo(
    index=GROUP_INDEX,
    alias='hqgroups',
    type='group',
    meta=DEFAULT_META,
    mapping=GROUP_MAPPING,
)
