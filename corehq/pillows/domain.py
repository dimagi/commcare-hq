from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.domain.models import Domain
from corehq.apps.es.domains import domain_adapter
from corehq.util.doc_processor.couch import CouchDocumentProvider
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer, ReindexerFactory


def get_domain_kafka_to_elasticsearch_pillow(pillow_id='KafkaDomainPillow', num_processes=1,
                                             process_num=0, **kwargs):
    """Domain pillow to replicate documents to ES

    Processors:
      - :py:class:`pillowtop.processors.elastic.ElasticProcessor`
    """
    assert pillow_id == 'KafkaDomainPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, domain_adapter.index_name, [topics.DOMAIN])
    domain_processor = ElasticProcessor(domain_adapter)
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
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args
    ]

    def build(self):
        iteration_key = "DomainToElasticsearchPillow_{}_reindexer".format(domain_adapter.index_name)
        doc_provider = CouchDocumentProvider(iteration_key, [Domain])
        options = {
            'chunk_size': 5
        }
        options.update(self.options)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            domain_adapter,
            pillow=get_domain_kafka_to_elasticsearch_pillow(),
            **options
        )
