from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed.document_types import GROUP
from corehq.apps.groups.models import Group
from corehq.elastic import get_es_new

from .mappings.group_mapping import GROUP_INDEX_INFO
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer


def get_group_pillow(pillow_id='GroupPillow', params=None):
    """
    This pillow adds users from xform submissions that come in to the User Index if they don't exist in HQ
    """
    assert pillow_id == 'GroupPillow', 'Pillow ID is not allowed to change'
    topics = [GROUP]
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, GROUP_INDEX_INFO, topics)
    processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=GROUP_INDEX_INFO,
    )
    change_feed = KafkaChangeFeed(topics=topics, group_id=checkpoint.checkpoint_id)
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
    )


def get_group_reindexer():
    return ElasticPillowReindexer(
        pillow=get_group_pillow(),
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
