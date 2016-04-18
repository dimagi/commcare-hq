import copy
from corehq.apps.accounting.models import Subscription
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.change_feed.document_types import DOMAIN
from corehq.apps.domain.models import Domain
from corehq.elastic import get_es_new
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX_INFO
from django_countries.data import COUNTRIES
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import ElasticProcessor
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer


def transform_domain_for_elasticsearch(doc_dict):
    doc_ret = copy.deepcopy(doc_dict)
    sub = Subscription.objects.filter(subscriber__domain=doc_dict['name'], is_active=True)
    doc_ret['deployment'] = doc_dict.get('deployment', None) or {}
    countries = doc_ret['deployment'].get('countries', [])
    doc_ret['deployment']['countries'] = []
    if sub:
        doc_ret['subscription'] = sub[0].plan_version.plan.edition
    for country in countries:
        doc_ret['deployment']['countries'].append(COUNTRIES[country].upper())
    return doc_ret


def get_domain_kafka_to_elasticsearch_pillow(pillow_id='domain-kafka-to-es'):
    checkpoint = PillowCheckpoint(
        pillow_id,
    )
    domain_processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=DOMAIN_INDEX_INFO,
        doc_prep_fn=transform_domain_for_elasticsearch
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[DOMAIN], group_id='domains-to-es'),
        processor=domain_processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


def get_domain_reindexer():
    return ElasticPillowReindexer(
        pillow=get_domain_kafka_to_elasticsearch_pillow(),
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
    )
