__author__ = 'dmyung'
from datetime import datetime
from couchdbkit import Database
from dimagi.utils.couch.debugdb import tidy_stacktrace, SQL_WARNING_THRESHOLD, ms_from_timedelta

#taken from the django debug toolbar sql panel
import traceback
import couchdbkit
from couchdbkit import resource, ResourceNotFound
from couchdbkit.client import ViewResults


class DebugDatabase(Database):
    _queries = []
    def debug_open_doc(self, docid, **params):
        """Get document from database

        Args:
        @param docid: str, document id to retrieve
        @param wrapper: callable. function that takes dict as a param.
        Used to wrap an object.
        @param **params: See doc api for parameters to use:
        http://wiki.apache.org/couchdb/HTTP_Document_API

        @return: dict, representation of CouchDB document as
         a dict.
        """
        start = datetime.utcnow()

        ############################
        #Start Database.open_doc
        wrapper = None
        if "wrapper" in params:
            wrapper = params.pop("wrapper")
        elif "schema" in params:
            schema = params.pop("schema")
            if not hasattr(schema, "wrap"):
                raise TypeError("invalid schema")
            wrapper = schema.wrap

        docid = resource.escape_docid(docid)
        error = None
        try:
            doc = self.res.get(docid, **params).json_body
        except ResourceNotFound as ex:
            error = ex
            doc = {}
        #############################

        #############################
        #Debug Panel data collection
        stop = datetime.utcnow()
        duration = ms_from_timedelta(stop - start)
        stacktrace = tidy_stacktrace(traceback.extract_stack())

        if wrapper is not None:
            view_path_display = "GET %s" % wrapper.__self__._doc_type
        else:
            view_path_display = "Raw GET"

        q = {
                'view_path': view_path_display,
                'duration': duration,
                'params': params,
                'stacktrace': stacktrace,
                'start_time': start,
                'stop_time': stop,
                'is_slow': (duration > SQL_WARNING_THRESHOLD),
                'total_rows': 1,
                'response': 200 if error is None else 404,
                'doc_type': doc.get('doc_type', '[unknown]'),
                'doc_id': docid,
            }
        self._queries.append(q)

        #end debug panel data collection
        ################################


        ##################################
        #Resume original Database.open_doc
        if error is not None:
            raise error

        if wrapper is not None:
            if not callable(wrapper):
                raise TypeError("wrapper isn't a callable")
            return wrapper(doc)

        return doc
    get = debug_open_doc

couchdbkit.client.Database = DebugDatabase



class DebugViewResults64(ViewResults):
    _queries = []
    def debug_fetch(self):
        """ Overrided
        fetch results and cache them
        """
        # reset dynamic keys
        for key in self._dynamic_keys:
            try:
                delattr(self, key)
            except AttributeError:
                pass
        self._dynamic_keys = []

        self._result_cache = self.fetch_raw().json_body
        self._total_rows = self._result_cache.get('total_rows')
        self._offset = self._result_cache.get('offset', 0)

        # add key in view results that could be added by an external
        # like couchdb-lucene
        for key in self._result_cache:
            if key not in ["total_rows", "offset", "rows"]:
                self._dynamic_keys.append(key)
                setattr(self, key, self._result_cache[key])

    def _debug_fetch_if_needed(self):
        view_args = self._arg.split('/')

        if len(view_args) == 4:
            design_doc = view_args[1]
            view_name = view_args[3]
            self.debug_view = '%s/%s' % (design_doc, view_name)
        else:
            self.debug_view = view_args[0]

        start = datetime.utcnow()

        if not self._result_cache:
            result_cached = False
            self.debug_fetch()
        else:
            result_cached = True

        stop = datetime.utcnow()
        duration = ms_from_timedelta(stop - start)
        stacktrace = tidy_stacktrace(traceback.extract_stack())

        self._queries.append({
                'view_path': self.debug_view,
                'duration': duration,
                'params': self.params,
                'stacktrace': stacktrace,
                'start_time': start,
                'stop_time': stop,
                'is_slow': (duration > SQL_WARNING_THRESHOLD),
                'total_rows': len(self._result_cache.get('rows', [])),
                'offset': self._result_cache.get('offset', 0),
                'rows': self._result_cache.get('total_rows', 0),
                'result_cached': result_cached,
                'include_docs': self.params.get('include_docs', False)
            })
    _fetch_if_needed = _debug_fetch_if_needed




class DebugViewResults57(ViewResults):
    _queries = []
    def debug_fetch(self):
        """ Overrided
        fetch results and cache them
        """
        # reset dynamic keys
        for key in self._dynamic_keys:
            try:
                delattr(self, key)
            except AttributeError:
                pass
        self._dynamic_keys = []

        self._result_cache = self.fetch_raw().json_body
        self._total_rows = self._result_cache.get('total_rows')
        self._offset = self._result_cache.get('offset', 0)

        # add key in view results that could be added by an external
        # like couchdb-lucene
        for key in self._result_cache:
            if key not in ["total_rows", "offset", "rows"]:
                self._dynamic_keys.append(key)
                setattr(self, key, self._result_cache[key])

    def _debug_fetch_if_needed(self):
        start = datetime.utcnow()

        if not self._result_cache:
            self.debug_fetch()

        stop = datetime.utcnow()
        duration = ms_from_timedelta(stop - start)
        stacktrace = tidy_stacktrace(traceback.extract_stack())

        view_path_arr = self.view.view_path.split('/')
        if len(view_path_arr) == 4:
            view_path_display = '%s/%s' % (view_path_arr[1], view_path_arr[3])
        else:
            view_path_display = view_path_arr[0] # _all_docs

        if not self._result_cache:
            result_cached = False
            self.debug_fetch()
        else:
            result_cached = True

        self._queries.append({
            'view_path': view_path_display,
            'duration': duration,
            'params': self.params,
            'stacktrace': stacktrace,
            'start_time': start,
            'stop_time': stop,
            'is_slow': (duration > SQL_WARNING_THRESHOLD),
            'total_rows': len(self._result_cache.get('rows', [])),
            'offset': self._result_cache.get('offset', 0),
            'rows': self._result_cache.get('total_rows', 0),
            'result_cached': result_cached,
            'include_docs': self.params.get('include_docs', False)
        })

    _fetch_if_needed = _debug_fetch_if_needed


if couchdbkit.version_info < (0, 6, 0):
    DebugViewResults = DebugViewResults57
else:
    DebugViewResults = DebugViewResults64

couchdbkit.client.ViewResults = DebugViewResults
