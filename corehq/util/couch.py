from collections import defaultdict, namedtuple
from time import sleep
from couchdbkit import ResourceNotFound, BulkSaveError
from django.http import Http404
from jsonobject.exceptions import WrappingAttributeError
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import get_docs


def get_document_or_404(cls, domain, doc_id, additional_doc_types=None):
    """
    Gets a document and enforces its domain and doc type.
    Raises Http404 if the doc isn't found or domain/doc_type don't match.
    """
    allowed_doc_types = (additional_doc_types or []) + [cls.__name__]
    try:
        unwrapped = cls.get_db().get(doc_id)
    except ResourceNotFound:
        raise Http404()

    if ((unwrapped.get('domain', None) != domain and
         domain not in unwrapped.get('domains', [])) or
        unwrapped['doc_type'] not in allowed_doc_types):
        raise Http404()

    try:
        return cls.wrap(unwrapped)
    except WrappingAttributeError:
        raise Http404()


def categorize_bulk_save_errors(error):
    result_map = defaultdict(list)
    for result in error.results:
        error = result.get('error', None)
        result_map[error].append(result)

    return result_map


class IterativeSaver(object):
    """
    Bulk save docs in chunks.

        with IterativeSaver(db) as iter_db:
            for doc in iter_docs(db, ids):
                iter_db.save(doc)

        iter_db.error_ids  # docs that errored
        iter_db.saved_ids  # docs that saved correctly
    """
    def __init__(self, database, chunksize=100, throttle_secs=None):
        self.db = database
        self.chunksize = chunksize
        self.throttle_secs = throttle_secs
        self.saved_ids = []
        self.deleted_ids = []
        self.error_ids = []

    def __enter__(self):
        self.to_save = []
        self.to_delete = []
        return self

    def commit(self, cmd, docs):
        try:
            results = self.db.bulk_save(docs)
        except BulkSaveError as e:
            results = e.results
            error_ids = {d['id'] for d in e.errors}
            self.error_ids.extend(error_ids)
            success_ids = [d['id'] for d in results
                           if d['id'] not in error_ids]
        else:
            success_ids = [d['id'] for d in results]

        if self.throttle_secs:
            sleep(self.throttle_secs)
        return success_ids

    def commit_save(self):
        success_ids = self.commit(self.db.bulk_save, self.to_save)
        self.saved_ids.extend(success_ids)
        self.to_save = []

    def commit_delete(self):
        success_ids = self.commit(self.db.bulk_delete, self.to_delete)
        self.deleted_ids.extend(success_ids)
        self.to_delete = []

    def save(self, doc):
        self.to_save.append(doc)
        if len(self.to_save) >= self.chunksize:
            self.commit_save()

    def delete(self, doc):
        self.to_delete.append(doc)
        if len(self.to_delete) >= self.chunksize:
            self.commit_delete()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.to_save:
            self.commit_save()
        if self.to_delete:
            self.commit_delet()
