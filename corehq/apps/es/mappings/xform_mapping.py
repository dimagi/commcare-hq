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
            "index": "not_analyzed",
            "type": "string"
        },
        "@uiVersion": {
            "type": "string"
        },
        "@version": {
            "type": "string"
        },
        "__retrieved_case_ids": {
            "index": "not_analyzed",
            "type": "string"
        },
        "_attachments": {
            "dynamic": False,
            "type": "object"
        },
        "app_id": {
            "index": "not_analyzed",
            "type": "string"
        },
        "backend_id": {
            "index": "not_analyzed",
            "type": "string"
        },
        "build_id": {
            "index": "not_analyzed",
            "type": "string"
        },
        "doc_type": {
            "type": "string"
        },
        "domain": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "external_blobs": {
            "dynamic": False,
            "type": "object"
        },
        "form": {
            "dynamic": False,
            "properties": {
                "#type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "@name": {
                    "index": "not_analyzed",
                    "type": "string"
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
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "@date_modified": {
                            "format": XFORM_DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "@user_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "@xmlns": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "case_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "date_modified": {
                            "format": XFORM_DATE_FORMATS_STRING,
                            "type": "date"
                        },
                        "user_id": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "xmlns": {
                            "index": "not_analyzed",
                            "type": "string"
                        }
                    }
                },
                "meta": {
                    "dynamic": False,
                    "properties": {
                        "appVersion": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "app_build_version": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "commcare_version": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "deviceID": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "geo_point": {
                            "geohash": True,
                            "geohash_precision": "10m",
                            "geohash_prefix": True,
                            "lat_lon": True,
                            "type": "geo_point"
                        },
                        "instanceID": {
                            "index": "not_analyzed",
                            "type": "string"
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
                            "index": "not_analyzed",
                            "null_value": NULL_VALUE,
                            "type": "string"
                        },
                        "username": {
                            "index": "not_analyzed",
                            "type": "string"
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
            "index": "not_analyzed",
            "type": "string"
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
            "index": "not_analyzed",
            "null_value": NULL_VALUE,
            "type": "string"
        },
        "xmlns": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}
