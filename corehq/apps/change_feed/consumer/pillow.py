from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.dao.django import DjangoDocumentStore
from pillowtop.models import DjangoPillowCheckpoint
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processor import NoopProcessor


# this number intentionally left high to avoid many redundant saves while this pillow is still
# in experimental stage
KAFKA_CHECKPOINT_FREQUENCY = 1000


def get_demo_case_consumer_pillow():
    document_store = DjangoDocumentStore(
        DjangoPillowCheckpoint, DjangoPillowCheckpoint.to_dict, DjangoPillowCheckpoint.from_dict,
    )
    checkpoint = PillowCheckpoint(
        document_store,
        'kafka-demo-case-pillow-checkpoint',
    )
    return ConstructedPillow(
        name='KafkaCaseConsumerPillow',
        document_store=document_store,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topic=topics.CASE, group_id='demo-case-group'),
        processor=NoopProcessor(),
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=KAFKA_CHECKPOINT_FREQUENCY,
        ),
    )
