import copy
from corehq.apps.accounting.models import Subscription
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.change_feed import topics
from corehq.apps.domain.models import Domain
from corehq.elastic import get_es_new
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
from corehq.util.doc_processor.couch import CouchDocumentProvider
from django_countries.data import COUNTRIES
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.reindexer import ResumableBulkElasticPillowReindexer, ReindexerFactory


def transform_domain_for_elasticsearch(doc_dict):
    doc_ret = copy.deepcopy(doc_dict)
    sub = Subscription.visible_objects.filter(subscriber__domain=doc_dict['name'], is_active=True)
    doc_ret['deployment'] = doc_ret.get('deployment', None) or {}
    countries = doc_ret['deployment'].get('countries', [])
    doc_ret['deployment']['countries'] = []
    if sub:
        doc_ret['subscription'] = sub[0].plan_version.plan.edition
    for country in countries:
        doc_ret['deployment']['countries'].append(COUNTRIES[country].upper())
    return doc_ret


def get_domain_kafka_to_elasticsearch_pillow(pillow_id='KafkaDomainPillow', num_processes=1,
                                             process_num=0, **kwargs):
    """Domain pillow to replicate documents to ES

    Processors:
      - :py:class:`pillowtop.processors.elastic.ElasticProcessor`
    """
    assert pillow_id == 'KafkaDomainPillow', 'Pillow ID is not allowed to change'
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, DOMAIN_INDEX_INFO, [topics.DOMAIN])
    domain_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=DOMAIN_INDEX_INFO,
        doc_prep_fn=transform_domain_for_elasticsearch,
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
        ReindexerFactory.resumable_reindexer_args,
        ReindexerFactory.elastic_reindexer_args
    ]

    def build(self):
        iteration_key = "DomainToElasticsearchPillow_{}_reindexer".format(DOMAIN_INDEX_INFO.index)
        doc_provider = CouchDocumentProvider(iteration_key, [Domain])
        options = {
            'chunk_size': 5
        }
        options.update(self.options)
        return ResumableBulkElasticPillowReindexer(
            doc_provider,
            elasticsearch=get_es_new(),
            index_info=DOMAIN_INDEX_INFO,
            doc_transform=transform_domain_for_elasticsearch,
            pillow=get_domain_kafka_to_elasticsearch_pillow(),
            **options
        )
