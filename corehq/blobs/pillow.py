from os.path import join
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.blobs import get_blob_db
from dimagi.utils.couch.database import get_db
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor


# this number intentionally left high to avoid many redundant saves while this
# pillow is still in experimental stage

KAFKA_CHECKPOINT_FREQUENCY = 1000


class BlobDeletionProcessor(PillowProcessor):

    def __init__(self, blob_db, bucket_base):
        super(BlobDeletionProcessor, self).__init__()
        self.blob_db = blob_db
        self.bucket_base = bucket_base

    def process_change(self, pillow_instance, change):
        if change.deleted:
            bucket = join(self.bucket_base, change.id)
            self.blob_db.delete(bucket=bucket)


def get_blob_deletion_pillow(pillow_id):
    """Get blob deletion pillow for the main couch database

    Using the KafkaChangeFeed ties this to the main couch database.
    """
    checkpoint = PillowCheckpoint(
        'kafka-blob-deletion-pillow-checkpoint',
    )
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(topics=[topics.META], group_id='blob-deletion-group'),
        processor=BlobDeletionProcessor(get_blob_db(), get_db(None).dbname),
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint,
            checkpoint_frequency=KAFKA_CHECKPOINT_FREQUENCY,
        ),
    )
