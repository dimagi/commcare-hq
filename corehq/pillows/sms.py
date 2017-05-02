from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed, KafkaCheckpointEventHandler
from corehq.apps.sms.change_publishers import change_meta_from_sms
from corehq.elastic import get_es_new
from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
from pillowtop.checkpoints.manager import get_checkpoint_for_elasticsearch_pillow
from pillowtop.feed.interface import Change
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor
from pillowtop.reindexer.change_providers.django_model import DjangoModelChangeProvider
from pillowtop.reindexer.reindexer import ElasticPillowReindexer


def get_sql_sms_pillow(pillow_id='SqlSMSPillow', params=None):
    assert pillow_id == 'SqlSMSPillow', 'Pillow ID is not allowed to change'
    kafka_topics = [topics.SMS]
    checkpoint = get_checkpoint_for_elasticsearch_pillow(pillow_id, SMS_INDEX_INFO, kafka_topics)
    processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=SMS_INDEX_INFO,
        doc_prep_fn=lambda x: x
    )
    change_feed = KafkaChangeFeed(topics=kafka_topics, group_id=checkpoint.checkpoint_id)
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=processor,
        change_processed_event_handler=KafkaCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100, change_feed=change_feed
        ),
    )


def get_sms_reindexer():
    from corehq.apps.sms.models import SMS
    return ElasticPillowReindexer(
        pillow=get_sql_sms_pillow(),
        change_provider=DjangoModelChangeProvider(SMS, _sql_sms_to_change),
        elasticsearch=get_es_new(),
        index_info=SMS_INDEX_INFO,
    )


def _sql_sms_to_change(sms):
    return Change(
        id=sms.couch_id,
        sequence_id=None,
        document=sms.to_json(),
        deleted=False,
        metadata=change_meta_from_sms(sms),
        document_store=None,
    )
