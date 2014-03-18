from corehq.apps.sms.models import SMSLog
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from custom.trialconnect.smspillow import TCSMSPillow

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(ElasticReindexer):
    help = "Fast reindex of trialconnect's sms elastic index by using the custom sms view and reindexing smslogs"

    doc_class = SMSLog
    view_name = 'trialconnect/smslogs'
    pillow_class = TCSMSPillow
