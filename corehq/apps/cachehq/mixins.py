import logging
from django.conf import settings
from couchdbkit import ResourceNotFound
from corehq.apps.cachehq.invalidate import invalidate_document
from corehq.util.quickcache import skippable_quickcache
from dimagi.utils.couch.cache import cache_core


class _InvalidateCacheMixin(object):
    def clear_caches(self):
        invalidate_document(self, couch_db=self.get_db())

    def save(self, **params):
        try:
            super(_InvalidateCacheMixin, self).save(**params)
        finally:
            self.clear_caches()

    @classmethod
    def save_docs(cls, docs, use_uuids=True, all_or_nothing=False):
        super(_InvalidateCacheMixin, cls).save_docs(docs, use_uuids, all_or_nothing)
        for doc in docs:
            doc.clear_caches()

    def delete(self):
        id = self._id
        try:
            super(_InvalidateCacheMixin, self).delete()
        except ResourceNotFound:
            # it was already deleted. this isn't a problem, but might be a caching bug
            logging.exception('Tried to delete cached doc %s but it was already deleted', id)

        self._doc['_id'] = id
        self.clear_caches()
        invalidate_document(self, couch_db=self.get_db(), deleted=True)


def dont_cache_docs(*args, **kwargs):
    if settings.UNIT_TESTING:
        return False
    return not getattr(settings, 'COUCH_CACHE_DOCS', True)


class QuickCachedDocumentMixin(_InvalidateCacheMixin):
    def clear_caches(self):
        super(QuickCachedDocumentMixin, self).clear_caches()
        if getattr(self, '_id', False):
            self.get.clear(self.__class__, self._id)

    @classmethod
    @skippable_quickcache(['cls.__name__', 'doc_id'], skip_arg=dont_cache_docs)
    def get(cls, doc_id, *args, **kwargs):
        return super(QuickCachedDocumentMixin, cls).get(doc_id, *args, **kwargs)


class CachedCouchDocumentMixin(QuickCachedDocumentMixin):
    """
    A mixin for Documents that's meant to be used to enable generationally cached
    access in front of couch.
    """

    @classmethod
    def view(cls, view_name, wrapper=None, dynamic_properties=None, wrap_doc=True, classes=None, **params):
        wrapper = wrapper or cls.wrap
        if dynamic_properties is None and wrap_doc and classes is None:
            return cache_core.cached_view(cls.get_db(), view_name, wrapper, **params)
        else:
            return super(CachedCouchDocumentMixin, cls).view(
                view_name, wrapper, dynamic_properties, wrap_doc, classes, **params
            )
