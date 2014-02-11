from corehq.apps.groups.models import Group
from corehq.pillows.mappings.group_mapping import GROUP_INDEX, GROUP_MAPPING
from dimagi.utils.decorators.memoized import memoized
from pillowtop.listener import AliasedElasticPillow
from django.conf import settings


class GroupPillow(HQPillow):
    """
    Simple/Common Case properties Indexer
    """

    document_class = Group
    couch_filter = "groups/all_groups"
    es_index_prefix = "hqgroups"
    es_alias = "hqgroups"
    es_type = "group"
    es_index = GROUP_INDEX
    default_mapping = GROUP_MAPPING
