from django.conf import settings
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.pillows.mappings.case_mapping import CASE_ES_TYPE
from corehq.util.elastic import prefix_for_tests
from pillowtop.es_utils import ElasticsearchIndexInfo, CASE_SEARCH_HQ_INDEX_NAME


CASE_SEARCH_INDEX = prefix_for_tests(settings.ES_CASE_SEARCH_INDEX_NAME)
CASE_SEARCH_ALIAS = prefix_for_tests('case_search')

CASE_SEARCH_MAPPING = {
    "_all": {
        "enabled": False
    },
    "_meta": {
        "comment": "",
        "created": "2016-03-29 @frener"
    },
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,
    "dynamic": False,
    "properties": {
        "@indexed_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "case_properties": {
            "dynamic": False,
            "type": "nested",
            "properties": {
                "key": {
                    "fields": {
                        "exact": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    },
                    "type": "string"
                },
                "value": {
                    "fields": {
                        "date": {
                            "format": DATE_FORMATS_STRING,
                            "ignore_malformed": True,
                            "type": "date"
                        },
                        "exact": {
                            "ignore_above": 8191,
                            "index": "not_analyzed",
                            "null_value": "",
                            "type": "string"
                        },
                        "numeric": {
                            "ignore_malformed": True,
                            "type": "double"
                        }
                    },
                    "null_value": "",
                    "type": "string"
                }
            }
        },
        "closed": {
            "type": "boolean"
        },
        "closed_by": {
            "index": "not_analyzed",
            "type": "string"
        },
        "closed_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "doc_type": {
            "index": "not_analyzed",
            "type": "string"
        },
        "domain": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "multi_field"
        },
        "external_id": {
            "index": "not_analyzed",
            "type": "string"
        },
        "indices": {
            "dynamic": False,
            "type": "nested",
            "properties": {
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "identifier": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "referenced_id": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "referenced_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "relationship": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            }
        },
        "location_id": {
            "index": "not_analyzed",
            "type": "string"
        },
        "modified_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "name": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "opened_by": {
            "index": "not_analyzed",
            "type": "string"
        },
        "opened_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "owner_id": {
            "index": "not_analyzed",
            "type": "string"
        },
        "server_modified_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "type": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "type": {
                    "index": "analyzed",
                    "type": "string"
                }
            },
            "type": "multi_field"
        },
        "user_id": {
            "index": "not_analyzed",
            "type": "string"
        }
    }
}


CASE_SEARCH_INDEX_INFO = ElasticsearchIndexInfo(
    index=CASE_SEARCH_INDEX,
    alias=CASE_SEARCH_ALIAS,
    type=CASE_ES_TYPE,
    mapping=CASE_SEARCH_MAPPING,
    hq_index_name=CASE_SEARCH_HQ_INDEX_NAME,
)
