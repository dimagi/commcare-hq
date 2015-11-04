from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics, change_feed_logger
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processor import LoggingProcessor


# this number intentionally left high to avoid many redundant saves while this pillow is still
# in experimental stage
KAFKA_CHECKPOINT_FREQUENCY = 10000


def get_demo_case_consumer_pillow():
    document_store = CouchDocumentStore(CommCareCase.get_db())
    checkpoint = PillowCheckpoint(
        document_store,
        'kafka-demo-case-pillow-checkpoint',
    )
    return ConstructedPillow(
        name='KafkaCaseConsumerPillow',
        document_store=document_store,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topic=topics.CASE, group_id='demo-case-group'),
        processor=LoggingProcessor(logger=change_feed_logger),
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=KAFKA_CHECKPOINT_FREQUENCY,
        ),
    )
