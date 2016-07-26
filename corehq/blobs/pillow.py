from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.blobs import get_blob_db
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor


# this number intentionally left high to avoid many redundant saves while this
# pillow is still in experimental stage

KAFKA_CHECKPOINT_FREQUENCY = 1000


class BlobDeletionProcessor(PillowProcessor):

    def __init__(self, blob_db):
        super(BlobDeletionProcessor, self).__init__()
        self.blob_db = blob_db

    def process_change(self, pillow_instance, change):
        if change.deleted:
            bucket = "{}/{}".format(change.meta.data_source_name, change.id)
            self.blob_db.delete(bucket=bucket)


def get_blob_deletion_pillow(pillow_id):
    """Get blob deletion pillow
    """
    checkpoint = PillowCheckpoint(pillow_id)
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=KafkaChangeFeed(
            topics=[topics.META, topics.APP],
            group_id='blob-deletion-group',
        ),
        processor=BlobDeletionProcessor(get_blob_db()),
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint,
            checkpoint_frequency=KAFKA_CHECKPOINT_FREQUENCY,
        ),
    )
