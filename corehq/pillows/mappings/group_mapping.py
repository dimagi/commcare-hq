from corehq.util.elastic import prefix_for_tests
from pillowtop.es_utils import ElasticsearchIndexInfo, GROUP_HQ_INDEX_NAME

GROUP_INDEX = prefix_for_tests("hqgroups_2017-05-29")
GROUP_ES_ALIAS = prefix_for_tests('hqgroups')
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
                    "index": "not_analyzed",
                    "type": "string",
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
        "removed_users": {"type": "string"},
    }
}


GROUP_INDEX_INFO = ElasticsearchIndexInfo(
    index=GROUP_INDEX,
    alias=GROUP_ES_ALIAS,
    type='group',
    mapping=GROUP_MAPPING,
    hq_index_name=GROUP_HQ_INDEX_NAME
)
