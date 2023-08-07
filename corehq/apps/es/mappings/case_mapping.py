from corehq.apps.es.client import Tombstone
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.apps.es.mappings.const import NULL_VALUE

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
                    "type": "string"
                },
                "date": {
                    "format": DATE_FORMATS_STRING,
                    "type": "date"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "indices": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "identifier": {
                            "type": "string"
                        },
                        "referenced_id": {
                            "type": "string"
                        },
                        "referenced_type": {
                            "type": "string"
                        }
                    }
                },
                "server_date": {
                    "format": DATE_FORMATS_STRING,
                    "type": "date"
                },
                "sync_log_id": {
                    "type": "string"
                },
                "user_id": {
                    "type": "string"
                },
                "xform_id": {
                    "type": "string"
                },
                "xform_name": {
                    "type": "string"
                },
                "xform_xmlns": {
                    "type": "string"
                }
            }
        },
        "backend_id": {
            "index": "not_analyzed",
            "type": "string"
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
        "computed_": {
            "enabled": False,
            "type": "object"
        },
        "computed_modified_on_": {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        "contact_phone_number": {
            "index": "not_analyzed",
            "type": "string"
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
            "type": "string"
        },
        "export_tag": {
            "type": "string"
        },
        "external_id": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "indices": {
            "dynamic": False,
            "type": "object",
            "properties": {
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "identifier": {
                    "type": "string"
                },
                "referenced_id": {
                    "type": "string"
                },
                "referenced_type": {
                    "type": "string"
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
        "owner_type": {
            "index": "not_analyzed",
            "null_value": NULL_VALUE,
            "type": "string"
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
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "user_id": {
            "type": "string"
        },
        "version": {
            "type": "string"
        },
        "xform_ids": {
            "index": "not_analyzed",
            "type": "string"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}
