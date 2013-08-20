from django.utils import http
from django.core import cache
import simplejson


MOCK_REDIS_CACHE = None
COUCH_CACHE_TIMEOUT = 43200

DEBUG_TRACE = False


def rcache():
    return MOCK_REDIS_CACHE or cache.get_cache('redis')

CACHED_VIEW_PREFIX = '#cached_view_'

#the actual payload of the cached_doc
CACHED_DOC_PREFIX = '#cached_doc_'

#for a given doc_id, a reverse relationship to see which views are touched by this cache
#value is a list of the cached_view keys
CACHED_VIEW_DOC_REVERSE = '#reverse_cached_doc_'


def key_doc_id(doc_id):
    """
    Redis cache key for a full couch document by doc_id
    """
    ret = "%s%s" % (CACHED_DOC_PREFIX, doc_id)
    return ret


def key_reverse_doc(doc_id, suffix):
    """
    a doc_id to tell you if a cached doc is in a view
    """
    ret = "%s%s_%s" % (CACHED_VIEW_DOC_REVERSE, doc_id, suffix)
    return ret


def key_view_full(view_name, params):
    cache_view_key = "%(prefix)s_%(view_name)s_%(params_str)s" % {
        "prefix": CACHED_VIEW_PREFIX,
        "view_name": view_name,
        "params_str": http.urlquote('|'.join(["%s:%s" % (k, v) for k, v in params.items()]))
    }
    return cache_view_key


def key_view_partial(view_name_suffix):
    """
    Given a partial view_key (just basically prefixing by view_name, don't care about params)
    Used for invalidating ALL views of a given view_name, or hand building a view cache key
    """
    cache_view_key = "%(prefix)s_%(view_name)s" % {
        "prefix": CACHED_VIEW_PREFIX,
        "view_name": view_name_suffix,
    }
    return cache_view_key


def purge_by_doc_id(doc_id):
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
        return True, exists
    else:
        return False, None

    #todo:
    #walk all views that are seen by that doc_id and blow away too?
    #if the pillow was not running this would def. be the case.


def purge_view(view_key):
    """
    view_name: you want to put in your key, does not necessarily have to be the right one...wildcard it yo
    """
    cached_view = rcache().get(view_key, None)
    if cached_view:
        results = simplejson.loads(cached_view)

        def gen_doc_ids(results):
            if isinstance(results, dict):
                for x in results['row_stubs']:
                    yield x['id']
            elif isinstance(results, list):
                for x in results:
                    if 'id' in x:
                        yield x['id']

        for doc_id in gen_doc_ids(results):
            reverse_doc_key = key_reverse_doc(doc_id, cached_view)
            rcache().delete(reverse_doc_key)

    #then purge this key
    rcache().delete(view_key)



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


def _get_cached_doc_only(doc_id):
    """
    helper cache retrieval method for open_doc - for use by views in retrieving their docs.
    """
    doc = rcache().get(key_doc_id(doc_id), None)
    if doc is not None:
        return simplejson.loads(doc)
    else:
        #uh oh, how do i retrieve this doc now?
        return None


def do_cache_doc(doc, cache_expire=COUCH_CACHE_TIMEOUT):
    rcache().set(key_doc_id(doc['_id']), simplejson.dumps(doc), timeout=cache_expire)


def cache_view_doc(doc_or_docid, view_key, cache_expire=COUCH_CACHE_TIMEOUT):
    """
    Cache by doc_id a reverse lookup of views that it is mutually dependent on
    """
    id = doc_or_docid['_id'] if isinstance(doc_or_docid, dict) else doc_or_docid
    key = key_reverse_doc(id, view_key)
    rcache().set(key, 1, timeout=cache_expire)

    if isinstance(doc_or_docid, dict):
        do_cache_doc(doc_or_docid)

def cached_view(db, view_name, wrapper=None, cache_expire=COUCH_CACHE_TIMEOUT, **params):
    """
    Call a view and cache the results, return cached if it's a cache hit.

    db: couch database to do query on
    view_name, params: couch view call parameters

    Note, a view call with include_docs=True will not be wrapped, you must wrap it on your own.


    """
    include_docs = params.get('include_docs', False)

    cache_view_key = key_view_full(view_name, params)
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
                        "doc": _get_cached_doc_only(stub["id"])
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
                cache_view_doc(row["doc"], cache_view_key, cache_expire=cache_expire)
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
        cached_view = rcache().get(cache_view_key, None)
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
                    cache_view_doc(doc_id, cache_view_key)
            return view_results
