from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.user import UserPillow, UnknownUsersPillow
from couchforms.models import XFormInstance

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(ElasticReindexer):
    help = "Fast reindex of user elastic index by using the domain view and reindexing users"

    doc_class = XFormInstance
    view_name = 'reports_forms/all_forms'
    pillow_class = UnknownUsersPillow
    indexing_pillow_class = UserPillow
    own_index_exists = False

    def get_extra_view_kwargs(self):
        return {'startkey': ['submission'], 'endkey': ['submission', {}]}
