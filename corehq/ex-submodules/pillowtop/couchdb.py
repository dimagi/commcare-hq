from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit import Database


class CachedCouchDB(Database):
    """
    A couchdb implementation that supports preloading a cache and a bit of
    additional controls on top of that.

    This is useful when you need to iterate through some thing one at a time
    but want to get gains of bulk-loading documents.

    The specific use case is python-filtered pillows and fast reindexing.
    """

    def __init__(self, uri, readonly):
        super(CachedCouchDB, self).__init__(uri)
        self._docs = {}
        self.readonly = readonly

    def get_all(self):
        """
        Gets all docs currently in the cache.
        """
        return list(self._docs.values())

    def doc_exist(self, doc_id):
        return doc_id in self._docs or super(CachedCouchDB, self).doc_exist(doc_id)

    def open_doc(self, doc_id, check_main=True):
        doc = self._docs.get(doc_id)
        if not doc and check_main:
            doc = super(CachedCouchDB, self).open_doc(doc_id)
            self._docs[doc_id] = doc

        return doc

    def save_doc(self, doc):
        if self.readonly:
            raise NotImplementedError("Can't save doc, this is just a loader class")
        else:
            super(CachedCouchDB, self).save_doc(doc)
            self._docs[doc['_id']] = doc

    def bulk_load(self, doc_ids, purge_existing=True):
        """
        A non overriding method - bulk load a bunch of documents so they can be
        efficiently retrieved later.
        """
        if purge_existing:
            del self._docs
            self._docs = {}

        docs = self.all_docs(keys=doc_ids, include_docs=True)
        self._docs.update({x['id']: x['doc'] for x in docs if 'id' in x and x['doc']})
