import json
import traceback
from collections import defaultdict, namedtuple
from copy import deepcopy
from functools import partial
from time import sleep

from couchdbkit import ResourceNotFound, BulkSaveError, Document
from django.conf import settings
from django.http import Http404
from jsonobject.exceptions import WrappingAttributeError

from corehq.util.exceptions import DocumentClassNotFound
from dimagi.utils.chunked import chunked
from memoized import memoized


class DocumentNotFound(Exception):
    pass


def get_document_or_not_found_lite(cls, doc_id):
    """
    Like `get_document_or_not_found` but without domain/doc_type checks.
    """
    return cls.wrap(_get_document_or_not_found_lite(cls, doc_id))


def _get_document_or_not_found_lite(cls, doc_id):
    """
    Returns an unwrapped document if it exists, or raises `DocumentNotFound` if not
    """
    try:
        return cls.get_db().get(doc_id)
    except ResourceNotFound:
        raise DocumentNotFound("Document {} of class {} not found!".format(
            doc_id,
            cls.__name__
        ))


def get_document_or_not_found(cls, domain, doc_id, additional_doc_types=None):
    allowed_doc_types = (additional_doc_types or []) + [cls.__name__]
    unwrapped = _get_document_or_not_found_lite(cls, doc_id)
    if ((unwrapped.get('domain', None) != domain and domain not in unwrapped.get('domains', []))
       or unwrapped['doc_type'] not in allowed_doc_types):
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
        raise Http404("{}\n\n{}".format(e, traceback.format_exc()))


@memoized
def get_classes_by_doc_type():
    queue = [Document]
    classes_by_doc_type = {}
    while queue:
        klass = queue.pop()
        try:
            klass._meta.app_label
        except AttributeError:
            # exclude abstract base classes (which don't have an app_label)
            pass
        else:
            # a base class (e.g. CommCareCase) wins over a subclass (e.g. SupplyPointCase)
            if klass._doc_type not in classes_by_doc_type:
                classes_by_doc_type[klass._doc_type] = klass
        queue.extend(klass.__subclasses__())
    return classes_by_doc_type


def get_document_class_by_doc_type(doc_type):
    """
    Given the doc_type of a document class, get the class itself.

    Raises a DocumentClassNotFound if not found
    """

    try:
        return get_classes_by_doc_type()[doc_type]
    except KeyError:
        raise DocumentClassNotFound(
            'No Document class with name "{}" could be found.'.format(doc_type))


def get_db_by_doc_type(doc_type):
    """
    Lookup a database by document type. Returns None if the database is not found.
    """
    try:
        return get_document_class_by_doc_type(doc_type).get_db()
    except DocumentClassNotFound:
        return None


def categorize_bulk_save_errors(error):
    result_map = defaultdict(list)
    for result in error.results:
        error = result.get('error', None)
        result_map[error].append(result)

    return result_map


class IterDBCallback(object):

    def post_commit(self, operation, committed_docs, success_ids, errors):
        """
        :param operation: 'save' or 'delete'
        :param committed_docs: List of all docs in this commit operation
        :param success_ids: List of IDs that were processed successfully
        :param errors: List of error dictionaries with keys: ('id', 'reason', 'error'
        """
        pass


class IterDB(object):
    """
    Bulk save docs in chunks.

        with IterDB(db) as iter_db:
            for doc in iter_docs(db, ids):
                iter_db.save(doc)

        iter_db.error_ids  # docs that errored
        iter_db.saved_ids  # docs that saved correctly

    `new_edits` param will be passed directly to db.bulk_save
    """

    def __init__(self, database, chunksize=100, throttle_secs=None,
                 new_edits=None, callback=None):
        self.db = database
        self.chunksize = chunksize
        self.throttle_secs = throttle_secs
        self.saved_ids = set()
        self.deleted_ids = set()
        self.error_ids = set()
        self.errors_by_type = defaultdict(list)
        self.new_edits = new_edits
        self.callback = callback

    def __enter__(self):
        self.to_save = []
        self.to_delete = []
        return self

    def _write(self, op_slug, cmd, docs):
        categorized_errors = {}
        try:
            results = cmd(docs)
        except BulkSaveError as e:
            categorized_errors = categorize_bulk_save_errors(e)
            for error_type, errors in categorized_errors.items():
                self.errors_by_type[error_type].extend(errors)
            error_ids = {d['id'] for d in e.errors}
            self.error_ids.update(error_ids)
            if not self.new_edits:
                # only errors returned in this mode
                success_ids = {doc['_id'] for doc in docs if doc['_id'] not in error_ids}
            else:
                success_ids = {r['id'] for r in categorized_errors.pop(None, [])}
        else:
            if self.new_edits or self.new_edits is None:
                success_ids = {d['id'] for d in results}
            else:
                # only errors returned in this mode
                success_ids = {d['_id'] for d in docs}

        if self.callback:
            self.callback.post_commit(op_slug, docs, success_ids, list(categorized_errors.values()))

        if self.throttle_secs:
            sleep(self.throttle_secs)
        return success_ids

    def _commit_save(self):
        bulk_save = partial(self.db.bulk_save, new_edits=self.new_edits)
        success_ids = self._write('save', bulk_save, self.to_save)
        self.saved_ids.update(success_ids)
        self.to_save = []

    def _commit_delete(self):
        success_ids = self._write('delete', self.db.bulk_delete, self.to_delete)
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
    rsession = db._request_session
    r = rsession.post(url=url,
                      data=json.dumps({'keys': [_f for _f in keys if _f]}),
                      headers={'content-type': 'application/json'},
                      params={'include_docs': 'true'})
    return r.json()['rows']


def iter_update(db, fn, ids, max_retries=3, verbose=False, chunksize=100):
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

    def _get_updated_doc_id(doc_update):
        if isinstance(doc_update.doc, dict):
            updated_doc_id = doc_update.doc.get('_id')
        else:
            updated_doc_id = doc_update.doc._id
        return updated_doc_id

    def _iter_update(doc_ids, try_num):
        with IterDB(db, chunksize=chunksize) as iter_db:
            for chunk in chunked(doc_ids, chunksize):
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
                              or _get_updated_doc_id(doc_update) != doc_id):
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
                msg = ("The following documents did not correctly save:\n"
                       + ", ".join(results.error_ids))
                raise IterUpdateError(results, msg)
            else:
                _iter_update(iter_db.error_ids, try_num + 1)

    _iter_update(ids, 0)
    if results.error_ids:
        msg = ("The following docs didn't correctly save.  Are you sure fn {} "
               "returned either None or an instance of DocUpdate?  Did you "
               "change or remove the '_id' field?".format(fn.__name__)
               + ", ".join(results.error_ids))
        raise IterUpdateError(results, msg)

    if verbose:
        print("couldn't find {} docs".format(len(results.not_found_ids)))
        print("ignored {} docs".format(len(results.ignored_ids)))
        print("deleted {} docs".format(len(results.deleted_ids)))
        print("updated {} docs".format(len(results.updated_ids)))
    return results


def stale_ok():
    return settings.COUCH_STALE_QUERY


def bulk_get_revs(target_db, doc_ids):
    """
    return (_id, _rev) for every existing doc in doc_ids
    if a doc id is not found in target_db, it is excluded from the result
    """
    result = target_db.all_docs(keys=list(doc_ids)).all()
    return [(row['id'], row['value']['rev']) for row in result if not row.get('error')]


def get_revisions_info(db, doc_id):
    """
    :return: a list of revisions ordered newest to oldest.  Eg:
    [{'rev': '3-583f2b050fc2099775b5a6ee573c0822', 'status': 'available'},
     {'rev': '2-1584c6ba63613203ae5aa03bdf34fa9e', 'status': 'available'},
     {'rev': '1-73ce55ebe921edf14e37a144706b1070', 'status': 'missing'}]
    """
    return db._request_session.get(
        url=f'{db.uri}/{doc_id}',
        params={'revs_info': 'true'}
    ).json()['_revs_info']


def get_old_rev(db, doc_id, rev):
    return db._request_session.get(
        url=f'{db.uri}/{doc_id}',
        params={'rev': rev}
    ).json()


def iter_old_doc_versions(db, doc_id):
    """
    Returns an generator of old versions of the document
    Note that there may be unavailable old revisions not included
    """
    for rev in get_revisions_info(db, doc_id):
        if rev['status'] == 'available':
            yield get_old_rev(db, doc_id, rev['rev'])
