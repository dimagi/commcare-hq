from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.pillows.core import DATE_FORMATS_STRING, DATE_FORMATS_ARR
from corehq.pillows.mappings import NULL_VALUE
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo

XFORM_INDEX = es_index("xforms_2016-07-07")

XFORM_MAPPING = {
    "date_detection": False,
    "date_formats": DATE_FORMATS_ARR,  # for parsing the explicitly defined dates
    'dynamic': False,
    "_meta": {
        "created": '2013-08-13',
    },
    "properties": {
        'doc_type': {'type': 'text'},
        'inserted_at': {"type": "date", "format": DATE_FORMATS_STRING},
        'user_type': {'type': 'keyword', "null_value": NULL_VALUE},
        "domain": {
            "type": "text",
            "fields": {
                "domain": {"type": "text"},
                "exact": {"type": "keyword"}
                # exact is full text string match - hyphens get parsed in standard
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
        "build_id": {"type": "keyword"},
        "received_on": {
            "type": "date",
            "format": DATE_FORMATS_STRING
        },
        "server_modified_on": {
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
        '__retrieved_case_ids': {'type': 'keyword'},
        'backend_id': {'type': 'keyword'},
        'form': {
            'dynamic': False,
            'properties': {
                '@name': {"type": "keyword"},
                "#type": {"type": "keyword"},
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
                        #note, the case_id method here assumes single case properties within a form
                        #in order to support multi case properties, a dynamic template needs to be added along with fundamentally altering case queries

                        "@case_id": {"type": "keyword"},
                        "@user_id": {"type": "keyword"},
                        "@xmlns": {"type": "keyword"},


                        "case_id": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "xmlns": {"type": "keyword"},
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
                        "userID": {"type": "keyword", "null_value": NULL_VALUE},
                        "deviceID": {"type": "keyword"},
                        "instanceID": {"type": "keyword"},
                        "username": {"type": "keyword"},
                        "appVersion": {"type": "keyword"},
                        "commcare_version": {"type": "keyword"},
                        "app_build_version": {"type": "keyword"},
                        "geo_point": {
                            "type": "geo_point"
                        },
                    }
                },
            },
        },
    }
}

XFORM_ES_TYPE = 'xform'
XFORM_ALIAS = "xforms"

XFORM_INDEX_INFO = ElasticsearchIndexInfo(
    index=XFORM_INDEX,
    alias=XFORM_ALIAS,
    type=XFORM_ES_TYPE,
    mapping=XFORM_MAPPING,
)
