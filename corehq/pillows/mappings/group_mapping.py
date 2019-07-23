from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo

GROUP_INDEX = es_index("hqgroups_2017-05-29")
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
            "type": "keyword"
        },
        "domain": {
            "type": "text",
            "fields": {
                "domain": {
                    "type": "text"
                },
                "exact": {
                    "type": "keyword"
                }
            },
        },
        "name": {
            "type": "text",
            "fields": {
                "exact": {
                    "type": "text",
                    "analyzer": "sortable_exact"
                },
                "name": {
                    "type": "text"
                }
            },
        },
        "reporting": {"type": "boolean"},
        "path": {"type": "text"},
        "case_sharing": {"type": "boolean"},
        "users": {"type": "text"},
        "removed_users": {"type": "text"},
    }
}


GROUP_INDEX_INFO = ElasticsearchIndexInfo(
    index=GROUP_INDEX,
    alias='hqgroups',
    type='group',
    mapping=GROUP_MAPPING,
)
