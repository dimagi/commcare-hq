__author__ = 'dmyung'

#taken from the django debug toolbar sql panel
import six.moves.socketserver
import os
import traceback
import django
from django.conf import settings

# -*- coding: utf-8 -

# Figure out some paths
django_path = os.path.realpath(os.path.dirname(django.__file__))
socketserver_path = os.path.realpath(os.path.dirname(six.moves.socketserver.__file__))


SQL_WARNING_THRESHOLD = getattr(settings, 'DEBUG_TOOLBAR_CONFIG', {}) \
                            .get('SQL_WARNING_THRESHOLD', 500)

UNKOWN_INFO = {}

DEFAULT_UUID_BATCH_COUNT = 1000

couch_view_queries = []


def process_key(key_obj):

    if isinstance(key_obj, list):
        key_obj = [six.text_type(x).encode('utf-8') for x in key_obj]
    else:
        key_obj = key_obj.encode('utf-8')
    return key_obj


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
            and django_path in s_path and 'django/contrib' not in s_path:
            continue
        if socketserver_path in s_path:
            continue
        trace.append((s[0], s[1], s[2], s[3]))
    return trace


def ms_from_timedelta(td):
    """
    Given a timedelta object, returns a float representing milliseconds
    """
    return (td.seconds * 1000) + (td.microseconds / 1000.0)


FORMAT_VIEW = 'view'
FORMAT_OPEN_DOC = 'open_doc'

VIEW_OUTPUT_HEADERS = [
    'view_path',
    'duration',
    'offset',
    'rows',
    'total_rows',
    'result_cached',
    'include_docs',
    # 'params',
]

OPEN_DOC_OUTPUT_HEADERS = [
    'doc_id',
    'duration',
    'doc_type',
    'response',
    # 'params',
]
