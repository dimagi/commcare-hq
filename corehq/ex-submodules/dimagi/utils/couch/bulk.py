from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from collections import defaultdict
import json
import logging
from requests.exceptions import HTTPError
from simplejson import JSONDecodeError

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.undo import DELETED_SUFFIX


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
        self.docs_to_delete = defaultdict(list)
        self.docs_to_save = defaultdict(dict)
        self.post_commit_actions = []

    def add_post_commit_action(self, action):
        self.post_commit_actions.append(action)

    def delete(self, doc):
        self.docs_to_delete[doc.__class__].append(doc)

    def delete_all(self, docs):
        for doc in docs:
            self.delete(doc)

    def save(self, doc):
        cls = doc.__class__
        if not doc.get_id:
            doc._id = uuid.uuid4().hex
        self.docs_to_save[cls][doc.get_id] = doc

    def preview_save(self, cls=None):
        if cls:
            return list(self.docs_to_save[cls].values())
        else:
            return [doc for _cls in self.docs_to_save
                            for doc in self.preview_save(cls=_cls)]

    def commit(self):
        for cls, docs in self.docs_to_delete.items():
            for chunk in chunked(docs, 1000):
                cls.bulk_delete(chunk)

        for cls, doc_map in self.docs_to_save.items():
            docs = list(doc_map.values())
            cls.bulk_save(docs)

        for action in self.post_commit_actions:
            action()

    def __enter__(self):
        self.depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.depth -= 1
        if self.depth == 0 and not exc_type:
            self.commit()


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
