from corehq.apps.groups.models import Group
from corehq.elastic import get_es_new

from .mappings.group_mapping import GROUP_INDEX, GROUP_MAPPING, GROUP_INDEX_INFO
from .base import HQPillow
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer


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


def get_group_reindexer():
    return ElasticPillowReindexer(
        pillow=GroupPillow(),
        change_provider=CouchViewChangeProvider(
            couch_db=Group.get_db(),
            view_name='all_docs/by_doc_type',
            view_kwargs={
                'startkey': ['Group'],
                'endkey': ['Group', {}],
                'include_docs': True,
            }
        ),
        elasticsearch=get_es_new(),
        index_info=GROUP_INDEX_INFO,
    )
