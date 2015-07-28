import traceback
import requests
import json
from copy import deepcopy
from collections import defaultdict, namedtuple
from time import sleep
from couchdbkit import ResourceNotFound, BulkSaveError
from django.http import Http404
from jsonobject.exceptions import WrappingAttributeError
from dimagi.utils.chunked import chunked
from dimagi.utils.requestskit import get_auth


class DocumentNotFound(Exception):
    pass


def get_document_or_not_found(cls, domain, doc_id, additional_doc_types=None):
    allowed_doc_types = (additional_doc_types or []) + [cls.__name__]
    try:
        unwrapped = cls.get_db().get(doc_id)
    except ResourceNotFound:
        raise DocumentNotFound("Document {} of class {} not found!".format(
            doc_id,
            cls.__name__
        ))

    if ((unwrapped.get('domain', None) != domain and
         domain not in unwrapped.get('domains', [])) or
        unwrapped['doc_type'] not in allowed_doc_types):

        raise DocumentNotFound("Document {} of class {} not in domain {}!".format(
            doc_id,
            cls.__name__,
            domain,
        ))

    try:
        return cls.wrap(unwrapped)
    except WrappingAttributeError:
        raise DocumentNotFound("Issue wrapping document {} of class {}!".format(
            doc_id,
            cls.__name__
        ))


def get_document_or_404(cls, domain, doc_id, additional_doc_types=None):
    """
    Gets a document and enforces its domain and doc type.
    Raises Http404 if the doc isn't found or domain/doc_type don't match.
    """
    try:
        return get_document_or_not_found(
            cls, domain, doc_id, additional_doc_types=additional_doc_types)
    except DocumentNotFound as e:
        tb = traceback.format_exc()
        raise Http404("{}\n\n{}".format(e, tb))


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
        self.saved_ids = set()
        self.deleted_ids = set()
        self.error_ids = set()
        self.errors_by_type = defaultdict(list)

    def __enter__(self):
        self.to_save = []
        self.to_delete = []
        return self

    def _write(self, cmd, docs):
        try:
            results = cmd(docs)
        except BulkSaveError as e:
            categorized_errors = categorize_bulk_save_errors(e)
            success_ids = {r['id'] for r in categorized_errors.pop(None, [])}
            self.errors_by_type = categorized_errors
            self.error_ids.update(d['id'] for d in e.errors)
        else:
            success_ids = {d['id'] for d in results}

        if self.throttle_secs:
            sleep(self.throttle_secs)
        return success_ids

    def _commit_save(self):
        success_ids = self._write(self.db.bulk_save, self.to_save)
        self.saved_ids.update(success_ids)
        self.to_save = []

    def _commit_delete(self):
        success_ids = self._write(self.db.bulk_delete, self.to_delete)
        self.deleted_ids.update(success_ids)
        self.to_delete = []

    def save(self, doc):
        self.to_save.append(doc)
        if len(self.to_save) >= self.chunksize:
            self._commit_save()

    def delete(self, doc):
        self.to_delete.append(doc)
        if len(self.to_delete) >= self.chunksize:
            self._commit_delete()

    def commit(self):
        if self.to_save:
            self._commit_save()
        if self.to_delete:
            self._commit_delete()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.commit()


class IterUpdateError(Exception):
    def __init__(self, results, *args, **kwargs):
        self.results = results
        super(IterUpdateError, self).__init__(*args, **kwargs)


class DocUpdate(object):
    def __init__(self, doc, delete=False):
        self.doc = doc
        self.delete = delete


def _is_unchanged(doc_or_Document, doc):
    if hasattr(doc_or_Document, 'to_json'):
        new_doc = doc_or_Document.to_json()
    else:
        new_doc = doc_or_Document
    return new_doc == doc


def send_keys_to_couch(db, keys):
    """
    Copied from dimagi-utils get_docs. Returns a response for every key.
    """
    url = db.uri + '/_all_docs'
    r = requests.post(url=url,
                      data=json.dumps({'keys': filter(None, keys)}),
                      headers={'content-type': 'application/json'},
                      auth=get_auth(url),
                      params={'include_docs': 'true'})
    return r.json()['rows']


def iter_update(db, fn, ids, max_retries=3, verbose=False):
    """
    Map `fn` over every doc in `db` matching `ids`

    `fn` should accept a json dict from couch and return an instance of
    DocUpdate or None (which will skip the doc)

    iter_update returns an object with the following properties:
    'ignored_ids', 'not_found_ids', 'deleted_ids', 'updated_ids', 'error_ids'

    Ex: mark dimagi users as cool, delete the Canadians, and ignore the rest

        from corehq.util.couch import iter_update, DocUpdate

        def mark_cool(user_dict):
            user = CommCareUser.wrap(user_dict)
            if user.is_dimagi:
                user.is_cool = True
                return DocUpdate(doc=user)
            if user.language == "Canadian":
                return DocUpdate(doc=user, delete=True)

        iter_update(CommCareUser.get_db(), mark_cool, all_user_ids)

    This looks up and saves docs in chunks and is intended for large changes
    such as a migration.  If an id is not found, it is skipped.  In the
    event of a BulkSaveError, it will re-process the unsaved documents.
    Wrapping is optional, and this function will unwrap if needed.
    """
    fields = ['ignored_ids', 'not_found_ids', 'deleted_ids', 'updated_ids',
              'error_ids']
    IterResults = namedtuple('IterResults', fields)
    results = IterResults(set(), set(), set(), set(), set())

    def _iter_update(doc_ids, try_num):
        with IterDB(db, chunksize=100) as iter_db:
            for chunk in chunked(set(doc_ids), 100):
                for res in send_keys_to_couch(db, keys=chunk):
                    raw_doc = res.get('doc')
                    doc_id = res.get('id', None)
                    if not raw_doc or not doc_id:
                        results.not_found_ids.add(res['key'])
                    else:
                        # copy the dictionary so we can tell if it changed
                        doc_update = fn(deepcopy(raw_doc))
                        if doc_update is None:
                            results.ignored_ids.add(doc_id)
                        elif (not isinstance(doc_update, DocUpdate)
                              or doc_update.doc.get('_id') != doc_id):
                            results.error_ids.add(doc_id)
                        elif doc_update.delete:
                            iter_db.delete(raw_doc)
                        elif not _is_unchanged(doc_update.doc, raw_doc):
                            iter_db.save(doc_update.doc)
                        else:
                            results.ignored_ids.add(doc_id)

        results.updated_ids.update(iter_db.saved_ids)
        results.deleted_ids.update(iter_db.deleted_ids)

        if iter_db.error_ids:
            if try_num >= max_retries:
                results.error_ids.update(iter_db.error_ids)
                msg = ("The following documents did not correctly save:\n" +
                       ", ".join(results.error_ids))
                raise IterUpdateError(results, msg)
            else:
                _iter_update(iter_db.error_ids, try_num + 1)

    _iter_update(ids, 0)
    if results.error_ids:
        msg = ("The following docs didn't correctly save.  Are you sure fn {} "
               "returned either None or an instance of DocUpdate?  Did you "
               "change or remove the '_id' field?".format(fn.__name__) +
               ", ".join(results.error_ids))
        raise IterUpdateError(results, msg)

    if verbose:
        print "couldn't find {} docs".format(len(results.not_found_ids))
        print "ignored {} docs".format(len(results.ignored_ids))
        print "deleted {} docs".format(len(results.deleted_ids))
        print "updated {} docs".format(len(results.updated_ids))
    return results
