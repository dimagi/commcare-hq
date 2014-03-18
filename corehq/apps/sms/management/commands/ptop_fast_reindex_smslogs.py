from corehq.apps.sms.models import SMSLog
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.sms import SMSPillow

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(ElasticReindexer):
    help = "Fast reindex of user elastic index by using the domain view and reindexing users"

    doc_class = SMSLog
    view_name = 'sms/by_domain'
    pillow_class = SMSPillow
