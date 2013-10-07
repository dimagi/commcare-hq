from django.utils import http
from django.core import cache
import simplejson
from django.conf import settings

COUCH_CACHE_TIMEOUT = 43200
MOCK_REDIS_CACHE = None

DEBUG_TRACE = False

CACHE_DOCS = getattr(settings, 'COUCH_CACHE_DOCS', False)
CACHE_VIEWS = getattr(settings, 'COUCH_CACHE_VIEWS', False)

def rcache():
    return MOCK_REDIS_CACHE or cache.get_cache('redis')

CACHED_VIEW_PREFIX = '#cached_view_'

#the actual payload of the cached_doc
CACHED_DOC_PREFIX = '#cached_doc_'
CACHED_DOC_PROP_PREFIX = '#cached_doc_helper_'

#for a given doc_id, a reverse relationship to see which views are touched by this cache
#value is a list of the cached_view keys
CACHED_VIEW_DOC_REVERSE = '#reverse_cached_doc_'


def key_doc_prop(doc_id, prop_name):
    return ':'.join([CACHED_DOC_PROP_PREFIX, doc_id, prop_name])


def key_doc_id(doc_id):
    """
    Redis cache key for a full couch document by doc_id
    """
    ret = ":".join([CACHED_DOC_PREFIX, doc_id])
    return ret


def invalidate_doc_generation(doc):
    doc_type = doc.get('doc_type', None)
    generation_mgr = DocGenCache.doc_type_generation_map()
    if doc_type in generation_mgr:
        generation_mgr[doc_type].increment()


def invalidate_doc(doc, deleted=False):
    """
    For a given doc, delete it and all reverses.

    return: tuple of (true|false existed or not, last_version)
    """
    #first by just individual doc
    doc_id = doc['_id']
    doc_key = key_doc_id(doc_id)

    #regardless if it exist or not, send it to the generational lookup and increment.
    prior_ver = rcache().get(doc_key, None)
    if prior_ver and not doc.get('doc_type', None):
        invalidate_doc = simplejson.loads(prior_ver)
    else:
        invalidate_doc = doc

    invalidate_doc_generation(invalidate_doc)
    rcache().delete(key_doc_id(doc_id))
    rcache().delete_pattern(key_doc_prop(doc_id, '*'))

    if not deleted and invalidate_doc.get('doc_id', None) in DocGenCache.doc_type_generation_map():
        do_cache_doc(doc)

    if prior_ver:
        return True
    else:
        return False


def cached_open_doc(db, doc_id, cache_expire=COUCH_CACHE_TIMEOUT, **params):
    """
    Main wrapping function to open up a doc. Replace db.open_doc(doc_id)
    """
    cached_doc = _get_cached_doc_only(doc_id)
    if not cached_doc:
        doc = db.open_doc(doc_id, **params)
        do_cache_doc(doc, cache_expire=cache_expire)
        return doc
    else:
        return cached_doc


def cache_doc_prop(doc_id, prop_name, doc_data, cache_expire=COUCH_CACHE_TIMEOUT, **params):
    """
    Cache Helper

    Wrap additional data around a doc_id's properties, and invalidate when the doc gets invalidated

    doc_id: doc_id in question
    prop_name: prop_name name
    doc_data: json_dict that is to be cached
    """
    if CACHE_DOCS:
        key = key_doc_prop(doc_id, prop_name)
        rcache().set(key, simplejson.dumps(doc_data), timeout=cache_expire)


def get_cached_prop(doc_id, prop_name):
    key = key_doc_prop(doc_id, prop_name)
    retval = rcache().get(key, None)
    if retval and CACHE_DOCS:
        return simplejson.loads(retval)
    else:
        return None


def _get_cached_doc_only(doc_id):
    """
    helper cache retrieval method for open_doc - for use by views in retrieving their docs.
    """
    doc = rcache().get(key_doc_id(doc_id), None)
    if doc and CACHE_DOCS:
        return simplejson.loads(doc)
    else:
        return None

def do_cache_doc(doc, cache_expire=COUCH_CACHE_TIMEOUT):
    if CACHE_DOCS:
        rcache().set(key_doc_id(doc['_id']), simplejson.dumps(doc), timeout=cache_expire)


def cached_view(db, view_name, wrapper=None, cache_expire=COUCH_CACHE_TIMEOUT, force_invalidate=False,
                **params):
    """
    Entry point for caching views. See if it's in the generational view system, else juts call normal.
    """
    generation_mgr = DocGenCache.view_generation_map()
    if view_name in generation_mgr:
        cache_method = generation_mgr[view_name].cached_view
    else:
        cache_method = NoGenerationCache.nogen().cached_view

    return cache_method(db, view_name, wrapper=wrapper, cache_expire=cache_expire, force_invalidate=force_invalidate,
                        **params)

class DocGenCache(object):
    generation_key = None
    doc_types = []
    views = []

    @staticmethod
    def gen_caches():
        if not getattr(DocGenCache, '_generational_caches', None):
            DocGenCache.generate_caches()
        return getattr(DocGenCache, '_generational_caches')

    @staticmethod
    def view_generation_map():
        view_map = {}
        for gen_model in DocGenCache.gen_caches():
            for view_name in gen_model.views:
                view_map[view_name] = gen_model
        return view_map

    @staticmethod
    def doc_type_generation_map():
        doc_type_map = {}
        for gen_model in DocGenCache.gen_caches():
            for doc_type in gen_model.doc_types:
                doc_type_map[doc_type] = gen_model
        return doc_type_map

    @staticmethod
    def generate_caches():
        generational_caches = []
        for gen_model in DocGenCache.__subclasses__():
            generational_caches.append(gen_model())
        setattr(DocGenCache, '_generational_caches', generational_caches)

    def get_generation(self):
        genret = rcache().get(self.generation_key, None)
        if not genret:
            #never seen key before, start from zero
            rcache().set(self.generation_key, 0, timeout=0)
            return str(0)
        else:
            return str(genret)

    def increment(self):
        """
        Invalidate this cache by incrementing the generation
        """
        current_generation = self.get_generation()
        return rcache().incr(self.generation_key)

    def mk_view_cache_key(self, view_name, params=None):
        """
        view_name = "design_doc/viewname"
        if params is dict, then make param_string
        if params is '*' it's a wildcard
        """
        param_string = ""
        if isinstance(params, dict):
            param_string = http.urlquote('|'.join(["%s::%s" % (k, v) for k, v in params.items()]))
        elif params == '*':
            param_string = params

        cache_view_key = ':'.join([
            self.get_generation(),
            CACHED_VIEW_PREFIX,
            view_name,
            param_string,
        ])
        return cache_view_key

    def cached_view_doc(self, doc_or_docid, cache_expire=COUCH_CACHE_TIMEOUT):
        """
        Cache by doc_id a reverse lookup of views that it is mutually dependent on
        """
        if isinstance(doc_or_docid, dict):
            do_cache_doc(doc_or_docid, cache_expire=cache_expire)


    def cached_view(self, db, view_name, wrapper=None, cache_expire=COUCH_CACHE_TIMEOUT, force_invalidate=False,
                    **params):
        """
        Call a view and cache the results, return cached if it's a cache hit.

        db: couch database to do query on
        view_name, params: couch view call parameters
        force_invalidate: extra param to always hit the db and cache on read.

        Note, a view call with include_docs=True will not be wrapped, you must wrap it on your own.
        """

        if force_invalidate:
            self.increment()

        include_docs = params.get('include_docs', False)

        cache_view_key = self.mk_view_cache_key(view_name, params)
        if include_docs:
            #include_docs=True results in couchdbkit remove the 'rows' result and returns just the actual rows in an array
            cached_view = rcache().get(cache_view_key, None)
            if cached_view and CACHE_VIEWS:
                results = simplejson.loads(cached_view)
                final_results = {}

                if include_docs:
                    row_stubs = results['row_stubs']

                    final_results['total_rows'] = results['total_rows']
                    final_results['offset'] = results['offset']

                    rows = []
                    for stub in row_stubs:
                        row = {
                            "id": stub['id'],
                            "value": None,
                            "key": stub["key"],
                            #this feels hacky, but for some reason other views are squashing the master cached doc.
                            #a more true invalidation scheme should have this more readily address this, but for now
                            #do a db call here and cache it. Should be a _cached_doc_only call here
                            "doc": cached_open_doc(db, stub['id'])
                        }
                        rows.append(row)
                    if wrapper:
                        final_results = [wrapper(x['doc']) for x in rows]
                    else:
                        #final_results['rows'] = rows
                        final_results = rows
                return final_results
            else:
                #cache miss, get view, cache it and all docs
                view_obj = db.view(view_name, **params)
                view_obj._fetch_if_needed()
                view_results = view_obj._result_cache
                row_stubs = []

                for row in view_results["rows"]:
                    stub = {
                        "id": row['id'],
                        "value": None,
                        "key": row["key"],
                    }
                    self.cached_view_doc(row["doc"], cache_expire=cache_expire)
                    row_stubs.append(stub)

                cached_results = {
                    "total_rows": view_results['total_rows'],
                    "offset": view_results['offset'],
                    "row_stubs": row_stubs
                }

                if wrapper:
                    retval = [wrapper(x['doc']) for x in view_results['rows']]
                else:
                    retval = view_results['rows']
                rcache().set(cache_view_key, simplejson.dumps(cached_results), timeout=cache_expire)
                return retval

        else:
            ###########################
            # include_docs=False just returns the entire view verbatim
            cached_view = rcache().get(cache_view_key)
            if cached_view and CACHE_VIEWS:
                results = simplejson.loads(cached_view)
                return results
            else:
                view_results = db.view(view_name, **params).all()
                rcache().set(cache_view_key, simplejson.dumps(view_results), timeout=cache_expire)
                for row in view_results:
                    doc_id = row.get('id', None)
                    if doc_id:
                        #a non reduce view will have doc_ids on each row, we want to reverse index these
                        #to know when to invalidate
                        self.cached_view_doc(doc_id)
                return view_results


class NoGenerationCache(DocGenCache):
    """
    Default cache for those not mapped. No generational tracking.
    """
    generation_key = None
    doc_types = [
    ]
    views = []

    _instance = None

    def get_generation(self):
        return "#global#"

    def increment(self):
        return self.get_generation()


    @staticmethod
    def nogen():
        if not NoGenerationCache._instance:
            NoGenerationCache._instance = NoGenerationCache()
        return NoGenerationCache._instance


