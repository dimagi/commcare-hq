"""
Utilities and plugins for running tests with nose

Django-nose database context to run tests in two phases:

 - Stage 1 runs all test that don't require DB access (test that don't inherit
   from TransactionTestCase)
 - Stage 2 runs all DB tests (test that do inherit from TransactionTestCase)

Adapted from testrunner.TwoStageTestRunner
Based on http://www.caktusgroup.com/blog/2013/10/02/skipping-test-db-creation/
"""
from __future__ import absolute_import
import logging
import os
import sys
import threading
import types
from fnmatch import fnmatch
from unittest.case import TestCase

from django.apps import apps

import couchlog.signals
from couchdbkit import ResourceNotFound
from couchdbkit.ext.django import loading
from mock import patch, Mock
from nose.plugins import Plugin
from django.apps import AppConfig
from django.conf import settings
try:
    from django.db.backends.base.creation import TEST_DATABASE_PREFIX
except ImportError:
    # TODO - remove when django >= 1.8
    from django.db.backends.creation import TEST_DATABASE_PREFIX
from django.db.utils import OperationalError
from django_nose.plugin import DatabaseContext

from corehq.tests.optimizer import optimize_apps_for_test_labels

log = logging.getLogger(__name__)


class HqTestFinderPlugin(Plugin):
    """Find tests in all modules within "tests" packages"""

    enabled = True

    INCLUDE_DIRS = [
        "corehq/ex-submodules/*",
        "submodules/auditcare-src",
        "submodules/couchlog-src",
        "submodules/dimagi-utils-src",
        "submodules/django-digest-src",
        "submodules/toggle",
        "submodules/touchforms-src",
    ]

    def options(self, parser, env):
        """Avoid adding a ``--with`` option for this plugin."""

    def configure(self, options, conf):
        # do not call super (always enabled)

        import corehq
        abspath = os.path.abspath
        dirname = os.path.dirname
        self.hq_root = dirname(dirname(abspath(corehq.__file__)))

    @staticmethod
    def pathmatch(path, pattern):
        """Test if globbing pattern matches path

        >>> join = os.path.join
        >>> match = HqTestFinderPlugin.pathmatch
        >>> match(join('a', 'b', 'c'), 'a/b/c')
        True
        >>> match(join('a', 'b', 'c'), 'a/b/*')
        True
        >>> match(join('a', 'b', 'c'), 'a/*/c')
        True
        >>> match(join('a'), 'a/*')
        True
        >>> match(join('a', 'b', 'c'), 'a/b')
        >>> match(join('a', 'b', 'c'), 'a/*')
        >>> match(join('a', 'b', 'c'), 'a/*/x')
        False
        >>> match(join('a', 'b', 'x'), 'a/b/c')
        False
        >>> match(join('a', 'x', 'c'), 'a/b')
        False

        :returns: `True` if the pattern matches. `False` if it does not
                  match. `None` if the match pattern could match, but
                  has less elements than the path.
        """
        parts = path.split(os.path.sep)
        patterns = pattern.split("/")
        result = all(fnmatch(part, pat) for part, pat in zip(parts, patterns))
        if len(patterns) >= len(parts):
            return result
        return None if result else False

    def wantDirectory(self, directory):
        root = self.hq_root + os.path.sep
        if directory.startswith(root):
            relname = directory[len(root):]
            results = [self.pathmatch(relname, p) for p in self.INCLUDE_DIRS]
            log.debug("want directory? %s -> %s", relname, results)
            if any(results):
                return True
        else:
            log.debug("ignored directory: %s", directory)
        return None

    def wantFile(self, path):
        """Want all .py files in .../tests dir (and all sub-packages)"""
        pysrc = os.path.splitext(path)[-1] == ".py"
        if pysrc:
            parent, base = os.path.split(path)
            while base and len(parent) > len(self.hq_root):
                if base == "tests":
                    return True
                parent, base = os.path.split(parent)

    def wantModule(self, module):
        """Want all modules in "tests" package"""
        return "tests" in module.__name__.split(".")


class OmitDjangoInitModuleTestsPlugin(Plugin):
    """Omit tests imported from other modules into tests/__init__.py

    This is a temporary plugin to allow coexistence of the (old, pre-1.7)
    Django test runner and nose.
    """
    enabled = True
    module = None
    path = None

    def options(self, parser, env):
        """Avoid adding a ``--with`` option for this plugin."""

    def configure(self, options, conf):
        self.seen = set()

    def prepareTestLoader(self, loader):
        # patch the loader so we can get the module in wantClass
        realLoadTestsFromModule = loader.loadTestsFromModule

        def loadTestsFromModule(module, path=None, *args, **kw):
            self.module = module
            self.path = path
            return realLoadTestsFromModule(module, path, *args, **kw)
        loader.loadTestsFromModule = loadTestsFromModule

    def wantClass(self, cls):
        if issubclass(cls, TestCase):
            key = (self.module, cls)
            if key in self.seen:
                log.error("ignoring duplicate test: %s in %s "
                          "(INVESTIGATE THIS)", cls, self.module)
                return False
            self.seen.add(key)
            if self.path and os.path.basename(self.path) == "tests":
                return cls.__module__ == self.module.__name__
        return None  # defer to default selector


class ErrorOnDbAccessContext(object):
    """Ensure that touching a database raises an error."""

    def __init__(self, tests, runner):
        pass

    def setup(self):
        """Disable database access"""
        self.original_db_enabled = settings.DB_ENABLED
        settings.DB_ENABLED = False

        # do not log request exceptions to couch for non-database tests
        couchlog.signals.got_request_exception.disconnect(
            couchlog.signals.log_request_exception)

        self.db_patch = patch('django.db.backends.util.CursorWrapper')
        db_mock = self.db_patch.start()
        error = RuntimeError(
            "Attempt to access database in a 'no database' test suite. "
            "It could be that you don't have 'BASE_ADDRESS' set in your "
            "localsettings.py. If your test really needs database access "
            "it should subclass 'django.test.testcases.TestCase' or a "
            "similar test base class.")
        db_mock.side_effect = error

        mock_couch = Mock(side_effect=error, spec=[])

        # register our dbs with the extension document classes
        self.db_classes = db_classes = []
        for app, value in loading.couchdbkit_handler.app_schema.items():
            for cls in value.values():
                db_classes.append(cls)
                cls.set_db(mock_couch)

    def teardown(self):
        """Enable database access"""
        settings.DB_ENABLED = self.original_db_enabled
        for cls in self.db_classes:
            del cls._db
        couchlog.signals.got_request_exception.connect(
            couchlog.signals.log_request_exception)
        self.db_patch.stop()


class AppLabelsPlugin(Plugin):
    """A plugin that supplies a list of app labels for the migration optimizer

    See `corehq.tests.optimizer`
    """
    enabled = True
    user_specified_test_names = []  # globally referenced singleton

    def options(self, parser, env):
        parser.add_option('--no-migration-optimizer', action="store_true",
                          default=env.get('NOSE_NO_MIGRATION_OPTIMIZER'),
                          help="Disable migration optimizer. "
                               "[NOSE_NO_MIGRATION_OPTIMIZER]")

    def configure(self, options, conf):
        type(self).enabled = not options.no_migration_optimizer

    def loadTestsFromNames(self, names, module=None):
        if names == ['.'] and os.getcwd() == settings.BASE_DIR:
            # no user specified names
            return
        type(self).user_specified_test_names = names

    @classmethod
    def get_test_labels(cls, tests):
        """Get a list of app labels and possibly tests for the db app optimizer

        This should be called after `loadTestsFromNames` has been called.
        """
        test_apps = set(app.name for app in apps.get_app_configs()
                        if app.name not in settings.APPS_TO_EXCLUDE_FROM_TESTS
                        and not app.name.startswith('django.'))
        if not cls.user_specified_test_names:
            return [AppConfig.create(app).label for app in test_apps]

        def iter_names(test):
            # a.b.c -> a.b.c, a.b, a
            if isinstance(test.context, type):
                name = test.context.__module__
            elif isinstance(test.context, types.ModuleType):
                name = test.context.__name__
            else:
                raise RuntimeError("unknown test type: {!r}".format(test))
            parts = name.split(".")
            num_parts = len(parts)
            for i in range(num_parts):
                yield ".".join(parts[:num_parts - i])

        labels = set()
        for test in tests:
            for name in iter_names(test):
                if name in test_apps:
                    labels.add((AppConfig.create(name).label, test.context))
                    break
        return list(labels)


class HqdbContext(DatabaseContext):
    """Database setup/teardown

    In addition to the normal django database setup/teardown, also
    setup/teardown couch databases. Database setup/teardown may be
    skipped, depending on the presence and value of an environment
    variable (`REUSE_DB`). Typical usage is `REUSE_DB=1` which means
    skip database setup and migrations if possible and do not teardown
    databases after running tests. If connection fails for any test
    database in `settings.DATABASES` all databases will be re-created
    and migrated.

    Other supported `REUSE_DB` values:

    - `REUSE_DB=reset` : drop existing, then create and migrate new test
      databses, but do not teardown after running tests. This is
      convenient when the existing databases are outdated and need to be
      rebuilt.
    - `REUSE_DB=optimize` : same as reset, but use migration optimizer
      to reduce the number of database migrations.
    - `REUSE_DB=teardown` : skip database setup; do normal teardown after
      running tests.
    """

    def __init__(self, tests, runner):
        reuse_db = os.environ.get("REUSE_DB")
        self.skip_setup_for_reuse_db = reuse_db and reuse_db not in ["reset", "optimize"]
        self.skip_teardown_for_reuse_db = reuse_db and reuse_db != "teardown"
        self.optimize_migrations = AppLabelsPlugin.enabled and reuse_db in [None, "optimize"]
        if self.optimize_migrations:
            self.test_labels = AppLabelsPlugin.get_test_labels(tests)
        super(HqdbContext, self).__init__(tests, runner)

    @classmethod
    def verify_test_db(cls, app, uri):
        if '/test_' not in uri:
            raise ValueError("not a test db url: app=%s url=%r" % (app, uri))
        return app, uri

    def should_skip_test_setup(self):
        # FRAGILE look in sys.argv; can't get nose config from here
        return "--collect-only" in sys.argv

    def setup(self):
        if self.should_skip_test_setup():
            return

        if self.optimize_migrations:
            self.optimizer = optimize_apps_for_test_labels(self.test_labels)
            self.optimizer.__enter__()

        from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
        self.blob_db = TemporaryFilesystemBlobDB()

        # get/verify list of apps with databases to be deleted on teardown
        databases = getattr(settings, "COUCHDB_DATABASES", [])
        if isinstance(databases, (list, tuple)):
            # Convert old style to new style
            databases = {app_name: uri for app_name, uri in databases}
        self.apps = [self.verify_test_db(*item) for item in databases.items()]

        if self.skip_setup_for_reuse_db:
            from django.db import connections
            old_names = []
            for connection in connections.all():
                db = connection.settings_dict
                assert db["NAME"].startswith(TEST_DATABASE_PREFIX), db["NAME"]
                try:
                    connection.ensure_connection()
                except OperationalError:
                    break  # cannot connect; resume normal setup
                old_names.append((connection, db["NAME"], True))
            else:
                self.old_names = old_names, []
                return  # skip remaining setup

        sys.__stdout__.write("\n")  # newline for creating database message
        if "REUSE_DB" in os.environ:
            sys.__stdout__.write("REUSE_DB={REUSE_DB!r} ".format(**os.environ))
        super(HqdbContext, self).setup()

    def teardown(self):
        if self.should_skip_test_setup():
            return

        self.blob_db.close()
        if self.optimize_migrations:
            self.optimizer.__exit__(None, None, None)

        if self.skip_teardown_for_reuse_db:
            return

        # delete couch databases
        deleted_databases = []
        for app, uri in self.apps:
            if uri in deleted_databases:
                continue
            app_label = app.split('.')[-1]
            db = loading.get_db(app_label)
            try:
                db.server.delete_db(db.dbname)
                deleted_databases.append(uri)
                log.info("deleted database %s for %s", db.dbname, app_label)
            except ResourceNotFound:
                log.info("database %s not found for %s! it was probably already deleted.",
                         db.dbname, app_label)

        # HACK clean up leaked database connections
        from corehq.sql_db.connections import connection_manager
        connection_manager.dispose_all()

        super(HqdbContext, self).teardown()


def print_imports_until_thread_change():
    """Print imports until the current thread changes

    This is useful for troubleshooting premature test runner exit
    (often caused by an import when running tests --with-doctest).
    """
    main = threading.current_thread()
    sys.__stdout__.write("setting up import hook on %s\n" % main)

    class InfoImporter(object):

        def find_module(self, name, path=None):
            thread = threading.current_thread()
            # add code here to check for other things happening on import
            #if name == 'gevent':
            #    sys.exit()
            sys.__stdout__.write("%s %s\n" % (thread, name))
            if thread is not main:
                sys.exit()
            return None

    # Register the import hook. See https://www.python.org/dev/peps/pep-0302/
    sys.meta_path.append(InfoImporter())

if os.environ.get("HQ_TESTS_PRINT_IMPORTS"):
    print_imports_until_thread_change()
