from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.elastic import get_es_new
from corehq.pillows.mappings.sms_mapping import SMS_INDEX_INFO
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors.elastic import ElasticProcessor


SMS_PILLOW_CHECKPOINT_ID = 'sql-sms-to-es'
SMS_PILLOW_KAFKA_CONSUMER_GROUP_ID = 'sql-sms-to-es'


def get_sql_sms_pillow(pillow_id):
    checkpoint = PillowCheckpoint(SMS_PILLOW_CHECKPOINT_ID)
    processor = ElasticProcessor(
        elasticsearch=get_es_new(),
        index_info=SMS_INDEX_INFO,
        doc_prep_fn=lambda x: x
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[topics.SMS], group_id=SMS_PILLOW_KAFKA_CONSUMER_GROUP_ID),
        processor=processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )
