import logging
from couchdbkit import ResourceNotFound
from corehq.apps.cachehq.invalidate import invalidate_document
from dimagi.utils.couch.cache import cache_core
from dimagi.utils.couch.cache.cache_core import cached_open_doc


class CachedCouchDocumentMixin(object):
    """
    A mixin for Documents that's meant to be used to enable generationally cached
    access in front of couch.
    """

    def save(self, **params):
        super(CachedCouchDocumentMixin, self).save(**params)
        invalidate_document(self)

    def delete(self):
        id = self._id
        try:
            super(CachedCouchDocumentMixin, self).delete()
        except ResourceNotFound:
            # it was already deleted. this isn't a problem, but might be a caching bug
            logging.exception('Tried to delete cached doc %s but it was already deleted' % id)

        self._doc['_id'] = id
        invalidate_document(self, deleted=True)

    @classmethod
    def get(cls, docid, rev=None, db=None, dynamic_properties=True):
        if rev is None and db is None and dynamic_properties:
            doc_json = cached_open_doc(cls.get_db(), docid)
            return cls.wrap(doc_json)
        else:
            return super(CachedCouchDocumentMixin, cls).get(docid, rev, db, dynamic_properties)

    @classmethod
    def view(cls, view_name, wrapper=None, dynamic_properties=None, wrap_doc=True, classes=None, **params):
        wrapper = wrapper or cls.wrap
        if dynamic_properties is None and wrap_doc and classes is None:
            return cache_core.cached_view(cls.get_db(), view_name, wrapper, **params)
        else:
            return super(CachedCouchDocumentMixin, cls).view(
                view_name, wrapper, dynamic_properties, wrap_doc, classes, **params
            )
