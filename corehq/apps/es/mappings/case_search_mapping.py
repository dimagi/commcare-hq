from corehq.apps.case_search.const import (
    CASE_PROPERTIES_PATH,
    GEOPOINT_VALUE,
    IDENTIFIER,
    INDEXED_ON,
    INDICES_PATH,
    REFERENCED_ID,
    VALUE,
)
from corehq.apps.es.client import Tombstone
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING

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
        INDEXED_ON: {
            "format": DATE_FORMATS_STRING,
            "type": "date"
        },
        CASE_PROPERTIES_PATH: {
            "dynamic": False,
            "type": "nested",
            "properties": {
                "key": {
                    "fields": {
                        "exact": {
                            "type": "keyword"
                        }
                    },
                    "type": "text"
                },
                VALUE: {
                    "fields": {
                        "date": {
                            "format": DATE_FORMATS_STRING,
                            "ignore_malformed": True,
                            "type": "date"
                        },
                        "exact": {
                            "ignore_above": 8191,
                            "null_value": "",
                            "type": "keyword"
                        },
                        "numeric": {
                            "ignore_malformed": True,
                            "type": "double"
                        },
                        "phonetic": {
                            "analyzer": "phonetic",
                            "type": "text"
                        }
                    },
                    "type": "text"
                },
                GEOPOINT_VALUE: {
                    "type": "geo_point"
                }
            }
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
        "external_id": {
            "type": "keyword"
        },
        INDICES_PATH: {
            "dynamic": False,
            "type": "nested",
            "properties": {
                "doc_type": {
                    "type": "keyword"
                },
                IDENTIFIER: {
                    "type": "keyword"
                },
                REFERENCED_ID: {
                    "type": "keyword"
                },
                "referenced_type": {
                    "type": "keyword"
                },
                "relationship": {
                    "type": "keyword"
                }
            }
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
        Tombstone.PROPERTY_NAME: {
            "type": "boolean"
        },
    }
}
