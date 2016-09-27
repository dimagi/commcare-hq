from corehq.pillows.base import DEFAULT_META
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
        'doc_type': {'type': 'string'},
        'inserted_at': {"type": "date", "format": DATE_FORMATS_STRING},
        'user_type': {'type': 'string', "index": "not_analyzed", "null_value": NULL_VALUE},
        "domain": {
            "type": "multi_field",
            "fields": {
                "domain": {"type": "string", "index": "analyzed"},
                "exact": {"type": "string", "index": "not_analyzed"}
                # exact is full text string match - hyphens get parsed in standard
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
        "build_id": {"type": "string", "index": "not_analyzed"},
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
        '__retrieved_case_ids': {'index': 'not_analyzed', 'type': 'string'},
        'backend_id': {'type': 'string', 'index': 'not_analyzed'},
        'form': {
            'dynamic': False,
            'properties': {
                '@name': {"type": "string", "index": "not_analyzed"},
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
                        #note, the case_id method here assumes single case properties within a form
                        #in order to support multi case properties, a dynamic template needs to be added along with fundamentally altering case queries

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
                        "userID": {"type": "string", "index": "not_analyzed", "null_value": NULL_VALUE},
                        "deviceID": {"type": "string", "index": "not_analyzed"},
                        "instanceID": {"type": "string", "index": "not_analyzed"},
                        "username": {"type": "string", "index": "not_analyzed"},
                        "appVersion": {"type": "string", "index": "not_analyzed"},
                        "commcare_version": {"type": "string", "index": "not_analyzed"},
                        "app_build_version": {"type": "string", "index": "not_analyzed"},
                        "geo_point": {
                            "type": "geo_point",
                            "lat_lon": True,
                            "geohash": True,
                            "geohash_prefix": True,
                            "geohash_precision": '10m'
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
    meta=DEFAULT_META,
    mapping=XFORM_MAPPING,
)
