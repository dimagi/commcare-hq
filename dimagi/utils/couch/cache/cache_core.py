from django.utils import http
from django.core import cache
import simplejson


MOCK_REDIS_CACHE = None
COUCH_CACHE_TIMEOUT = 1800


def rcache():
    return MOCK_REDIS_CACHE or cache.get_cache('redis')

#cached_view which has a list of doc_ids
#any time any of these doc_ids are altered, it'll invalidate the entire view for that index.
#however note, this does not account for the case where new docs meet the view criteria, so be careful with this usage
#alternatively, do a limit=0 and see if total_rows AND offset change to invalidate, but that incurs a cost that might be as bad as the original request

CACHED_VIEW_PREFIX = '#cached_view_'

#the actual payload of the cached_doc
CACHED_DOC_PREFIX = '#cached_doc_'

#for a given doc_id, a reverse relationship to see which views are touched by this cache
#value is a list of the cached_view keys
CACHED_VIEW_DOC_REVERSE = '#reverse_cached_doc_'

def key_doc_id(doc_id):
    ret = "%s%s" % (CACHED_DOC_PREFIX, doc_id)
    return ret

def key_reverse_doc(doc_id, suffix):
    ret =  "%s%s_%s" % (CACHED_VIEW_DOC_REVERSE, doc_id, suffix)
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
    does not necessarily have to be the full name - if you're hand building it for something
    """
    cache_view_key = "%(prefix)s_%(view_name)s" % {
        "prefix": CACHED_VIEW_PREFIX,
        "view_name": view_name_suffix,
    }
    return cache_view_key


def purge_by_doc_id(doc_id):
    #first by just individual doc
    print "purging single doc: %s" % doc_id
    rcache().delete(key_doc_id(doc_id))
    #then all the reverse indices by that doc_id
    rcache().delete_pattern(key_reverse_doc(doc_id, '*'))


def purge_view(view_key):
    """
    view_name you want to put in your key, does not necessarily have to be the right one...wildcard it yo
    """
    print "purging view: %s" % view_key
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



def cached_open_doc(db, doc_id, **params):
    cached_doc = get_cached_doc_only(doc_id)
    if not cached_doc:
        print "cached_open_doc miss: %s" % doc_id
        doc = db.open_doc(doc_id, **params)
        do_cache_doc(doc)
        return doc
    else:
        print "cached_open_doc hit: %s" % doc_id
        return cached_doc


def get_cached_doc_only(doc_id):
    """
    Main cache retrieval method for open_doc - for use by views in retrieving their docs.
    """
    doc = rcache().get(key_doc_id(doc_id), None)
    if doc is not None:
        return simplejson.loads(doc)
    else:
        #uh oh, how do i retrieve this doc now?
        return None


def do_cache_doc(doc):
    rcache().set(key_doc_id(doc['_id']), simplejson.dumps(doc), timeout=COUCH_CACHE_TIMEOUT)


def cache_view_doc(doc_or_docid, view_key):
    """
    cache by doc_id a reverse lookup of views that it is mutually dependent on
    """
    id = doc_or_docid['_id'] if isinstance(doc_or_docid, dict) else doc_or_docid
    key = key_reverse_doc(id, view_key)
    rcache().set(key, 1, timeout=COUCH_CACHE_TIMEOUT)

    if isinstance(doc_or_docid, dict):
        do_cache_doc(doc_or_docid)

def cached_view(db, view_name, **params):
    """
    cannot be wrapped, you must wrap it on your own
    """
    cache_docs = params.get('include_docs', False)

    cache_view_key = key_view_full(view_name, params)
    print "VIEW KEY: %s" % cache_view_key
    if cache_docs:
        #include_docs=true results look like:
        #{"total_rows": <int>, "offset": <int>, "rows": [...]}
        #test to see if view already cached
        cached_view = rcache().get(cache_view_key, None)
        if cached_view:
            intermediate_results = simplejson.loads(cached_view)
            final_results = {}
            row_stubs = intermediate_results['row_stubs']

            final_results['total_rows'] = intermediate_results['total_rows']
            final_results['offset'] = intermediate_results['offset']

            rows = []
            for stub in row_stubs:
                row = {
                    "id": stub['id'],
                    "value": None,
                    "key": stub["key"],
                    "doc": get_cached_doc_only(stub["id"])
                }
                rows.append(row)
            final_results['rows'] = rows
            return final_results
        else:
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
                cache_view_doc(row["doc"], cache_view_key)
                row_stubs.append(stub)

            cached_results = {
                "total_rows": view_results['total_rows'],
                "offset": view_results['offset'],
                "row_stubs": row_stubs
            }
            rcache().set(cache_view_key, simplejson.dumps(cached_results), timeout=COUCH_CACHE_TIMEOUT)
            return view_results


    else:
        cached_view = rcache().get(cache_view_key, None)
        if cached_view:
            results = simplejson.loads(cached_view)
            return results
        else:
            view_results = db.view(view_name, **params).all()
            rcache().set(cache_view_key, simplejson.dumps(view_results), timeout=COUCH_CACHE_TIMEOUT)
            for row in view_results:
                doc_id = row.get('id', None)
                if doc_id:
                    cache_view_doc(doc_id, cache_view_key)
            return view_results
