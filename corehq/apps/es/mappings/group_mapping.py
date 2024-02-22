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
        "name": {
            "fields": {
                "exact": {
                    "type": "keyword"
                }
            },
            "type": "text"
        },
        "path": {
            "type": "text"
        },
        "removed_users": {
            "type": "text"
        },
        "reporting": {
            "type": "boolean"
        },
        "users": {
            "type": "text"
        },
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        }
    }
}
