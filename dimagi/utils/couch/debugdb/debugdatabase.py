__author__ = 'dmyung'
from datetime import datetime
from dimagi.utils.couch.debugdb import tidy_stacktrace, SQL_WARNING_THRESHOLD, process_key, ms_from_timedelta
from couchdbkit import Database
#taken from the django debug toolbar sql panel
import traceback

from django.views.debug import linebreak_iter
import couchdbkit
from couchdbkit import resource, ResourceNotFound


# -*- coding: utf-8 -
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
        start = datetime.now()
        newparams = params.copy()

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
        errored=False
        try:
            doc = self.res.get(docid, **params).json_body
        except ResourceNotFound, ex:
            errored=True
            doc = {}
        #############################

        #############################
        #Debug Panel data collection
        stop = datetime.now()
        duration = ms_from_timedelta(stop - start)
        stacktrace = tidy_stacktrace(traceback.extract_stack())

        if wrapper is not None:
            view_path_display = "GET %s" % wrapper.im_self._doc_type
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
                'response': 200 if not errored else 404,
                'doc_type': doc.get('doc_type', '[unknown]'),
                'doc_id': docid,
            }
        self._queries.append(q)

        #end debug panel data collection
        ################################


        ##################################
        #Resume original Database.open_doc
        if wrapper is not None:
            if not callable(wrapper):
                raise TypeError("wrapper isn't a callable")
            return wrapper(doc)

        if errored:
            raise ResourceNotFound

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
        for key in  self._dynamic_keys:
            try:
                delattr(self, key)
            except:
                pass
        self._dynamic_keys = []

        self._result_cache = self.fetch_raw().json_body
        self._total_rows = self._result_cache.get('total_rows')
        self._offset = self._result_cache.get('offset', 0)

        # add key in view results that could be added by an external
        # like couchdb-lucene
        for key in self._result_cache.keys():
            if key not in ["total_rows", "offset", "rows"]:
                self._dynamic_keys.append(key)
                setattr(self, key, self._result_cache[key])

    def _debug_fetch_if_needed(self):
        view_args = self._arg.split('/')
        design_doc = view_args[1]
        view_name = view_args[3]
        self.debug_view = '%s/%s' % (design_doc, view_name)


        newparams = self.params.copy()
        if newparams.has_key('key'):
            newparams['key'] = process_key(newparams['key'])
        if newparams.has_key('startkey'):
            newparams['startkey'] = process_key(newparams['startkey'])
        if newparams.has_key('endkey'):
            newparams['endkey'] = process_key(newparams['endkey'])
        if newparams.has_key('keys'):
            newparams['keys'] = process_key(newparams['keys'])
        start = datetime.now()

        if not self._result_cache:
            result_cached=False
            self.debug_fetch()
        else:
            result_cached=True

        stop = datetime.now()
        duration = ms_from_timedelta(stop - start)
        stacktrace = tidy_stacktrace(traceback.extract_stack())

        self._queries.append({
                'view_path': self.debug_view,
                'duration': duration,
                'params': newparams,
                'stacktrace': stacktrace,
                'start_time': start,
                'stop_time': stop,
                'is_slow': (duration > SQL_WARNING_THRESHOLD),
                'total_rows': len(self._result_cache.get('rows', [])),
                'offset': self._result_cache.get('offset', 0),
                'rows': self._result_cache.get('total_rows', 0),
                'result_cached': result_cached,
            })
    _fetch_if_needed = _debug_fetch_if_needed




class DebugViewResults57(ViewResults):
    _queries = []
    def debug_fetch(self):
        """ Overrided
        fetch results and cache them
        """
        # reset dynamic keys
        for key in  self._dynamic_keys:
            try:
                delattr(self, key)
            except:
                pass
        self._dynamic_keys = []

        self._result_cache = self.fetch_raw().json_body
        self._total_rows = self._result_cache.get('total_rows')
        self._offset = self._result_cache.get('offset', 0)

        # add key in view results that could be added by an external
        # like couchdb-lucene
        for key in self._result_cache.keys():
            if key not in ["total_rows", "offset", "rows"]:
                self._dynamic_keys.append(key)
                setattr(self, key, self._result_cache[key])

    def _debug_fetch_if_needed(self):
        #todo: hacky way of making sure unicode is not in the keys
        newparams = self.params.copy()
        if newparams.has_key('key'):
            newparams['key'] = process_key(newparams['key'])
        if newparams.has_key('startkey'):
            newparams['startkey'] = process_key(newparams['startkey'])
        if newparams.has_key('endkey'):
            newparams['endkey'] = process_key(newparams['endkey'])
        if newparams.has_key('keys'):
            newparams['keys'] = process_key(newparams['keys'])
        start = datetime.now()

        if not self._result_cache:
            self.debug_fetch()

        stop = datetime.now()
        duration = ms_from_timedelta(stop - start)
        stacktrace = tidy_stacktrace(traceback.extract_stack())

        view_path_arr = self.view.view_path.split('/')
        view_path_arr.pop(0) #pop out the leading _design
        view_path_arr.pop(1) #pop out the middle _view
        view_path_display = '/'.join(view_path_arr)

        if not self._result_cache:
            result_cached = False
            self.debug_fetch()
        else:
            result_cached = True

        self._queries.append({
            'view_path': view_path_display,
            'duration': duration,
            'params': newparams,
            'stacktrace': stacktrace,
            'start_time': start,
            'stop_time': stop,
            'is_slow': (duration > SQL_WARNING_THRESHOLD),
            'total_rows': len(self._result_cache.get('rows', [])),
            'offset': self._result_cache.get('offset', 0),
            'rows': self._result_cache.get('total_rows', 0),
            'result_cached': result_cached
        })

    _fetch_if_needed = _debug_fetch_if_needed


if couchdbkit.version_info < (0, 6, 0):
    DebugViewResults = DebugViewResults57

    couchdbkit.client.ViewResults = DebugViewResults57
else:
    DebugViewResults = DebugViewResults64

couchdbkit.client.ViewResults = DebugViewResults


def get_template_info(source, context_lines=3):
    line = 0
    upto = 0
    source_lines = []
    before = during = after = ""

    origin, (start, end) = source
    template_source = origin.reload()

    for num, next in enumerate(linebreak_iter(template_source)):
        if start >= upto and end <= next:
            line = num
            before = template_source[upto:start]
            during = template_source[start:end]
            after = template_source[end:next]
        source_lines.append((num, template_source[upto:next]))
        upto = next

    top = max(1, line - context_lines)
    bottom = min(len(source_lines), line + 1 + context_lines)

    context = []
    for num, content in source_lines[top:bottom]:
        context.append({
            'num': num,
            'content': content,
            'highlight': (num == line),
        })

    return {
        'name': origin.name,
        'context': context,
    }

