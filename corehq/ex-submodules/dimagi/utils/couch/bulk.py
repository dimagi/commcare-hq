from __future__ import absolute_import
import uuid
from collections import defaultdict
import json
import logging
import requests
from requests.exceptions import HTTPError
from simplejson import JSONDecodeError

from dimagi.utils.chunked import chunked
from dimagi.utils.couch.undo import DELETED_SUFFIX
from dimagi.utils.requestskit import get_auth


class BulkFetchException(Exception):
    pass


class CouchTransaction(object):
    """
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
            cls.bulk_delete(docs)

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
    r = requests.post(url, data=payload,
                      headers={'content-type': 'application/json'},
                      auth=get_auth(url),
                      params=query_params)

    try:
        r.raise_for_status()
        return [row.get('doc') for row in r.json()['rows'] if row.get('doc')]
    except KeyError:
        logging.exception('%r has no key %r' % (r.json(), 'rows'))
        raise
    except (HTTPError, JSONDecodeError) as e:
        raise BulkFetchException(e)


def wrapped_docs(cls, keys):
    docs = get_docs(cls.get_db(), keys)
    for doc in docs:
        yield cls.wrap(doc)


def soft_delete_docs(all_docs, cls, doc_type=None):
    """
    Adds the '-Deleted' suffix to all the docs passed in.
    docs - the docs to soft delete, should be dictionary (json) and not objects
    cls - the class of the docs
    doc_type - doc type of the docs, defaults to cls.__name__
    """
    doc_type = doc_type or cls.__name__
    for docs in chunked(all_docs, 50):
        docs_to_save = []
        for doc in docs:
            if doc.get('doc_type', '') != doc_type:
                continue
            doc['doc_type'] += DELETED_SUFFIX
            docs_to_save.append(doc)
        cls.get_db().bulk_save(docs_to_save)
