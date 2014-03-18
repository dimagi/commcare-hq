from auditcare.models import AuditEvent
from couchforms.models import XFormInstance
from couchlog.models import ExceptionRecord
from pillowtop.listener import LogstashMonitoringPillow
from django.conf import settings


DATE_FORMATS_ARR = ["yyyy-MM-dd",
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
                   "mm/dd/yy' 'HH:mm:ss",
]

#https://github.com/elasticsearch/elasticsearch/issues/2132
#elasticsearch Illegal pattern component: t
#no builtin types for || joins
DATE_FORMATS_STRING = '||'.join(DATE_FORMATS_ARR)

class AuditcarePillow(LogstashMonitoringPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_AUDITCARE_PORT
    document_class = AuditEvent
    couch_filter = 'auditcare/auditdocs'


class CouchlogPillow(LogstashMonitoringPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_COUCHLOG_PORT
    document_class = ExceptionRecord
    couch_filter = 'couchlog/couchlogs'


class DevicelogPillow(LogstashMonitoringPillow):
    endpoint_host = settings.LOGSTASH_HOST
    endpoint_port = settings.LOGSTASH_DEVICELOG_PORT
    document_class = XFormInstance
    couch_filter = 'couchforms/devicelogs'




