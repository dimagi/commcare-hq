from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.pillows.core import DATE_FORMATS_STRING, DATE_FORMATS_ARR
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo

REPORT_XFORM_INDEX = es_index("report_xforms_20160824_1708")

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

        "@case_id": {"type": "keyword"},
        "@user_id": {"type": "keyword"},
        "@xmlns": {"type": "keyword"},


        "case_id": {"type": "keyword"},
        "user_id": {"type": "keyword"},
        "xmlns": {"type": "keyword"},

        "create": {
            'type': 'object',
            'dynamic': True,
            'properties:': {
                'case_type': {"type": "keyword"},
                'owner_id': {"type": "keyword"},
                'case_name': {"type": "keyword"},
            }
        },

        "update": {
            'type': 'object',
            'dynamic': True,
            'properties:': {
                'case_type': {"type": "keyword"},
                'owner_id': {"type": "keyword"},
                'case_name': {"type": "keyword"},
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
        'doc_type': {'type': 'text'},
        "domain": {
            "type": "text",
            "fields": {
                "domain": {"type": "text"},
                "exact": {"type": "keyword"}
                #exact is full text string match - hyphens get parsed in standard
                # analyzer
                # in queries you can access by domain.exact
            }
        },
        "xmlns": {
            "type": "text",
            "fields": {
                "xmlns": {"type": "text"},
                "exact": {"type": "keyword"}
            }
        },
        '@uiVersion': {"type": "text"},
        '@version': {"type": "text"},
        "path": {"type": "keyword"},
        "submit_ip": {"type": "ip"},
        "app_id": {"type": "keyword"},
        "received_on": {
            "type": "date",
            "format": DATE_FORMATS_STRING
        },
        'initial_processing_complete': {"type": "boolean"},
        'partial_submission': {"type": "boolean"},
        "#export_tag": {"type": "keyword"},
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
                '@name': {"type": "keyword"},
                "#type": {"type": "keyword"},
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
                        "userID": {"type": "keyword"},
                        "deviceID": {"type": "keyword"},
                        "instanceID": {"type": "keyword"},
                        "username": {"type": "keyword"},
                        "appVersion": {"type": "keyword"},
                        "CommCareVersion": {"type": "keyword"},
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
                "mapping": {"type": "keyword"}
            }
        }
    ]
}

REPORT_XFORM_ALIAS = "report_xforms"
REPORT_XFORM_TYPE = "report_xform"

REPORT_XFORM_INDEX_INFO = ElasticsearchIndexInfo(
    index=REPORT_XFORM_INDEX,
    alias=REPORT_XFORM_ALIAS,
    type=REPORT_XFORM_TYPE,
    mapping=REPORT_XFORM_MAPPING,
)
