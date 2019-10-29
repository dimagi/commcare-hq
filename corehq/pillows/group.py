from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.groups.models import Group
from corehq.elastic import get_es_instance, get_es_interface

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
        es_interface=get_es_interface(),
        index_info=GROUP_INDEX_INFO,
    )


def get_group_pillow_old(pillow_id='GroupPillow', num_processes=1, process_num=0, **kwargs):
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
    This pillow adds users from xform submissions that come in to the User Index if they don't exist in HQ
    """
    assert pillow_id == 'GroupPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, GROUP_INDEX_INFO, [topics.GROUP])
    processor = get_group_to_elasticsearch_processor()
    change_feed = KafkaChangeFeed(
        topics=[topics.GROUP], client_id='groups-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=10, change_feed=change_feed
        ),
    )


class GroupReindexerFactory(ReindexerFactory):
    slug = 'group'
    arg_contributors = [
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        return ElasticPillowReindexer(
            pillow_or_processor=get_group_pillow_old(),
            change_provider=CouchViewChangeProvider(
                couch_db=Group.get_db(),
                view_name='all_docs/by_doc_type',
                view_kwargs={
                    'startkey': ['Group'],
                    'endkey': ['Group', {}],
                    'include_docs': True,
                }
            ),
            elasticsearch=get_es_instance(),
            index_info=GROUP_INDEX_INFO,
            **self.options
        )
