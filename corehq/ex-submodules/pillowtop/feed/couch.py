from couchdbkit import ChangesStream
from django.conf import settings
from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.feed.interface import ChangeFeed, Change
from pillowtop.utils import force_seq_int


class CouchChangeFeed(ChangeFeed):

    def __init__(self, couch_db, include_docs, couch_filter=None, extra_couch_view_params=None):
        self._couch_db = couch_db
        self._document_store = CouchDocumentStore(couch_db)
        self._couch_filter = couch_filter
        self._include_docs = include_docs
        self._extra_couch_view_params = extra_couch_view_params or {}

    def iter_changes(self, since, forever):
        extra_args = {'feed': 'continuous'} if forever else {}
        extra_args.update(self._extra_couch_view_params)
        changes_stream = ChangesStream(
            db=self._couch_db,
            heartbeat=True,
            since=since,
            filter=self._couch_filter,
            include_docs=self._include_docs,
            **extra_args
        )
        for couch_change in changes_stream:
            yield change_from_couch_row(couch_change, document_store=self._document_store)

    def get_latest_change_id(self):
        return get_current_seq(self._couch_db)

    def get_current_offsets(self):
        return {self._couch_db.dbname: force_seq_int(self.get_latest_change_id())}

    def get_checkpoint_value(self):
        return str(self.get_latest_change_id())


def change_from_couch_row(couch_change, document_store=None):
    return Change(
        id=couch_change['id'],
        sequence_id=couch_change.get('seq', None),
        document=couch_change.get('doc', None),
        deleted=couch_change.get('deleted', False),
        document_store=document_store,
    )


def get_current_seq(couch_db):
    return couch_db.info()['update_seq']
