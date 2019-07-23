from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.pillows.mappings import NULL_VALUE
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo

CASE_INDEX = es_index("hqcases_2016-03-04")
CASE_ES_TYPE = 'case'

CASE_MAPPING = {
    'date_detection': False,
    'date_formats': DATE_FORMATS_ARR,
    'dynamic': False,
    '_meta': {
        'comment': '',
        'created': '2013-09-19 @dmyung'
    },
    'properties': {
        'actions': {'dynamic': False,
                    'properties': {
                        'action_type': {'type': 'text'},
                        'date': {'format': DATE_FORMATS_STRING,
                                 'type': 'date'},
                        'doc_type': {'type': 'keyword'},
                        'indices': {'dynamic': False,
                                    'properties': {
                                        'doc_type': {'type': 'keyword'},
                                        'identifier': {'type': 'text'},
                                        'referenced_id': {'type': 'text'},
                                        'referenced_type': {'type': 'text'}
                                    },
                                    'type': 'object'},
                        'server_date': {'format': DATE_FORMATS_STRING,
                                        'type': 'date'},
                        'sync_log_id': {'type': 'text'},
                        'user_id': {'type': 'text'},
                        'xform_id': {'type': 'text'},
                        'xform_name': {'type': 'text'},
                        'xform_xmlns': {'type': 'text'}
                    },
                    'type': 'nested'},
        'closed': {'type': 'boolean'},
        'closed_by': {'type': 'text'},
        'closed_on': {'format': DATE_FORMATS_STRING,
                      'type': 'date'},
        'computed_': {'enabled': False,
                      'type': 'object'},
        'computed_modified_on_': {'format': DATE_FORMATS_STRING,
                                  'type': 'date'},
        'doc_type': {'type': 'keyword'},
        'inserted_at': {"type": "date", "format": DATE_FORMATS_STRING},
        'domain': {'fields': {'domain': {'type': 'text'},
                              'exact': {'type': 'keyword'}},
                   'type': 'text'},
        'export_tag': {'type': 'text'},
        'external_id': {'fields': {'exact': {'type': 'keyword'},
                                   'external_id': {'type': 'text'}},
                        'type': 'text'},
        'indices': {'dynamic': False,
                    'properties': {'doc_type': {'type': 'keyword'},
                                   'identifier': {'type': 'text'},
                                   'referenced_id': {'type': 'text'},
                                   'referenced_type': {'type': 'text'}},
                    'type': 'object'},
        'initial_processing_complete': {'type': 'boolean'},
        'location_id': {'type': 'text'},
        'modified_on': {'format': DATE_FORMATS_STRING,
                        'type': 'date'},
        'name': {'fields': {'exact': {'type': 'keyword'},
                            'name': {'type': 'text'}},
                 'type': 'text'},
        'opened_by': {'type': 'text'},
        'opened_on': {'format': DATE_FORMATS_STRING,
                      'type': 'date'},
        'owner_id': {'type': 'text'},
        'owner_type': {'type': 'keyword', "null_value": NULL_VALUE},
        'referrals': {'enabled': False, 'type': 'object'},
        'server_modified_on': {'format': DATE_FORMATS_STRING,
                               'type': 'date'},
        'type': {'fields': {'exact': {'type': 'keyword'},
                            'type': {'type': 'text'}},
                 'type': 'text'},
        'user_id': {'type': 'text'},
        'version': {'type': 'text'},
        'xform_ids': {'type': 'keyword'},
        'contact_phone_number': {'type': 'keyword'},
        'backend_id': {'type': 'keyword'},
    }
}

CASE_ES_ALIAS = "hqcases"

CASE_INDEX_INFO = ElasticsearchIndexInfo(
    index=CASE_INDEX,
    alias=CASE_ES_ALIAS,
    type=CASE_ES_TYPE,
    mapping=CASE_MAPPING
)
