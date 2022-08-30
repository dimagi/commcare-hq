import json
import logging
from collections import defaultdict
from contextlib import ExitStack
from functools import partial

from django.db.transaction import atomic
from requests.exceptions import HTTPError
from simplejson import JSONDecodeError

from couchdbkit import BulkSaveError
from dimagi.utils.chunked import chunked

from .migration import SyncCouchToSQLMixin, SyncSQLToCouchMixin


class BulkFetchException(Exception):
    pass


class CouchTransaction(object):
    """
    Do not use this class. There is no such thing as a transaction in CouchDB.
    This class can fail during delete, leaving only some rows deleted.
    This class can fail after delete and before saves, leaving everything deleted.
    This class can fail during save, leaving some rows saved, some not.
    This class can fail after save but before post commit actions, leaving your code in an uncertain state.
    There is no cleanup behavior here other than throwing an exception in any of these.
    The exception does not give you enough information to recover.

    https://docs.couchdb.org/en/stable/api/database/bulk-api.html?highlight=_bulk_docs#api-db-bulk-docs-semantics

    Helper for saving up a bunch of saves and deletes of couch docs
    and then committing them all at once with a few bulk operations

    ex:
        with CouchTransaction() as transaction:
            for doc in docs:
                transaction.save(doc)
                other = Other.get(doc.other_id)
                other.name = ''
                transaction.save(other)

    etc. This will do one bulk save per doc type, rather than one save per
    call save call.

    If an exception is raised during the body of the with statement,
    no changes are commited to the db.

    If the same transaction is used in multiple embedded with statements,
    it will only be commited on successful exit of the outermost one. This lets
    you do something like:

        def save_stuff(stuff, transaction=None):
            with transaction or CouchTransaction() as transaction:
                # save all the stuff

    and call this function either with no transaction or have it cooperate
    with an ongoing transaction that you pass in.
    """
    def __init__(self):
        self.depth = 0
        self.docs_to_delete = defaultdict(set)
        self.docs_to_save = defaultdict(set)
        self.sql_save_actions = {}
        self.post_commit_actions = []

    def add_post_commit_action(self, action):
        self.post_commit_actions.append(action)

    def delete(self, doc):
        self.docs_to_delete[doc.__class__].add(doc)

    def delete_all(self, docs):
        for doc in docs:
            self.delete(doc)

    def save(self, doc):
        cls = doc.__class__
        if cls in self.sql_save_actions and issubclass(cls, SyncSQLToCouchMixin):
            raise TypeError("Updated SQL objects must be returned by save "
                f"action ({self.sql_save_actions[cls]}), not added to "
                "the transaction with CouchTransaction.save()")
        self.docs_to_save[cls].add(doc)

    def set_sql_save_action(self, doc_class, action):
        """Set action callback to perform instead of bulk SQL insert

        This must be used when updating existing documents since it is
        not possible for the transaction to efficiently apply updates to
        large numbers of existing SQL rows.

        When `doc_class` is a subclass of `SyncSQLToCouchMixin` the
        action must return a list of saved model objects, which will be
        used to construct Couch documents to be persisted with
        `Document.bulk_save()`.
        """
        if doc_class in self.sql_save_actions:
            raise TypeError(f"Save action already set for {doc_class.__name__}")
        if issubclass(doc_class, SyncSQLToCouchMixin) and self.docs_to_save.get(doc_class):
            raise TypeError("Unexpected docs to save:"
                f"{self.docs_to_save[doc_class]}. Updated SQL objects must be "
                "returned by save action, not added to the transaction with "
                "CouchTransaction.save()")
        self.docs_to_save.setdefault(doc_class, set())
        self.sql_save_actions[doc_class] = action

    def commit(self):
        def start_sql_transaction():
            nonlocal started
            if not started:
                context.enter_context(atomic())
                started = True
        started = False
        with ExitStack() as context:
            self._commit(start_sql_transaction)

    def _commit(self, start_sql_transaction):
        for cls, docs in self.docs_to_delete.items():
            if issubclass(cls, SyncCouchToSQLMixin):
                def delete(chunk):
                    start_sql_transaction()
                    ids = [doc._id for doc in chunk if doc._id]
                    _bulk_delete(cls, chunk)
                    sql_class.objects.filter(**{id_name + "__in": ids}).delete()
                sql_class = cls._migration_get_sql_model_class()
                id_name = sql_class._migration_couch_id_name
            elif issubclass(cls, SyncSQLToCouchMixin):
                raise NotImplementedError(cls)
            else:
                delete = partial(_bulk_delete, cls)
            for chunk in chunked(docs, 1000):
                delete(chunk)

        for cls, docs in self.docs_to_save.items():
            if cls in self.sql_save_actions:
                start_sql_transaction()
                saved_docs = self.sql_save_actions[cls]()
                if issubclass(cls, SyncSQLToCouchMixin):
                    assert not docs, (docs, saved_docs)
                    docs = _iter_couch_docs(cls, saved_docs)
                    save = cls._migration_get_couch_model_class().bulk_save
                else:
                    save = cls.bulk_save
            elif issubclass(cls, SyncCouchToSQLMixin) and cls not in self.sql_save_actions:
                def save(chunk):
                    if any(doc._rev is not None for doc in chunk):
                        raise NotImplementedError("Cannot update "
                            f"{cls.__name__}. Use CouchTransaction."
                            "set_sql_save_action() to update objects in bulk.")
                    cls.bulk_save(chunk)
                    start_sql_transaction()
                    cls._migration_bulk_sync_to_sql(chunk)
            elif issubclass(cls, SyncSQLToCouchMixin):
                def save(chunk):
                    if any(not obj._state.adding for obj in chunk):
                        raise NotImplementedError("Cannot update "
                            f"{cls.__name__}. Use CouchTransaction."
                            "set_sql_save_action() to update objects in bulk.")
                    start_sql_transaction()
                    cls.objects.bulk_create(chunk)
                    couch_class = cls._migration_get_couch_model_class()
                    new_couch_docs = list(_iter_couch_docs(cls, chunk))
                    couch_class.bulk_save(new_couch_docs)
            else:
                save = cls.bulk_save
            for chunk in chunked(docs, 1000, list):
                save(chunk)

        for action in self.post_commit_actions:
            action()

    def __enter__(self):
        self.depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.depth -= 1
        if self.depth == 0 and not exc_type:
            self.commit()


def _iter_couch_docs(cls, sql_objects):
    couch_class = cls._migration_get_couch_model_class()
    for obj in sql_objects:
        doc = couch_class(_id=obj._migration_couch_id)
        assert doc._id is not None, obj
        obj._migration_sync_to_couch(doc, save=False)
        yield doc


def _bulk_delete(cls, chunk):
    try:
        cls.bulk_delete(chunk)
    except BulkSaveError as err:
        if not _was_deleted(err, cls.get_db()):
            raise


def _was_deleted(bulk_save_error, db):
    def is_conflict(error):
        return error.get("error") == "conflict" and "id" in error

    def is_deleted(result):
        return "value" in result and result["value"].get("deleted")

    return (all(is_conflict(e) for e in bulk_save_error.errors)
        and all(is_deleted(r) for r in db.view(
            "_all_docs",
            keys=[e["id"] for e in bulk_save_error.errors]
        )))


def get_docs(db, keys, **query_params):
    if not keys:
        return []

    payload = json.dumps({'keys': [_f for _f in keys if _f]})
    url = db.uri + '/_all_docs'
    query_params['include_docs'] = True

    query_params = {k: json.dumps(v) for k, v in query_params.items()}
    rsession = db._request_session
    r = rsession.post(url, data=payload,
                      headers={'content-type': 'application/json'},
                      params=query_params)

    try:
        r.raise_for_status()
        return [row.get('doc') for row in r.json()['rows'] if row.get('doc')]
    except KeyError:
        logging.exception('%r has no key %r' % (r.json(), 'rows'))
        raise
    except (HTTPError, JSONDecodeError) as e:
        raise BulkFetchException(e)
