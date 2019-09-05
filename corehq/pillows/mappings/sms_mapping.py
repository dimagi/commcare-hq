from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo

SMS_INDEX = es_index("smslogs_2017-02-09")
SMS_MAPPING = {
    '_meta': {
       'comment': 'Autogenerated [corehq.apps.sms.models.SMSLog] mapping from ptop_generate_mapping 09/23/2013',
       'created': None
    },
    'date_detection': False,
    'date_formats': DATE_FORMATS_ARR,
    'dynamic': False,
    'properties': {
        'backend_api': {'type': 'string'},
        'backend_id': {'type': 'string'},
        'base_doc': {'type': 'string'},
        'billed': {'type': 'boolean'},
        'couch_recipient': {'type': 'string'},
        'couch_recipient_doc_type': {'type': 'string'},
        'date': {
            'format': DATE_FORMATS_STRING,
            'type': 'date'
        },
        'direction': {'type': 'string'},
        'doc_type': {'index': 'not_analyzed', 'type': 'string'},
        'domain': {
            'fields': {
                'domain': {'index': 'analyzed', 'type': 'string'},
                'exact': {'index': 'not_analyzed', 'type': 'string'}
            },
            'type': 'multi_field'
        },
        'phone_number': {'type': 'string'},
        'processed': {'type': 'boolean'},
        'reminder_id': {'type': 'string'},
        'text': {'type': 'string'},
        'workflow': {'type': 'string'},
        'xforms_session_couch_id': {'type': 'string'}
    }
}

SMS_TYPE = 'sms'

SMS_INDEX_INFO = ElasticsearchIndexInfo(
    index=SMS_INDEX,
    alias="smslogs",
    type=SMS_TYPE,
    mapping=SMS_MAPPING,
)
