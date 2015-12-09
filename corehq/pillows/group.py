from corehq.apps.groups.models import Group

from .mappings.group_mapping import GROUP_INDEX, GROUP_MAPPING
from .base import HQPillow


class GroupPillow(HQPillow):
    """
    Simple/Common Case properties Indexer
    """

    document_class = Group
    couch_filter = "groups/all_groups"
    es_alias = "hqgroups"
    es_type = "group"
    es_index = GROUP_INDEX
    default_mapping = GROUP_MAPPING

    @classmethod
    def get_unique_id(self):
        return GROUP_INDEX
