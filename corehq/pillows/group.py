from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.groups.models import Group
from corehq.elastic import get_es_new
from corehq.util.doc_processor.couch import CouchDocumentProvider

from .mappings.group_mapping import GROUP_INDEX_INFO
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer, ReindexerFactory


def get_group_to_elasticsearch_processor():
    """Inserts group changes into ES

    Reads from:
      - Kafka topics: group
      - Group data source (CouchDB)

    Writes to:
      - GroupES index
    """
    return ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=GROUP_INDEX_INFO,
    )


def get_group_pillow_old(pillow_id='GroupPillow', num_processes=1, process_num=0, **kwargs):
    """Group pillow (old). Sends Group data to Elasticsearch

    Processors:
      - :py:class:`corehq.pillows.group.get_group_to_elasticsearch_processor`
    """
    # todo; To remove after full rollout of https://github.com/dimagi/commcare-hq/pull/21329/
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
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args
    ]

    def build(self):
        iteration_key = "GroupToElasticsearchPillow_{}_reindexer".format(GROUP_INDEX_INFO.index)
        doc_provider = CouchDocumentProvider(iteration_key, [Group])
        options = {
            'chunk_size': 5
        }
        options.update(self.options)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            elasticsearch=get_es_new(),
            index_info=GROUP_INDEX_INFO,
            doc_transform=lambda x: x,
            pillow=get_group_pillow_old(),
            **options
        )
