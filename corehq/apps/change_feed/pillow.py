from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import data_sources
from corehq.apps.change_feed.connection import get_kafka_client_or_none
from corehq.apps.change_feed.document_types import get_doc_meta_object_from_document, \
    change_meta_from_doc_meta_and_document
from corehq.apps.change_feed.exceptions import MissingMetaInformationError
from corehq.apps.change_feed.producer import ChangeProducer
from corehq.apps.change_feed.topics import get_topic
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.util.couchdb_management import couch_config
from corehq.util.soft_assert import soft_assert
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.feed.couch import CouchChangeFeed
from pillowtop.pillow.interface import ConstructedPillow
from pillowtop.processors import PillowProcessor


class KafkaProcessor(PillowProcessor):
    """
    Processor that pushes changes to Kafka
    """
    def __init__(self, kafka, data_source_type, data_source_name):
        self._kafka = kafka
        self._producer = ChangeProducer(self._kafka)
        self._data_source_type = data_source_type
        self._data_source_name = data_source_name

    def process_change(self, pillow_instance, change, do_set_checkpoint=False):
        try:
            doc_meta = get_doc_meta_object_from_document(change.document)
            change_meta = change_meta_from_doc_meta_and_document(
                doc_meta=doc_meta,
                document=change.document,
                data_source_type=self._data_source_type,
                data_source_name=self._data_source_name,
                doc_id=change.id,
            )
        except MissingMetaInformationError:
            pass
        else:
            # change.deleted is used for hard deletions, from which we don't currently
            # get any metadata from so this should have raised a MissingMetaInformationError above
            _assert = soft_assert(to='@'.join(['czue', 'dimagi.com']), send_to_ops=False)
            _assert(not change.deleted, u'change {} (meta: {}) should not have been deleted but was.'.format(
                change,
                change_meta.to_json()
            ))
            self._producer.send_change(get_topic(doc_meta), change_meta)


def get_default_couch_db_change_feed_pillow(pillow_id):
    return get_change_feed_pillow_for_db(pillow_id, CommCareCase.get_db())


def get_user_groups_db_kafka_pillow(pillow_id):
    return get_change_feed_pillow_for_db(pillow_id, couch_config.get_db_for_class(CommCareUser))


def get_domain_db_kafka_pillow(pillow_id):
    return get_change_feed_pillow_for_db(pillow_id, couch_config.get_db_for_class(Domain))


def get_change_feed_pillow_for_db(pillow_id, couch_db):
    kafka_client = get_kafka_client_or_none()
    processor = KafkaProcessor(
        kafka_client, data_source_type=data_sources.COUCH, data_source_name=couch_db.dbname
    )
    checkpoint = PillowCheckpoint(pillow_id)
    return ConstructedPillow(
        name=pillow_id,
        checkpoint=checkpoint,
        change_feed=CouchChangeFeed(couch_db, include_docs=True),
        processor=processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )
