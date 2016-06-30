from corehq.pillows.core import DATE_FORMATS_STRING, DATE_FORMATS_ARR
from corehq.util.elastic import es_index
REPORT_XFORM_INDEX = es_index("report_xforms_20150406_1136")

CASE_MAPPING_FRAGMENT = {
    'type': 'nested',
    'dynamic': False,
    'properties': {
        'date_modified': {
            "type": "date",
            "format": DATE_FORMATS_STRING
        },
        '@date_modified': {
            "type": "date",
            "format": DATE_FORMATS_STRING
        },
        'index': {
            'type': 'object',
            'dynamic': True
        },

        "@case_id": {"type": "string", "index": "not_analyzed"},
        "@user_id": {"type": "string", "index": "not_analyzed"},
        "@xmlns": {"type": "string", "index": "not_analyzed"},


        "case_id": {"type": "string", "index": "not_analyzed"},
        "user_id": {"type": "string", "index": "not_analyzed"},
        "xmlns": {"type": "string", "index": "not_analyzed"},

        "create": {
            'type': 'object',
            'dynamic': True,
            'properties:': {
                'case_type': {"type": "string", "index": "not_analyzed"},
                'owner_id': {"type": "string", "index": "not_analyzed"},
                'case_name': {"type": "string", "index": "not_analyzed"},
            }
        },

        "update": {
            'type': 'object',
            'dynamic': True,
            'properties:': {
                'case_type': {"type": "string", "index": "not_analyzed"},
                'owner_id': {"type": "string", "index": "not_analyzed"},
                'case_name': {"type": "string", "index": "not_analyzed"},
                'date_opened': {
                    "type": "date",
                    "format": DATE_FORMATS_STRING
                },

            },
        },
        "index": {
            'type': 'object',
            'dynamic': True
        },
        'attachment': {
            'type': 'object',
            'dynamic': False
        }
    }
}

REPORT_XFORM_MAPPING = {
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR, #for parsing the explicitly defined dates
    'dynamic': True,
    "_meta": {
        "created": '2014-10-07', #record keeping on the index.
    },
    "properties": {
        'doc_type': {'type': 'string'},
        "domain": {
            "type": "multi_field",
            "fields": {
                "domain": {"type": "string", "index": "analyzed"},
                "exact": {"type": "string", "index": "not_analyzed"}
                #exact is full text string match - hyphens get parsed in standard
                # analyzer
                # in queries you can access by domain.exact
            }
        },
        "xmlns": {
            "type": "multi_field",
            "fields": {
                "xmlns": {"type": "string", "index": "analyzed"},
                "exact": {"type": "string", "index": "not_analyzed"}
            }
        },
        '@uiVersion': {"type": "string"},
        '@version': {"type": "string"},
        "path": {"type": "string", "index": "not_analyzed"},
        "submit_ip": {"type": "ip"},
        "app_id": {"type": "string", "index": "not_analyzed"},
        "received_on": {
            "type": "date",
            "format": DATE_FORMATS_STRING
        },
        'initial_processing_complete': {"type": "boolean"},
        'partial_submission': {"type": "boolean"},
        "#export_tag": {"type": "string", "index": "not_analyzed"},
        'external_blobs': {
            'dynamic': False,
            'type': 'object'
        },
        '_attachments': {
            'dynamic': False,
            'type': 'object'
        },
        'form': {
            'dynamic': True,
            'properties': {
                '@name': {"type": "string", "index": "not_analyzed"},
                "#type": {"type": "string", "index": "not_analyzed"},
                'meta': {
                    'dynamic': False,
                    'properties': {
                        "timeStart": {
                            "type": "date",
                            "format": DATE_FORMATS_STRING
                        },
                        "timeEnd": {
                            "type": "date",
                            "format": DATE_FORMATS_STRING
                        },
                        "userID": {"type": "string", "index": "not_analyzed"},
                        "deviceID": {"type": "string", "index": "not_analyzed"},
                        "instanceID": {"type": "string", "index": "not_analyzed"},
                        "username": {"type": "string", "index": "not_analyzed"},
                        "appVersion": {"type": "string", "index": "not_analyzed"},
                        "CommCareVersion": {"type": "string", "index": "not_analyzed"},
                    }
                },
            },
        },
    },
    "dynamic_templates": [
        {
            'case_block': {
                "match": "case",
                "mapping": CASE_MAPPING_FRAGMENT
            }
        },
        {
            "everything_else": {
                "match": "*",
                "match_mapping_type": "string",
                "mapping": {"type": "string", "index": "not_analyzed"}
            }
        }
    ]
}
