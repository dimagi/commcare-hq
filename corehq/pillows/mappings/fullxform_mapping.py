from corehq.pillows.core import DATE_FORMATS_STRING, DATE_FORMATS_ARR

FULL_XFORM_INDEX="full_xforms_b3577b244de808e77ac5aa30117268e2"




FULL_XFORM_MAPPING = {
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR, #for parsing the explicitly defined dates
    'ignore_malformed': True,
    'dynamic': False, # still set to false, as we want to leave it to the implementor's decision on how to map properties
    "_meta": {
        "created": '', #record keeping on the index.
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
        '_attachments': {
            'dynamic': False,
            'type': 'object'
        },
        'form': {
            'dynamic': False,
            'properties': {
                "#type": {"type": "string", "index": "not_analyzed"},
                'case': {
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

                        "@case_id": {"type": "string", "index": "not_analyzed"},
                        "@user_id": {"type": "string", "index": "not_analyzed"},
                        "@xmlns": {"type": "string", "index": "not_analyzed"},


                        "case_id": {"type": "string", "index": "not_analyzed"},
                        "user_id": {"type": "string", "index": "not_analyzed"},
                        "xmlns": {"type": "string", "index": "not_analyzed"},
                    }
                },
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
                        "username": {"type": "string", "index": "not_analyzed"}
                    }
                },
            },
        },
    }
}