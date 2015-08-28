import importlib
from django.utils import http
from . import CACHED_VIEW_PREFIX, rcache, COUCH_CACHE_TIMEOUT, CACHE_VIEWS
from django.conf import settings
from django_redis.exceptions import ConnectionInterrupted
import simplejson
from dimagi.utils.couch.cache.cache_core.const import INTERRUPTED, MISSING


class GenerationCache(object):
    generation_key = None
    doc_types = []
    views = []

    @staticmethod
    def _get_generational_caches():
        if not getattr(GenerationCache, '_generational_caches', None):
            GenerationCache._generate_caches()
        return getattr(GenerationCache, '_generational_caches')

    @staticmethod
    def view_generation_map():
        view_map = {}
        for gen_model in GenerationCache._get_generational_caches():
            for view_name in gen_model.views:
                view_map[view_name] = gen_model
        return view_map

    @staticmethod
    def doc_type_generation_map():
        doc_type_map = {}
        for gen_model in GenerationCache._get_generational_caches():
            for doc_type in gen_model.doc_types:
                doc_type_map[doc_type] = gen_model
        return doc_type_map

    @staticmethod
    def _generate_caches():
        generational_caches = []

        for cache_str in getattr(settings, 'COUCH_CACHE_BACKENDS', []):
            mod_path, cache_class_name = cache_str.rsplit('.', 1)
            mod = importlib.import_module(mod_path)
            gen_model = getattr(mod, cache_class_name)
            generational_caches.append(gen_model())
        setattr(GenerationCache, '_generational_caches', generational_caches)

    def _get_generation(self):
        genret = rcache().get(self.generation_key, None)
        if not genret:
            # never seen key before, start from zero
            rcache().set(self.generation_key, 0, timeout=0)
            return str(0)
        else:
            return str(genret)

    def invalidate_all(self):
        """
        Invalidate this cache by incrementing the generation
        """
        try:
            return rcache().incr(self.generation_key)
        except ValueError:
            # there was likely no cached data to start with. that's fine.
            pass

    def _mk_view_cache_key(self, view_name, params=None):
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
            self._get_generation(),
            CACHED_VIEW_PREFIX,
            view_name,
            param_string,
        ])
        return cache_view_key

    def _cached_view_doc(self, doc_or_docid, cache_expire=COUCH_CACHE_TIMEOUT):
        """
        Cache by doc_id a reverse lookup of views that it is mutually dependent on
        """
        from .api import do_cache_doc
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
        from .api import cached_open_doc

        include_docs = params.get('include_docs', False)

        try:
            if force_invalidate:
                self.invalidate_all()
            cache_view_key = self._mk_view_cache_key(view_name, params)
            cached_view = rcache().get(cache_view_key, MISSING)
        except ConnectionInterrupted:
            cache_view_key = INTERRUPTED
            cached_view = INTERRUPTED

        is_cache_hit = cached_view not in (MISSING, INTERRUPTED) and CACHE_VIEWS
        if include_docs:
            # include_docs=True results in couchdbkit remove the 'rows' result
            # and returns just the actual rows in an array
            if is_cache_hit:
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
                            # this feels hacky, but for some reason other views are squashing the master cached doc.
                            # a more true invalidation scheme should have this more readily address this, but for now
                            # do a db call here and cache it. Should be a _cached_doc_only call here
                            "doc": cached_open_doc(db, stub['id'])
                        }
                        rows.append(row)
                    if wrapper:
                        final_results = [wrapper(x['doc']) for x in rows]
                    else:
                        final_results = rows
                return final_results
            else:
                # cache miss, get view, cache it and all docs
                view_obj = db.view(view_name, **params)
                # todo: we should try and decouple this from the "protected" methods of
                # couchdbkit's ViewResults
                view_obj._fetch_if_needed()
                view_results = view_obj._result_cache
                row_stubs = []

                for row in view_results["rows"]:
                    stub = {
                        "id": row['id'],
                        "value": None,
                        "key": row["key"],
                    }
                    self._cached_view_doc(row["doc"], cache_expire=cache_expire)
                    row_stubs.append(stub)

                cached_results = {
                    "total_rows": view_obj._total_rows,
                    "offset": view_obj._offset,
                    "row_stubs": row_stubs
                }

                if wrapper:
                    retval = [wrapper(x['doc']) for x in view_results['rows']]
                else:
                    retval = view_results['rows']
                if cached_view is not INTERRUPTED:
                    rcache().set(cache_view_key, simplejson.dumps(cached_results), timeout=cache_expire)
                return retval

        else:
            # include_docs=False just returns the entire view verbatim
            if is_cache_hit:
                results = simplejson.loads(cached_view)
                return results
            else:
                view_results = db.view(view_name, **params).all()
                if cached_view is not INTERRUPTED:
                    rcache().set(cache_view_key, simplejson.dumps(view_results), timeout=cache_expire)
                    for row in view_results:
                        doc_id = row.get('id', None)
                        if doc_id:
                            # a non reduce view will have doc_ids on each row, we want to reverse index these
                            # to know when to invalidate
                            self._cached_view_doc(doc_id)
                return view_results


class GlobalCache(GenerationCache):
    """
    Default cache for those not mapped. No generational tracking.
    """
    generation_key = None
    doc_types = [
    ]
    views = []

    _instance = None

    def _get_generation(self):
        return "#global#"

    def invalidate_all(self):
        raise NotImplementedError("You're trying to call a global cache invalidation - does not support invalidation - please rethink your priorities.")


    @staticmethod
    def nogen():
        if not GlobalCache._instance:
            GlobalCache._instance = GlobalCache()
        return GlobalCache._instance


