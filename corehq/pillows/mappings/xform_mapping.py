from pillowtop.es_utils import XFORM_HQ_INDEX_NAME, ElasticsearchIndexInfo

from corehq.apps.es.client import Tombstone
from corehq.apps.es.forms import form_adapter
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.pillows.mappings.const import NULL_VALUE
from corehq.util.elastic import prefix_for_tests

XFORM_INDEX = form_adapter.index_name
XFORM_ES_TYPE = form_adapter.type
XFORM_ALIAS = prefix_for_tests("xforms")

XFORM_MAPPING = {
    "_meta": {
        "created": "2013-08-13"
    },
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,  # for parsing the explicitly defined dates
    "dynamic": False,
    "properties": {
        "#export_tag": {
            "type": "keyword"
        },
        "@uiVersion": {
            "type": "text"
        },
        "@version": {
            "type": "text"
        },
        "__retrieved_case_ids": {
            "type": "keyword"
        },
        "_attachments": {
            "dynamic": False,
            "type": "object"
        },
        "app_id": {
            "type": "keyword"
        },
        "backend_id": {
            "type": "keyword"
        },
        "build_id": {
            "type": "keyword"
        },
        "doc_type": {
            "type": "text"
        },
        "domain": {
            "fields": {
                "domain": {
                    "type": "text"
                },
                "exact": {
                    # exact is full text string match - hyphens get parsed in standard
                    # analyzer
                    # in queries you can access by domain.exact
                    "type": "keyword"
                }
            },
            "type": "multi_field"
        },
        "external_blobs": {
            "dynamic": False,
            "type": "object"
        },
        "form": {
            "dynamic": False,
            "properties": {
                "#type": {
                    "type": "keyword"
                },
                "@name": {
                    "type": "keyword"
                },
                "case": {
                    "dynamic": False,
                    "properties": {
                        # Note, the case_id method here assumes single case
                        # properties within a form.
                        # In order to support multi case properties, a dynamic
                        # template needs to be added along with fundamentally
                        # altering case queries
                        "@case_id": {
                            "type": "keyword"
                        },
                        "@date_modified": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "@user_id": {
                            "type": "keyword"
                        },
                        "@xmlns": {
                            "type": "keyword"
                        },
                        "case_id": {
                            "type": "keyword"
                        },
                        "date_modified": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "user_id": {
                            "type": "keyword"
                        },
                        "xmlns": {
                            "type": "keyword"
                        }
                    }
                },
                "meta": {
                    "dynamic": False,
                    "properties": {
                        "appVersion": {
                            "type": "keyword"
                        },
                        "app_build_version": {
                            "type": "keyword"
                        },
                        "commcare_version": {
                            "type": "keyword"
                        },
                        "deviceID": {
                            "type": "keyword"
                        },
                        "geo_point": {
                            "type": "geo_point"
                        },
                        "instanceID": {
                            "type": "keyword"
                        },
                        "timeEnd": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "timeStart": {
                            "format": DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "userID": {
                            "null_value": NULL_VALUE,
                            "type": "keyword"
                        },
                        "username": {
                            "type": "keyword"
                        }
                    }
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
        "partial_submission": {
            "type": "boolean"
        },
        "path": {
            "type": "keyword"
        },
        "received_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "server_modified_on": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "submit_ip": {
            "type": "ip"
        },
        "user_type": {
            "null_value": NULL_VALUE,
            "type": "keyword"
        },
        "xmlns": {
            "fields": {
                "exact": {
                    "type": "keyword"
                },
                "xmlns": {
                    "type": "text"
                }
            },
            "type": "multi_field"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}

XFORM_INDEX_INFO = ElasticsearchIndexInfo(
    index=XFORM_INDEX,
    alias=XFORM_ALIAS,
    type=XFORM_ES_TYPE,
    mapping=XFORM_MAPPING,
    hq_index_name=XFORM_HQ_INDEX_NAME,
)
