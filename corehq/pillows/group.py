from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.groups.models import Group
from corehq.elastic import get_es_new

from .mappings.group_mapping import GROUP_INDEX_INFO
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer, ReindexerFactory


def get_group_to_elasticsearch_processor():
    """
    This processor adds users from xform submissions that come in to the User Index if they don't exist in HQ
    """
    return ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=GROUP_INDEX_INFO,
    )


class GroupReindexerFactory(ReindexerFactory):
    slug = 'group'
    arg_contributors = [
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        return ElasticPillowReindexer(
            pillow_or_pillow_processor=get_group_to_elasticsearch_processor(),
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
            **self.options
        )
