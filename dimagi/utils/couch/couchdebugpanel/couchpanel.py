#taken from the django debug toolbar sql panel
import SocketServer
import logging
import traceback
from debug_toolbar.panels.sql import reformat_sql, reformat_sql
import django
from django.conf import settings #your django settings
from django.utils.translation import ugettext_lazy as _
import os

from debug_toolbar.panels import DebugPanel
import threading
from django.template.loader import render_to_string
from django.views.debug import linebreak_iter
import couchdbkit
from dimagi.utils.couch.couchdebugpanel.debugdatabase import DebugCouchDatabase

# Figure out some paths
django_path = os.path.realpath(os.path.dirname(django.__file__))
socketserver_path = os.path.realpath(os.path.dirname(SocketServer.__file__))
class CouchThreadTrackingHandler(logging.Handler):
    def __init__(self):
        if threading is None:
            raise NotImplementedError("threading module is not available, \
                the logging panel cannot be used without it")
        logging.Handler.__init__(self)
        self.records = {} # a dictionary that maps threads to log records

    def emit(self, record):
        self.get_records().append(record)

    def get_records(self, thread=None):
        """
        Returns a list of records for the provided thread, of if none is provided,
        returns a list for the current thread.
        """
        if thread is None:
            thread = threading.currentThread()
        if thread not in self.records:
            self.records[thread] = []
        return self.records[thread]

    def clear_records(self, thread=None):
        if thread is None:
            thread = threading.currentThread()
        if thread in self.records:
            del self.records[thread]


def tidy_stacktrace(strace):
    """
    Clean up stacktrace and remove all entries that:
    1. Are part of Django (except contrib apps)
    2. Are part of SocketServer (used by Django's dev server)
    3. Are the last entry (which is part of our stacktracing code)
    """
    trace = []
    for s in strace[:-1]:
        s_path = os.path.realpath(s[0])
        if getattr(settings, 'DEBUG_TOOLBAR_CONFIG', {}).get('HIDE_DJANGO_SQL', True) \
            and django_path in s_path and not 'django/contrib' in s_path:
            continue
        if socketserver_path in s_path:
            continue
        trace.append((s[0], s[1], s[2], s[3]))
    return trace



handler = CouchThreadTrackingHandler()
logging.root.setLevel(logging.NOTSET)
logging.root.addHandler(handler)

class CouchDBLoggingPanel(DebugPanel):
    """adapted from the django debug toolbar's LoggingPanel.  Instead, intercept the couchdbkit restkit logging calls to make a tidier display of couchdb calls being made."""
    name = 'CouchDB'
    has_content = True

    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self._offset = len(couch_view_queries)
        self._couch_time = 0
        self._key_queries = []

    def title(self):
        return _("CouchDB")

    def nav_title(self):
        return _("CouchDB")

    def nav_subtitle(self):
        self._key_queries = couch_view_queries[self._offset:]
        self._couch_time = sum([q['duration'] for q in self._key_queries])
        num_queries = len(self._key_queries)
        ## TODO l10n: use ngettext
        return "%d %s in %.2fms" % (
            num_queries,
            (num_queries == 1) and 'request' or 'requests',
            self._couch_time
        )

    def process_request(self, request):
        handler.clear_records()

    def get_and_delete(self):
        records = handler.get_records()
        handler.clear_records()
        return records

    def url(self):
        return ''


    def content(self):
        width_ratio_tally = 0
        for query in self._key_queries:
            query['view_params'] = str(query['params'])
            try:
                query['width_ratio'] = (query['duration'] / self._couch_time) * 100
            except ZeroDivisionError:
                query['width_ratio'] = 0
            query['start_offset'] = width_ratio_tally
            width_ratio_tally += query['width_ratio']

        context = self.context.copy()
        context.update({
            'queries': self._key_queries,
            'couch_time': self._couch_time,
        })
        return render_to_string('couchdebugpanel/couch.html', context)





# -*- coding: utf-8 -
from datetime import  datetime
from couchdbkit.client import   View, Database, ViewResults
from django.utils.hashcompat import sha_constructor


SQL_WARNING_THRESHOLD = getattr(settings, 'DEBUG_TOOLBAR_CONFIG', {}) \
                            .get('SQL_WARNING_THRESHOLD', 500)

UNKOWN_INFO = {}

DEFAULT_UUID_BATCH_COUNT = 1000

couch_view_queries = []


class DebugViewResults(ViewResults):
    def _fetch_if_needed(self):
        #todo: hacky way of makijng sure unicode is not in the keys
        newparams = self.params.copy()
        if newparams.has_key('key'):
            newparams['key'] = str(newparams['key'])
        if newparams.has_key('startkey'):
            newparams['startkey'] = str(newparams['startkey'])
        if newparams.has_key('endkey'):
            newparams['endkey'] = str(newparams['endkey'])
        if newparams.has_key('keys'):
            newparams['keys'] = str(newparams['keys'])
        #print self.params
        start = datetime.now()

        if not self._result_cache:
            self.fetch()

        stop = datetime.now()
        duration = ms_from_timedelta(stop - start)
        stacktrace = tidy_stacktrace(traceback.extract_stack())

        view_path_arr = self.view.view_path.split('/')
        view_path_arr.pop(0) #pop out the leading _design
        view_path_arr.pop(1) #pop out the middle _view
        view_path_display = '/'.join(view_path_arr)
        #print view_path_display

        couch_view_queries.append({
                'view_path': self.view.view_path,
                'view_path_safe': self.view.view_path.replace('/','|'),
                'view_path_display': view_path_display,
                'duration': duration,
                'params': newparams,
                'hash': sha_constructor(settings.SECRET_KEY + str(newparams) + str(self.view.view_path)).hexdigest(),
                'stacktrace': stacktrace,
                'start_time': start,
                'stop_time': stop,
                'is_slow': (duration > SQL_WARNING_THRESHOLD),
                #'is_cached': is_cached,
                #'is_reduce': sql.lower().strip().startswith('select'),
                #'template_info': template_info,
            })


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


def ms_from_timedelta(td):
    """
    Given a timedelta object, returns a float representing milliseconds
    """
    return (td.seconds * 1000) + (td.microseconds / 1000.0)
