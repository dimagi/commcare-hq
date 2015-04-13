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


class IterDB(object):
    """
    Bulk save docs in chunks.

        with IterDB(db) as iter_db:
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
            results = cmd(docs)
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
            self.commit_delete()


def iter_update(db, fn, ids):
    """
    Map `fn` over every doc in `db` matching `ids`

    `fn` should accept a json dict from couch and return one of:
     * a json dict (or wrapped couch document) - bulk save that document
     * the string "DELETE" - bulk delete that document
     * None - pass

    iter_update returns an object with the following properties:
    saved_ids, deleted_ids, ignored_ids,

    Ex: mark dimagi users as cool, delete the Canadians, and ignore the rest

        def mark_cool(user_dict):
            user = CommCareUser.wrap(user_dict)
            if user.is_dimagi:
                user.is_cool = True
                return user
            if user.language == "Canadian":
                return "DELETE"

        iter_update(CommCareUser.get_db(), mark_cool, all_user_ids)

    This looks up and saves docs in chunks and is intended for large changes
    such as a migration.  If an id is not found, it is skipped.  In the
    event of a BulkSaveError, it will re-process the unsaved documents.
    Wrapping is optional, and this function will unwrap if needed.
    """
    IterResults = namedtuple('IterResults', ['ignored_ids', 'not_found_ids',
                                             'deleted_ids', 'updated_ids'])
    results = IterResults(set(), set(), set(), set())

    def _iter_update(doc_ids):
        with IterDB(db, chunksize=100) as iter_db:
            for chunk in chunked(set(doc_ids), 100):
                for res in get_docs(db, keys=chunk):
                    raw_doc = res.get('doc')
                    doc_id = res.get('id', None)
                    if not raw_doc or not doc_id:
                        results.not_found_ids.add(res['key'])
                    else:
                        doc = fn(raw_doc)
                        if isinstance(doc, dict):
                            iter_db.save(doc)
                        elif doc == "DELETE":
                            iter_db.delete(raw_doc)
                        else:
                            results.ignored_ids.add(doc_id)

        results.updated_ids.update(iter_db.saved_ids)
        results.deleted_ids.update(iter_db.deleted_ids)

        if iter_db.error_ids:
            _iter_update(iter_db.error_ids)

    _iter_update(ids)
    return results
