from corehq.apps.groups.models import Group
from corehq.apps.hqcase.management.commands.ptop_fast_reindexer import ElasticReindexer
from corehq.pillows.groups_to_user import GroupToUserPillow
from corehq.pillows.user import UserPillow


class Command(ElasticReindexer):
    help = "Fast reindex of user elastic index by using the domain view and reindexing users"

    doc_class = Group
    view_name = 'groups/all_groups'
    pillow_class = GroupToUserPillow
    indexing_pillow_class = UserPillow
    own_index_exists = False
