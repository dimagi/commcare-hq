import hashlib
import simplejson
from auditcare.models import AuditEvent
from couchforms.models import XFormInstance
from couchlog.models import ExceptionRecord
from pillowtop.listener import  LogstashMonitoringPillow, AliasedElasticPillow
from pillowtop.listener import ElasticPillow
from casexml.apps.case.models import CommCareCase
from corehq.apps.domain.models import Domain
import logging
import settings
from datetime import datetime


date_format_arr = ["yyyy-MM-dd",
                   #"date_time_no_millis",
                   #                      'date_optional_time',
                   "yyyy-MM-dd'T'HH:mm:ssZZ",
                   "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
                   "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'",
                   "yyyy-MM-dd'T'HH:mm:ss'Z'",
                   "yyyy-MM-dd'T'HH:mm:ssZ",
                   "yyyy-MM-dd'T'HH:mm:ssZZ'Z'",
                   "yyyy-MM-dd'T'HH:mm:ss.SSSZZ",
                   "yyyy-MM-dd'T'HH:mm:ss",
                   "yyyy-MM-dd' 'HH:mm:ss",
                   "yyyy-MM-dd' 'HH:mm:ss.SSSSSS",
]
#https://github.com/elasticsearch/elasticsearch/issues/2132
#elasticsearch Illegal pattern component: t
#no builtin types for || joins
formats_string = '||'.join(date_format_arr)

class AuditcarePillow(LogstashMonitoringPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_AUDITCARE_PORT
    couch_db = AuditEvent.get_db()
    couch_filter = 'auditcare/auditdocs'


class CouchlogPillow(LogstashMonitoringPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_COUCHLOG_PORT
    couch_db = ExceptionRecord.get_db()
    couch_filter = 'couchlog/couchlogs'


class DevicelogPillow(LogstashMonitoringPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_DEVICELOG_PORT
    couch_db = XFormInstance.get_db()
    couch_filter = 'couchforms/devicelogs'




