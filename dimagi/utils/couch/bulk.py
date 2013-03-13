from collections import defaultdict
import json
import logging
import requests
from dimagi.utils.requestskit import get_auth


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

    def delete(self, doc):
        self.docs_to_delete[doc.__class__].append(doc)

    def delete_all(self, docs):
        for doc in docs:
            self.delete(doc)

    def save(self, doc):
        cls = doc.__class__
        if not doc.get_id:
            doc._id = cls.get_db().server.next_uuid()
        self.docs_to_save[cls][doc.get_id] = doc

    def preview_save(self, cls=None):
        if cls:
            return self.docs_to_save[cls].values()
        else:
            return [doc for _cls in self.docs_to_save.keys()
                            for doc in self.preview_save(cls=_cls)]

    def commit(self):
        for cls, docs in self.docs_to_delete.items():
            cls.get_db().bulk_delete(docs)

        for cls, doc_map in self.docs_to_save.items():
            docs = doc_map.values()
            cls.bulk_save(docs)

    def __enter__(self):
        self.depth += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.depth -= 1
        if self.depth == 0 and not exc_type:
            self.commit()


def get_docs(db, keys):
    payload = json.dumps({'keys': keys})
    url = db.uri + '/_all_docs?include_docs=true'

    r = requests.post(url, data=payload,
                      headers={'content-type': 'application/json'},
                      auth=get_auth(url))

    try:
        return r.json()['rows']
    except KeyError:
        logging.exception('%r has no key %r' % (r.json(), 'rows'))
        raise


def wrapped_docs(cls, keys):
    rows = get_docs(cls.get_db(), keys)
    for row in rows:
        yield cls.wrap(row['doc'])
