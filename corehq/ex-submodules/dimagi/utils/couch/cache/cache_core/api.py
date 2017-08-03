from couchdbkit import MultipleResultsFound
from django_redis.exceptions import ConnectionInterrupted
import simplejson
from . import COUCH_CACHE_TIMEOUT, CACHE_DOCS, rcache, key_doc_id
from .const import INTERRUPTED
from .gen import GenerationCache
from .lib import invalidate_doc_generation, _get_cached_doc_only


class FakeViewResults(list):
    """
    Fake view results that mostly act like a list, but implement a few of the
    common functions on couchdbkit's ViewResults object.
    """

    def first(self):
        try:
            return self[0]
        except IndexError:
            return None

    def one(self):
        """
        Return exactly one result or raise an exception.
        """
        length = len(self)
        if length > 1:
            raise MultipleResultsFound("%s results found." % length)

        return self.first()

    def all(self):
        """ return list of all results """
        return self


################################
# Primary API calls for caching

def cached_view(db, view_name, wrapper=None, cache_expire=COUCH_CACHE_TIMEOUT, force_invalidate=False,
                **params):
    """
    Entry point for caching views. See if it's in the generational view system, else juts call normal.
    """
    from dimagi.utils.couch.cache.cache_core.gen import GlobalCache, GenerationCache
    generation_mgr = GenerationCache.view_generation_map()
    if view_name in generation_mgr:
        cache_method = generation_mgr[view_name].cached_view
    else:
        cache_method = GlobalCache.nogen().cached_view

    return FakeViewResults(
        cache_method(db, view_name, wrapper=wrapper, cache_expire=cache_expire,
                     force_invalidate=force_invalidate, **params)
    )


def do_cache_doc(doc, cache_expire=COUCH_CACHE_TIMEOUT):
    """Cache an already opened doc instance"""
    if CACHE_DOCS:
        rcache().set(key_doc_id(doc['_id']), simplejson.dumps(doc), timeout=cache_expire)


def cached_open_doc(db, doc_id, cache_expire=COUCH_CACHE_TIMEOUT, **params):
    """
    Main wrapping function to open up a doc. Replace db.open_doc(doc_id)
    """
    try:
        cached_doc = _get_cached_doc_only(doc_id)
    except ConnectionInterrupted:
        cached_doc = INTERRUPTED
    if cached_doc in (None, INTERRUPTED):
        doc = db.open_doc(doc_id, **params)
        if cached_doc is not INTERRUPTED:
            do_cache_doc(doc, cache_expire=cache_expire)
        return doc
    else:
        return cached_doc


def invalidate_doc(doc, deleted=False):
    """
    For a given doc, delete it and all reverses.

    return: (true|false existed or not)
    """
    #first by just individual doc
    doc_id = doc['_id']
    doc_key = key_doc_id(doc_id)

    # regardless if it exist or not, send it to the generational lookup and invalidate_all.
    prior_ver = rcache().get(doc_key, None)
    if prior_ver and not doc.get('doc_type', None):
        invalidate_doc = simplejson.loads(prior_ver)
    else:
        invalidate_doc = doc

    invalidate_doc_generation(invalidate_doc)
    rcache().delete(key_doc_id(doc_id))

    if not deleted and invalidate_doc.get('doc_id', None) in GenerationCache.doc_type_generation_map():
        do_cache_doc(doc)

    if prior_ver:
        return True
    else:
        return False
