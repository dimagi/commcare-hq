from corehq.apps.groups.models import Group
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.group import GroupPillow

CHUNK_SIZE = 500
POOL_SIZE = 15


class Command(ElasticReindexer):
    help = "Fast reindex of group elastic index by using the group view and reindexing groups"

    doc_class = Group
    view_name = 'groups/all_groups'
    pillow_class = GroupPillow
