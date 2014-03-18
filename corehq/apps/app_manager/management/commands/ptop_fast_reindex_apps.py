from corehq.apps.app_manager.models import ApplicationBase
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.application import AppPillow

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(ElasticReindexer):
    help = "Fast reindex of app elastic index by using the applications view and reindexing apps"

    doc_class = ApplicationBase
    view_name = 'app_manager/applications'
    pillow_class = AppPillow
