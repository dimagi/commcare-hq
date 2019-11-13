from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.domain.models import Domain
from corehq.elastic import get_es_new
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer, ReindexerFactory


def get_domain_kafka_to_elasticsearch_pillow(pillow_id='KafkaDomainPillow', num_processes=1,
                                             process_num=0, **kwargs):
    assert pillow_id == 'KafkaDomainPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, DOMAIN_INDEX_INFO, [topics.DOMAIN])
    domain_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=DOMAIN_INDEX_INFO,
    )
    change_feed = KafkaChangeFeed(
        topics=[topics.DOMAIN], client_id='domains-to-es', num_processes=num_processes, process_num=process_num
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=domain_processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
    )


class DomainReindexerFactory(ReindexerFactory):
    slug = 'domain'
    arg_contributors = [
        ReindexerFactory.elastic_reindexer_args,
    ]

    def build(self):
        return ElasticPillowReindexer(
            pillow_or_processor=get_domain_kafka_to_elasticsearch_pillow(),
            change_provider=CouchViewChangeProvider(
                couch_db=Domain.get_db(),
                view_name='all_docs/by_doc_type',
                view_kwargs={
                    'startkey': ['Domain'],
                    'endkey': ['Domain', {}],
                    'include_docs': True,
                }
            ),
            elasticsearch=get_es_new(),
            index_info=DOMAIN_INDEX_INFO,
            **self.options
        )
