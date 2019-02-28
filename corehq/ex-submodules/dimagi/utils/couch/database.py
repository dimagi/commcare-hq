from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit import ResourceConflict
from couchdbkit.client import Database
from dimagi.ext.couchdbkit import Document
from django.conf import settings
from dimagi.utils.chunked import chunked
from dimagi.utils.couch.bulk import get_docs
from requests.exceptions import RequestException
from time import sleep
import six
from six.moves import range


class DocTypeMismatchException(Exception):
    pass


class DesignDoc(object):
    """Data structure representing a design doc"""
    
    def __init__(self, database, id):
        self.id = id
        self._doc = database.get(id)
        self.name = id.replace("_design/", "")
    
    @property
    def views(self):
        views = []
        if "views" in self._doc:
            for view_name, _ in self._doc["views"].items(): 
                views.append(view_name)
        return views


def get_db(postfix=None):
    """
    Get the couch database.
    """
    # this is a bit of a hack, since it assumes all the models talk to the same
    # db.  that said a lot of our code relies on that assumption.
    # this import is here because of annoying dependencies
    db_url = settings.COUCH_DATABASE
    if postfix:
        db_url = settings.EXTRA_COUCHDB_DATABASES[postfix]
    return Database(db_url, create=True)


def get_design_docs(database):
    design_doc_rows = database.view("_all_docs", startkey="_design/", 
                                    endkey="_design/zzzz")
    ret = []
    for row in design_doc_rows:
        ret.append(DesignDoc(database, row["id"]))
    return ret


def iter_docs(database, ids, chunksize=100, **query_params):
    for doc_ids in chunked(ids, chunksize):
        for doc in get_docs(database, keys=doc_ids, **query_params):
            yield doc


def iter_docs_with_retry(database, ids, chunksize=100, max_attempts=5, **query_params):
    """
    A version of iter_docs that retries fetching documents if the connection
    to couch fails for any reason.

    This is useful for long-running migrations where you don't want a single
    failed request to make the process fail.
    """
    for doc_ids in chunked(ids, chunksize):
        for i in range(max_attempts):
            try:
                result = get_docs(database, keys=doc_ids, **query_params)
                break
            except RequestException:
                if i == (max_attempts - 1):
                    raise
                sleep(30)

        for doc in result:
            yield doc


def iter_bulk_delete(database, ids, chunksize=100, doc_callback=None, wait_time=None,
        max_fetch_attempts=1):
    total_count = 0
    for doc_ids in chunked(ids, chunksize):
        for i in range(max_fetch_attempts):
            try:
                doc_dicts = get_docs(database, keys=doc_ids)
                break
            except RequestException:
                if i == (max_fetch_attempts - 1):
                    raise
                sleep(30)

        if doc_callback:
            for doc in doc_dicts:
                doc_callback(doc)

        total_count += len(doc_dicts)
        database.bulk_delete(doc_dicts)
        if wait_time:
            sleep(wait_time)

    return total_count


def iter_bulk_delete_with_doc_type_verification(database, ids, doc_type, chunksize=100, wait_time=None,
        max_fetch_attempts=1):
    def verify_doc_type(doc):
        actual_doc_type = doc.get('doc_type')
        if actual_doc_type != doc_type:
            raise DocTypeMismatchException("Expected %s, got %s" % (doc_type, actual_doc_type))

    return iter_bulk_delete(database, ids, chunksize=chunksize, doc_callback=verify_doc_type, wait_time=wait_time,
        max_fetch_attempts=max_fetch_attempts)


def is_bigcouch():
    # this is a bit of a hack but we'll use it for now
    return 'cloudant' in settings.COUCH_DATABASE or getattr(settings, 'BIGCOUCH', False)


def bigcouch_quorum_count():
    """
    The number of nodes to force an update/read in bigcouch to make sure
    we have a quorum. Should typically be the number of copies of a doc
    that end up in the cluster.
    """
    return (3 if not hasattr(settings, 'BIGCOUCH_QUORUM_COUNT')
            else settings.BIGCOUCH_QUORUM_COUNT)


def get_safe_write_kwargs():
    return {'w': bigcouch_quorum_count()} if is_bigcouch() else {}


def get_safe_read_kwargs():
    return {'r': bigcouch_quorum_count()} if is_bigcouch() else {}


class SafeSaveDocument(Document):
    """
    A document class that overrides save such that any time it's called in bigcouch
    mode it saves with the maximum quorum count (unless explicitly overridden).
    """
    def save(self, **params):
        if is_bigcouch() and 'w' not in params:
            params['w'] = bigcouch_quorum_count()
        return super(SafeSaveDocument, self).save(**params)


def safe_delete(db, doc_or_id):
    if not isinstance(doc_or_id, six.string_types):
        doc_or_id = doc_or_id._id
    db.delete_doc(doc_or_id, **get_safe_write_kwargs())


def apply_update(doc, update_fn, max_tries=5):
    """
    A function for safely applying a change to a couch doc. For getting around ResourceConflict
    errors that stem from the distributed cloudant nodes
    """
    tries = 0
    while tries < max_tries:
        try:
            update_fn(doc)
            doc.save()
            return doc
        except ResourceConflict:
            doc = doc.__class__.get(doc._id)
        tries += 1
    raise ResourceConflict("Document update conflict. -- Max Retries Reached")
