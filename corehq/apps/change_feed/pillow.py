from casexml.apps.case.models import CommCareCase
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
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.util.couchdb_management import couch_config


class KafkaProcessor(PillowProcessor):
    """
    Processor that pushes changes to Kafka
    """

    def __init__(self, data_source_type, data_source_name, default_topic):
        self._producer = ChangeProducer()
        self._data_source_type = data_source_type
        self._data_source_name = data_source_name
        self._default_topic = default_topic

    def process_change(self, change):
        populate_change_metadata(change, self._data_source_type, self._data_source_name)
        if change.metadata:
            change_meta = change.metadata
            # change.deleted is used for hard deletions whereas change_meta.is_deletion is for soft deletions.
            # from the consumer's perspective both should be counted as deletions so just "or" them
            # note: it is strange and hard to reproduce that the couch changes feed is providing a "doc"
            # along with a hard deletion, but it is doing that in the wild so we might as well support it.
            change_meta.is_deletion = change_meta.is_deletion or change.deleted
            if change_meta.is_deletion:
                # If a change has been hard deleted, set a default topic because we may
                # not be able to retrieve its correct doc type
                topic = get_topic_for_doc_type(
                    change_meta.document_type, self._data_source_type, self._default_topic
                )
            else:
                topic = get_topic_for_doc_type(change_meta.document_type, self._data_source_type)
            self._producer.send_change(topic, change_meta)


def get_default_couch_db_change_feed_pillow(pillow_id, **kwargs):
    return get_change_feed_pillow_for_db(pillow_id, CommCareCase.get_db(), topics.CASE)


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
