from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import data_sources
from corehq.apps.change_feed.connection import get_kafka_client_or_none
from corehq.apps.change_feed.producer import ChangeProducer
from corehq.apps.change_feed.topics import get_topic
from corehq.apps.users.models import CommCareUser
from corehq.util.couchdb_management import couch_config
from couchforms.models import all_known_formlike_doc_types
from pillowtop.checkpoints.manager import PillowCheckpoint, PillowCheckpointEventHandler
from pillowtop.couchdb import CachedCouchDB
from pillowtop.feed.couch import CouchChangeFeed
from pillowtop.feed.interface import ChangeMeta
from pillowtop.listener import PythonPillow
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
        document_type = _get_document_type(change.document)
        if document_type:
            assert change.document is not None
            change_meta = ChangeMeta(
                document_id=change.id,
                data_source_type=self._data_source_type,
                data_source_name=self._data_source_name,
                document_type=document_type,
                document_subtype=_get_document_subtype(change.document),
                domain=change.document.get('domain', None),
                is_deletion=change.deleted,
            )
            self._producer.send_change(get_topic(document_type), change_meta)


class ChangeFeedPillow(PythonPillow):

    def __init__(self, couch_db, kafka, checkpoint):
        super(ChangeFeedPillow, self).__init__(couch_db=couch_db, checkpoint=checkpoint, chunk_size=10)
        self._processor = KafkaProcessor(
            kafka, data_source_type=data_sources.COUCH, data_source_name=self.get_db_name()
        )

    def get_db_name(self):
        return self.get_couch_db().dbname

    def process_change(self, change, is_retry_attempt=False):
        self._processor.process_change(self, change)


def get_default_couch_db_change_feed_pillow():
    default_couch_db = CachedCouchDB(CommCareCase.get_db().uri, readonly=False)
    kafka_client = get_kafka_client_or_none()
    return ChangeFeedPillow(
        couch_db=default_couch_db,
        kafka=kafka_client,
        checkpoint=PillowCheckpoint('default-couch-change-feed')
    )


def get_user_groups_db_kafka_pillow():
    # note: this is temporarily using ConstructedPillow as a test. If it is successful we should
    # flip the main one over as well
    user_groups_couch_db = couch_config.get_db_for_class(CommCareUser)
    pillow_name = 'UserGroupsDbKafkaPillow'
    kafka_client = get_kafka_client_or_none()
    processor = KafkaProcessor(
        kafka_client, data_source_type=data_sources.COUCH, data_source_name=user_groups_couch_db.dbname
    )
    checkpoint = PillowCheckpoint(pillow_name)
    return ConstructedPillow(
        name=pillow_name,
        document_store=None,  # because we're using include_docs we can be explicit about not using this
        checkpoint=checkpoint,
        change_feed=CouchChangeFeed(user_groups_couch_db, include_docs=True),
        processor=processor,
        change_processed_event_handler=PillowCheckpointEventHandler(
            checkpoint=checkpoint, checkpoint_frequency=100,
        ),
    )


def _get_document_type(document_or_none):
    return document_or_none.get('doc_type', None) if document_or_none else None


def _get_document_subtype(document_or_none):
    type = _get_document_type(document_or_none)
    if type in ('CommCareCase', 'CommCareCase-Deleted'):
        return document_or_none.get('type', None)
    elif type in all_known_formlike_doc_types():
        return document_or_none.get('xmlns', None)
    return None
