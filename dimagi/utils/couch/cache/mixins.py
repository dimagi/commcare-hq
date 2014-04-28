from django.core.cache import cache


CACHE_PREFIX = 'COUCH_DOCUMENT_CACHE'
CACHE_TIMEOUT = 30 * 60


class CachedCouchDocumentMixin(object):
    """
    A mixin for Documents that's meant to be used to enable cached access in front of couch.
    """

    def save(self, **params):
        ret = super(CachedCouchDocumentMixin, self).save(**params)
        cache.delete(self._key(self._id))
        return ret

    @classmethod
    def get(cls, docid, rev=None, db=None, dynamic_properties=True):
        def _super():
            return super(CachedCouchDocumentMixin, cls).get(docid, rev, db, dynamic_properties)
        if rev is None and db is None and dynamic_properties is True:
            MISS = object()
            key = cls._key(docid)
            from_cache = cache.get(key, MISS)
            if from_cache != MISS:
                return from_cache
            else:
                raw = _super()
                cache.set(key, raw, CACHE_TIMEOUT)
                return raw
        else:
            return _super()

    @classmethod
    def _key(cls, id):
        key = '{prefix}:{cls}:{id}'.format(
            prefix=CACHE_PREFIX,
            cls=cls.__name__,
            id=id
        )
        return key
