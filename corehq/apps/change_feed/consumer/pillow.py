from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler, \
    get_django_checkpoint_store
from pillowtop.couchdb import CachedCouchDB
from pillowtop.listener import PythonPillow
from pillowtop.logger import pillow_logging
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processor import NoopProcessor


# this number intentionally left high to avoid many redundant saves while this pillow is still
# in experimental stage
KAFKA_CHECKPOINT_FREQUENCY = 1000


class LoggingPythonPillow(PythonPillow):

    def process_change(self, change, is_retry_attempt=False):
        # do nothing
        pass

    def fire_change_processed_event(self, change, context):
        # todo: when PythonPillow moves checkpoints to this function this class will
        # need to use some other mechanism for this or reimplement checkpointing
        if context.changes_seen % KAFKA_CHECKPOINT_FREQUENCY == 0:
            # only log a small amount to avoid clogging up supervisor
            pillow_logging.info('Processed change {}: {}'.format(context.changes_seen, change))


def get_demo_case_consumer_pillow():
    checkpoint = PillowCheckpoint(
        get_django_checkpoint_store(),
        'kafka-demo-case-pillow-checkpoint',
    )
    return ConstructedPillow(
        name='KafkaCaseConsumerPillow',
        document_store=None,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topic=topics.CASE, group_id='demo-case-group'),
        processor=NoopProcessor(),
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=KAFKA_CHECKPOINT_FREQUENCY,
        ),
    )


def get_demo_python_pillow_consumer():
    checkpoint = PillowCheckpoint(
        get_django_checkpoint_store(),
        'kafka-demo-python-pillow-checkpoint',
    )
    return LoggingPythonPillow(
        couch_db=CachedCouchDB(CommCareCase.get_db().uri, readonly=False),
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topic=topics.CASE, group_id='demo-python-pillow-group'),
        preload_docs=False,
    )
