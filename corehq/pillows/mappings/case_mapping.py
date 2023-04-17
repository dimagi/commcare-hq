from pillowtop.es_utils import CASE_HQ_INDEX_NAME, ElasticsearchIndexInfo

from corehq.apps.es.case_search import case_adapter
from corehq.apps.es.client import Tombstone
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.pillows.mappings.const import NULL_VALUE
from corehq.util.elastic import prefix_for_tests

CASE_INDEX = case_adapter.index_name
CASE_ES_TYPE = case_adapter.type
CASE_ES_ALIAS = prefix_for_tests("hqcases")

CASE_MAPPING = {
    "_meta": {
        "comment": "",
        "created": "2013-09-19 @dmyung"
    },
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,
    "dynamic": False,
    "properties": {
        "actions": {
            "dynamic": False,
            "type": "nested",
            "properties": {
                "action_type": {
                    "type": "text"
                },
                "date": {
                    "format": DATE_FORMATS_STRING,
                    "type": "date"
                },
                "doc_type": {
                    "type": "keyword"
                },
                "indices": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "doc_type": {
                            "type": "keyword"
                        },
                        "identifier": {
                            "type": "text"
                        },
                        "referenced_id": {
                            "type": "text"
                        },
                        "referenced_type": {
                            "type": "text"
                        }
                    }
                },
                "server_date": {
                    "format": DATE_FORMATS_STRING,
                    "type": "date"
                },
                "sync_log_id": {
                    "type": "text"
                },
                "user_id": {
                    "type": "text"
                },
                "xform_id": {
                    "type": "text"
                },
                "xform_name": {
                    "type": "text"
                },
                "xform_xmlns": {
                    "type": "text"
                }
            }
        },
        "backend_id": {
            "type": "keyword"
        },
        "closed": {
            "type": "boolean"
        },
        "closed_by": {
            "type": "keyword"
        },
        "closed_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "computed_": {
            "enabled": False,
            "type": "object"
        },
        "computed_modified_on_": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "contact_phone_number": {
            "type": "keyword"
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
        "export_tag": {
            "type": "text"
        },
        "external_id": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        "indices": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "doc_type": {
                    "type": "keyword"
                },
                "identifier": {
                    "type": "text"
                },
                "referenced_id": {
                    "type": "text"
                },
                "referenced_type": {
                    "type": "text"
                }
            }
        },
        "initial_processing_complete": {
            "type": "boolean"
        },
        "inserted_at": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "location_id": {
            "type": "text"
        },
        "modified_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "name": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        "opened_by": {
            "type": "keyword"
        },
        "opened_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "owner_id": {
            "type": "keyword"
        },
        "owner_type": {
            "null_value": NULL_VALUE,
            "type": "keyword"
        },
        "referrals": {
            "enabled": False,
            "type": "object"
        },
        "server_modified_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "type": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        "user_id": {
            "type": "text"
        },
        "version": {
            "type": "text"
        },
        "xform_ids": {
            "type": "keyword"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}

CASE_INDEX_INFO = ElasticsearchIndexInfo(
    index=CASE_INDEX,
    alias=CASE_ES_ALIAS,
    type=CASE_ES_TYPE,
    mapping=CASE_MAPPING,
    hq_index_name=CASE_HQ_INDEX_NAME
)
