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


def key_doc_prop(doc_id, property):
    key = "%s%s_%s" % (CACHED_DOC_PROP_PREFIX, doc_id, property)
    return key


def key_doc_id(doc_id):
    """
    Redis cache key for a full couch document by doc_id
    """
    ret = ":".join([CACHED_DOC_PREFIX, doc_id])
    return ret


def key_reverse_doc(doc_id, suffix):
    """
    a doc_id to tell you if a cached doc is in a view
    """
    ret = ":".join([CACHED_VIEW_DOC_REVERSE, doc_id, suffix])
    return ret


def invalidate_doc_generation(doc):
    doc_type = doc.get('doc_type', None)
    generation_mgr = DocGenCache.doc_type_generation_map()
    if doc_type in generation_mgr:
        generation_mgr[doc_type].increment()


def invalidate_by_doc_id(doc_id):
    """
    For a given doc_id, delete it and all reverses.

    return: tuple of (true|false existed or not, last_version)
    """
    #first by just individual doc
    doc_key = key_doc_id(doc_id)
    exists = rcache().get(doc_key, None)

    if exists:
        rcache().delete(key_doc_id(doc_id))

        #then all the reverse indices by that doc_id
        rcache().delete_pattern(key_reverse_doc(doc_id, '*'))

        #then delete all properties
        rcache().delete_pattern(key_doc_prop(doc_id, '*'))
        last_version = simplejson.loads(exists)
        invalidate_doc_generation(last_version)
        return True, simplejson.loads(exists)
    else:
        return False, None

    #todo:
    #walk all views that are seen by that doc_id and blow away too?
    #if the pillow was not running this would def. be the case.


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


def cache_doc_prop(doc_id, property, doc_data, cache_expire=COUCH_CACHE_TIMEOUT, **params):
    """
    Cache Helper

    Wrap additional data around a doc_id's properties, and invalidate when the doc gets invalidated

    doc_id: doc_id in question
    property: property name
    doc_data: json_dict that is to be cached
    """
    key = key_doc_prop(doc_id, property)
    rcache().set(key, simplejson.dumps(doc_data), timeout=cache_expire)


def get_cached_prop(doc_id, property):
    key = key_doc_prop(doc_id, property)
    retval = rcache().get(key, None)
    if retval:
        return simplejson.loads(retval)
    else:
        return None


def _get_cached_doc_only(doc_id):
    """
    helper cache retrieval method for open_doc - for use by views in retrieving their docs.
    """
    doc = rcache().get(key_doc_id(doc_id), None)
    if doc is not None:
        return simplejson.loads(doc)
    else:
        return None


def do_cache_doc(doc, cache_expire=COUCH_CACHE_TIMEOUT):
    rcache().set(key_doc_id(doc['_id']), simplejson.dumps(doc), timeout=cache_expire)

class DocGenCache(object):
    generation_key = None
    doc_types = []
    views = []

    @staticmethod
    def gen_caches():
        if not getattr(DocGenCache, '_generational_caches', None):
            DocGenCache.generate_caches()
        return getattr(DocGenCache._generational_caches)

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
            rcache().set(self.generation_key, timeout=0)
            return 0
        else:
            return genret

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
        if isinstance(params, dict):
            param_string = http.urlquote('|'.join(["%s::%s" % (k, v) for k, v in params.items()]))
        elif params == '*':
            param_string = params
        else:
            param_string = ""

        cache_view_key = ':'.join([
            self.get_generation(),
            CACHED_VIEW_PREFIX,
            view_name,
            param_string
        ])
        return cache_view_key

    def cache_view_doc(self, doc_or_docid, cache_expire=COUCH_CACHE_TIMEOUT):
        """
        Cache by doc_id a reverse lookup of views that it is mutually dependent on
        """
        if isinstance(doc_or_docid, dict):
            do_cache_doc(doc_or_docid, cache_expire=cache_expire)


    def cache_view(self, db, view_name, wrapper=None, cache_expire=COUCH_CACHE_TIMEOUT, **params):
        """
        Call a view and cache the results, return cached if it's a cache hit.

        db: couch database to do query on
        view_name, params: couch view call parameters

        Note, a view call with include_docs=True will not be wrapped, you must wrap it on your own.
        """
        include_docs = params.get('include_docs', False)

        cache_view_key = self.mk_view_cache_key(view_name, params)
        if include_docs:
            #include_docs=True results in couchdbkit remove the 'rows' result and returns just the actual rows in an array
            cached_view = rcache().get(cache_view_key, None)
            if cached_view:
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
                    self.cache_view_doc(row["doc"], cache_view_key, cache_expire=cache_expire)
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
            if cached_view:
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
                        self.cache_view_doc(doc_id)
                return view_results