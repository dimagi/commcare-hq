from os.path import join
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.consumer.feed import KafkaChangeFeed
from corehq.apps.app_manager.models import Application
from corehq.blobs import get_blob_db
from corehq.util.couchdb_management import couch_config
from dimagi.utils.couch.database import get_db
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.feed.couch import CouchChangeFeed
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

    def process_change(self, pillow_instance, change, do_set_checkpoint):
        if change.deleted:
            bucket = join(self.bucket_base, change.id)
            self.blob_db.delete(bucket=bucket)


def get_main_blob_deletion_pillow(pillow_id):
    """Get blob deletion pillow for the main couch database

    Using the KafkaChangeFeed ties this to the main couch database.
    """
    return _get_blob_deletion_pillow(
        pillow_id,
        get_db(None),
        PillowCheckpoint('kafka-blob-deletion-pillow-checkpoint'),
        KafkaChangeFeed(topics=[topics.META], group_id='blob-deletion-group'),
    )


def get_application_blob_deletion_pillow(pillow_id):
    """Get blob deletion pillow for the apps couch database"""
    couch_db = couch_config.get_db_for_class(Application)
    return _get_blob_deletion_pillow(pillow_id, couch_db)


def _get_blob_deletion_pillow(pillow_id, couch_db, checkpoint=None, change_feed=None):
    if checkpoint is None:
        checkpoint = PillowCheckpoint(pillow_id)
    if change_feed is None:
        change_feed = CouchChangeFeed(couch_db, include_docs=False)
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=BlobDeletionProcessor(get_blob_db(), couch_db.dbname),
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint,
            checkpoint_frequency=KAFKA_CHECKPOINT_FREQUENCY,
        ),
    )
