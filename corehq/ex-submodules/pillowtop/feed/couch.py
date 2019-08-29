from couchdbkit import ChangesStream
from pillowtop.dao.couch import CouchDocumentStore
from pillowtop.feed.interface import ChangeFeed, Change
from pillowtop.utils import force_seq_int


class CouchChangeFeed(ChangeFeed):

    def __init__(self, couch_db, couch_filter=None, extra_couch_view_params=None):
        self._couch_db = couch_db
        self._document_store = CouchDocumentStore(couch_db)
        self._couch_filter = couch_filter
        self._extra_couch_view_params = extra_couch_view_params or {}
        self._last_processed_seq = None

    def iter_changes(self, since, forever):
        from corehq.apps.change_feed.data_sources import SOURCE_COUCH
        extra_args = {'feed': 'continuous'} if forever else {}
        extra_args.update(self._extra_couch_view_params)
        if self._couch_filter:
            extra_args.update({'filter': self._couch_filter})
        self._last_processed_seq = since
        changes_stream = ChangesStream(
            db=self._couch_db,
            since=since,
            include_docs=True,
            **extra_args
        )
        for couch_change in changes_stream:
            change = change_from_couch_row(couch_change, document_store=self._document_store)
            populate_change_metadata(change, SOURCE_COUCH, self._couch_db.dbname)
            yield change
            self._last_processed_seq = couch_change.get('seq', None)

    def get_processed_offsets(self):
        return {self._couch_db.dbname: force_seq_int(self._last_processed_seq)}

    def get_latest_offsets(self):
        return {self._couch_db.dbname: force_seq_int(get_current_seq(self._couch_db))}

    def get_latest_offsets_as_checkpoint_value(self):
        return str(get_current_seq(self._couch_db))

    @property
    def couch_db(self):
        return self._couch_db


def change_from_couch_row(couch_change, document_store=None):
    return Change(
        id=couch_change['id'],
        sequence_id=couch_change.get('seq', None),
        document=couch_change.get('doc', None),
        deleted=couch_change.get('deleted', False),
        document_store=document_store,
    )


def populate_change_metadata(change, data_source_type, data_source_name):
    from corehq.apps.change_feed.exceptions import MissingMetaInformationError
    from corehq.apps.change_feed.document_types import get_doc_meta_object_from_document
    from corehq.apps.change_feed.document_types import change_meta_from_doc_meta_and_document

    if change.metadata:
        return

    try:
        document = change.get_document()
        doc_meta = get_doc_meta_object_from_document(document)
        change_meta = change_meta_from_doc_meta_and_document(
            doc_meta=doc_meta,
            document=document,
            data_source_type=data_source_type,
            data_source_name=data_source_name,
            doc_id=change.id,
        )
    except MissingMetaInformationError:
        pass
    else:
        change.metadata = change_meta


def get_current_seq(couch_db):
    return couch_db.info()['update_seq']
