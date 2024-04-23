from corehq.apps.es.client import Tombstone
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.apps.es.mappings.const import NULL_VALUE

XFORM_DATE_FORMATS_STRING = "epoch_millis||" + DATE_FORMATS_STRING

XFORM_MAPPING = {
    "_meta": {
        "created": "2013-08-13"
    },
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,
    "dynamic": False,
    "properties": {
        "#export_tag": {
            "type": "keyword"
        },
        "@uiVersion": {
            "type": "keyword"
        },
        "@version": {
            "type": "keyword"
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
        "doc_id": {
            "type": "keyword"
        },
        "doc_type": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        "domain": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
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
                            "format": XFORM_DATE_FORMATS_STRING,
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
                            "format": XFORM_DATE_FORMATS_STRING,
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
                            "format": XFORM_DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "timeStart": {
                            "format": XFORM_DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "userID": {
                            "type": "keyword",
                            "null_value": NULL_VALUE
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
            "format": XFORM_DATE_FORMATS_STRING,
            "type": "date"
        },
        "partial_submission": {
            "type": "boolean"
        },
        "path": {
            "type": "keyword"
        },
        "received_on": {
            "format": XFORM_DATE_FORMATS_STRING,
            "type": "date"
        },
        "server_modified_on": {
            "format": XFORM_DATE_FORMATS_STRING,
            "type": "date"
        },
        "submit_ip": {
            "type": "ip"
        },
        "user_type": {
            "type": "keyword",
            "null_value": NULL_VALUE
        },
        "xmlns": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}
