from corehq.apps.es.client import Tombstone
from corehq.pillows.core import DATE_FORMATS_ARR

GROUP_MAPPING = {
    "_meta": {
        "comment": "Ethan updated on 2014-04-02",
        "created": None
    },
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,
    "dynamic": False,
    "properties": {
        "case_sharing": {
            "type": "boolean"
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
        "name": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "string"
        },
        "path": {
            "type": "string"
        },
        "removed_users": {
            "type": "string"
        },
        "reporting": {
            "type": "boolean"
        },
        "users": {
            "type": "string"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}
