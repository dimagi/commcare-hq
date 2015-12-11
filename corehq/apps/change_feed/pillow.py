import json
from kafka import KeyedProducer
from kafka.common import KafkaUnavailableError
from casexml.apps.case.models import CommCareCase
from corehq.apps.change_feed import data_sources
from corehq.apps.change_feed.connection import get_kafka_client
from corehq.apps.change_feed.topics import get_topic
from couchforms.models import all_known_formlike_doc_types
import logging
from pillowtop.checkpoints.manager import PillowCheckpoint, get_django_checkpoint_store
from pillowtop.couchdb import CachedCouchDB
from pillowtop.feed.interface import ChangeMeta
from pillowtop.listener import PythonPillow


class ChangeFeedPillow(PythonPillow):

    def __init__(self, couch_db, kafka, checkpoint):
        super(ChangeFeedPillow, self).__init__(couch_db=couch_db, checkpoint=checkpoint, chunk_size=10)
        self._kafka = kafka
        self._producer = KeyedProducer(self._kafka)

    def get_db_name(self):
        return self.get_couch_db().dbname

    def process_change(self, change, is_retry_attempt=False):
        document_type = _get_document_type(change.document)
        if document_type:
            assert change.document is not None
            change_meta = ChangeMeta(
                document_id=change.id,
                data_source_type=data_sources.COUCH,
                data_source_name=self.get_db_name(),
                document_type=document_type,
                document_subtype=_get_document_subtype(change.document),
                domain=change.document.get('domain', None),
                is_deletion=change.deleted,
            )
            self._producer.send_messages(
                bytes(get_topic(document_type)),
                bytes(change_meta.domain),
                bytes(json.dumps(change_meta.to_json())),
            )


def get_default_couch_db_change_feed_pillow():
    default_couch_db = CachedCouchDB(CommCareCase.get_db().uri, readonly=False)
    try:
        kafka_client = get_kafka_client()
    except KafkaUnavailableError:
        logging.warning('Ignoring missing kafka client during unit testing')
        kafka_client = None

    return ChangeFeedPillow(
        couch_db=default_couch_db,
        kafka=kafka_client,
        checkpoint=PillowCheckpoint(get_django_checkpoint_store(), 'default-couch-change-feed')
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
