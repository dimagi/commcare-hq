from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

import django
from django.core.checks import run_checks
from django.core.exceptions import AppRegistryNotReady

from manage import init_hq_python_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
init_hq_python_path()
django.setup()
try:
    run_checks()
except AppRegistryNotReady:
    pass

DB_SHARED_THREAD = """\
DatabaseWrapper objects created in a thread can only \
be used in that same thread.  The object with alias '{0}' \
was created in thread id {1} and this is thread id {2}.\
"""


def patch_thread_ident():
    # monkey patch django.
    # This patch make sure that we use real threads to get the ident which
    # is going to happen if we are using gevent or eventlet.
    # -- patch taken from gunicorn
    if getattr(patch_thread_ident, 'called', False):
        return
    try:
        from django.db.backends import BaseDatabaseWrapper, DatabaseError

        if 'validate_thread_sharing' in BaseDatabaseWrapper.__dict__:
            import thread
            _get_ident = thread.get_ident

            __old__init__ = BaseDatabaseWrapper.__init__

            def _init(self, *args, **kwargs):
                __old__init__(self, *args, **kwargs)
                self._thread_ident = _get_ident()

            def _validate_thread_sharing(self):
                if (not self.allow_thread_sharing and
                        self._thread_ident != _get_ident()):
                    raise DatabaseError(
                        DB_SHARED_THREAD % (
                            self.alias, self._thread_ident, _get_ident()),
                    )

            BaseDatabaseWrapper.__init__ = _init
            BaseDatabaseWrapper.validate_thread_sharing = \
                _validate_thread_sharing

        patch_thread_ident.called = True
    except ImportError:
        pass

patch_thread_ident()

app = Celery()
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
