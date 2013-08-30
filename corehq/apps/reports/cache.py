from django.conf import settings
from django.core import cache
from django.utils.cache import _generate_cache_header_key
from dimagi.utils.decorators.memoized import memoized
import functools

DEFAULT_EXPIRY = 60 * 60 # an hour

class CacheableRequestMixIn(object):
    """
    Used in conjunction with reports, to get a cache key that can be
    used in django's caching framework. Relies on the assumption that
    there is a .request property defined on this object.
    
    To actually enable caching, set is_cacheable to True (or some function)
    on a subclass of this.
    """

    is_cacheable = False
    CACHE_PREFIX = 'hq.reports' # a namespace where cache keys go

    def get_cache(self):
        try:
            return cache.get_cache(settings.REPORT_CACHE)
        except ValueError:
            return cache.cache

    @property
    @memoized
    def cache_key(self):
        # went source diving for this in django, it does exactly
        # what we want here, though is marked 'private'. seemed
        # better to import than to copy it and all dependencies
        # elsewhere
        return _generate_cache_header_key(self.CACHE_PREFIX, self.request)

    def _is_valid(self):
        # checks if this meets the preconditions for being allowed in the cache
        try:
            assert self.request.domain
            assert self.request.couch_user._id
            assert self.request.get_full_path().startswith('/a/{domain}/'.format(domain=self.request.domain))
            return True
        except (AssertionError, AttributeError):
            return False

    def set_in_cache(self, tag, object, expiry=DEFAULT_EXPIRY):
        if self._is_valid():
            self.get_cache().set(self.get_cache_key(tag), object, expiry)
        else:
            pass

    def get_from_cache(self, tag):
        if self._is_valid():
            return self.get_cache().get(self.get_cache_key(tag))
        else:
            return None

    def get_cache_key(self, tag):
        assert self._is_valid()
        domain = self.request.domain
        user = self.request.couch_user._id
        return "{key}-{domain}-{user}-{tag}".format(
            key=self.cache_key, 
            domain=domain,
            user=user,
            tag=tag,
        )

class request_cache(object):
    """
    A decorator that can be used on a function of a CacheableRequestMixIn
    to cache the results.
    """
    def __init__(self, tag, expiry=DEFAULT_EXPIRY):
        self.tag = tag
        self.expiry = expiry

    def __call__(self, fn):
        @functools.wraps(fn)
        def decorated(*args, **kwargs):
            report = args[0]
            if not report.is_cacheable:
                return fn(*args, **kwargs)
            else:
                from_cache = report.get_from_cache(self.tag)
                if from_cache:
                    return from_cache
                ret = fn(*args, **kwargs)
                report.set_in_cache(self.tag, ret, self.expiry)
                return ret
        return decorated

