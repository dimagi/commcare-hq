from django.db import IntegrityError
from pillowtop.checkpoints.manager import (
    PillowCheckpoint,
    PillowCheckpointEventHandler,
)
from pillowtop.feed.couch import CouchChangeFeed, populate_change_metadata
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor

from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.producer import ChangeProducer
from corehq.apps.change_feed.topics import get_topic_for_doc_type
from corehq.apps.cleanup.models import DeletedCouchDoc
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.util.couchdb_management import couch_config


class KafkaProcessor(PillowProcessor):
    """Generic processor for CouchDB changes to put those changes in a kafka topic

    Reads from:
      - CouchDB change feed

    Writes to:
      - Specified kafka topic
      - DeletedCouchDoc SQL table
    """

    def __init__(self, data_source_type, data_source_name, default_topic):
        self._producer = ChangeProducer()
        self._data_source_type = data_source_type
        self._data_source_name = data_source_name
        self._default_topic = default_topic

    def process_change(self, change):
        populate_change_metadata(change, self._data_source_type, self._data_source_name)
        if change.metadata:
            doc_type = _get_doc_type_from_change(change)
            # The default topic is used in case a doc_type cannot be found (e.g., a hard deletion might result
            # in a missing doc_type)
            topic = get_topic_for_doc_type(doc_type, self._data_source_type, self._default_topic)
            self._producer.send_change(topic, change.metadata)

            # soft deletion
            if change.metadata.is_deletion and doc_type is not None:
                deleted_on = change.metadata.original_publication_datetime
                _create_deleted_couch_doc(change.id, doc_type, deleted_on)


def get_default_couch_db_change_feed_pillow(pillow_id, **kwargs):
    return get_change_feed_pillow_for_db(pillow_id, couch_config.get_db(None))


def get_user_groups_db_kafka_pillow(pillow_id, **kwargs):
    return get_change_feed_pillow_for_db(
        pillow_id, couch_config.get_db_for_class(CommCareUser), topics.COMMCARE_USER
    )


def get_domain_db_kafka_pillow(pillow_id, **kwargs):
    return get_change_feed_pillow_for_db(pillow_id, couch_config.get_db_for_class(Domain), topics.DOMAIN)


def get_application_db_kafka_pillow(pillow_id, **kwargs):
    from corehq.apps.app_manager.models import Application
    return get_change_feed_pillow_for_db(pillow_id, couch_config.get_db_for_class(Application), topics.APP)


def get_change_feed_pillow_for_db(pillow_id, couch_db, default_topic=None):
    """Generic pillow for inserting Couch documents into Kafka.

    Reads from:
      - CouchDB

    Writes to:
      - Kafka
    """
    processor = KafkaProcessor(
        data_source_type=data_sources.SOURCE_COUCH,
        data_source_name=couch_db.dbname,
        default_topic=default_topic,
    )
    change_feed = CouchChangeFeed(couch_db)
    checkpoint = PillowCheckpoint(pillow_id, change_feed.sequence_format)
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=change_feed,
        processor=processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


def _get_doc_type_from_change(change):
    """
    According to past comments, couch change feeds do not consistently include the 'doc' with the published
    change which makes it hard to determine the doc_type. Try the metadata first, then the 'doc', otherwise
    we are out of luck
    """
    if change.metadata.document_type:
        return change.metadata.document_type
    try:
        return change['doc']['doc_type']
    except KeyError:
        return None


def _create_deleted_couch_doc(doc_id, doc_type, deleted_on):
    try:
        DeletedCouchDoc.objects.create(doc_id=doc_id,
                                       doc_type=doc_type,
                                       deleted_on=deleted_on)
    except IntegrityError:
        # if it already exists, ignore it
        pass
