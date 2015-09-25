import datetime
from corehq.util.couch import IterDB
from dimagi.utils.couch.database import iter_docs
from dimagi.utils.chunked import chunked
import logging


def filter_doc_ids_by_doc_type(db, doc_ids, doc_types):
    for doc_ids_chunk in chunked(doc_ids, 100):
        keys = [[doc_type, doc_id]
                for doc_id in doc_ids_chunk
                for doc_type in doc_types]
        results = db.view('all_docs/by_doc_type', keys=keys)
        for result in results:
            yield result['id']


def copy_docs(source_db, target_db, doc_ids):
    """
    copy docs from source_db to target_db
    by doc_id

    """
    with IterDB(target_db, new_edits=False) as iter_db:
        for doc in iter_docs(source_db, doc_ids, attachments=True):
            iter_db.save(doc)
    if iter_db.errors_by_type:
        logging.error('errors bulk saving in copy_docs: {!r}'
                      .format(iter_db.errors_by_type))


def delete_docs(target_db, doc_id_rev_pairs):
    """
    delete docs from database by doc _id and _rev
    """
    with IterDB(target_db, new_edits=False) as iter_db:
        for doc_id, doc_rev in doc_id_rev_pairs:
            iter_db.delete({'_id': doc_id, '_rev': doc_rev})
    if iter_db.errors_by_type:
        logging.error('errors bulk saving in delete_docs: {!r}'
                      .format(iter_db.errors_by_type))


class ContinuousReplicator(object):
    def __init__(self, source_db, target_db, doc_types,
                 max_changes_before_commit=10000,
                 max_time_before_commit=datetime.timedelta(hours=1)):
        self.source_db = source_db
        self.target_db = target_db
        self.doc_types = doc_types
        self.max_changes_before_commit = max_changes_before_commit
        self.max_time_before_commit = max_time_before_commit
        self._ids_to_save = None
        self._id_rev_pairs_to_delete = None
        self._reset()

    def _reset(self):
        self._last_commit_time = datetime.datetime.utcnow()
        self._uncommitted_changes_count = 0
        self._ids_to_save = set()
        self._id_rev_pairs_to_delete = set()

    def replicate_change(self, change):
        if change.deleted:
            self._id_rev_pairs_to_delete.add((change.id, change.rev))
        else:
            self._ids_to_save.add(change.id)
        self._uncommitted_changes_count += 1

    def commit(self):
        ids_to_save = filter_doc_ids_by_doc_type(
            self.source_db, self._ids_to_save, self.doc_types)
        copy_docs(self.source_db, self.target_db, ids_to_save)
        delete_docs(self.target_db, self._id_rev_pairs_to_delete)
        self._reset()

    def _get_time_since_last_commit(self):
        return datetime.datetime.utcnow() - self._last_commit_time

    def should_commit(self):
        return (self._uncommitted_changes_count < self.max_changes_before_commit or
                self._get_time_since_last_commit < self.max_time_before_commit)
