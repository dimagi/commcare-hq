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
                    "type": "keyword"
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
                            "type": "keyword"
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
                    "type": "keyword"
                },
                "user_id": {
                    "type": "keyword"
                },
                "xform_id": {
                    "type": "keyword"
                },
                "xform_name": {
                    "type": "text"
                },
                "xform_xmlns": {
                    "type": "keyword"
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
        "doc_id": {
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
            "type": "keyword"
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
                    "type": "keyword"
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
            "type": "keyword"
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
            "type": "keyword"
        },
        "version": {
            "type": "keyword"
        },
        "xform_ids": {
            "type": "keyword"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}
