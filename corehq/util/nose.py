"""
A nose plugin that splits testing into two stages:
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
from unittest.case import TestCase

from couchdbkit import ResourceNotFound
from couchdbkit.ext.django import loading
from mock import patch, Mock
from nose.plugins import Plugin
from django_nose.plugin import DatabaseContext

log = logging.getLogger(__name__)


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
        key = (self.module, cls)
        if issubclass(cls, TestCase):
            if key in self.seen:
                log.error("ignoring duplicate test: %s in %s "
                          "(INVESTIGATE THIS)", cls, self.module)
                return False
            self.seen.add(key)
            if self.path and os.path.basename(self.path) == "tests":
                return cls.__module__ == self.module.__name__
        return None  # defer to default selector


class DjangoMigrationsPlugin(Plugin):
    """Run tests with Django migrations.

    Migrations are disabled by default.
    """
    # Inspired by https://gist.github.com/NotSqrt/5f3c76cd15e40ef62d09
    # See also https://github.com/henriquebastos/django-test-without-migrations

    name = 'migrations'

    def configure(self, options, conf):
        super(DjangoMigrationsPlugin, self).configure(options, conf)
        if not self.enabled:
            from django.conf import settings
            settings.MIGRATION_MODULES = DisableMigrations()


class DisableMigrations(object):

    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return "notmigrations"


class ErrorOnDbAccessContext(object):
    """Ensure that touching a database raises and error."""

    def __init__(self, tests, runner):
        pass

    def setup(self):
        """Disable database access"""
        from django.conf import settings
        self.original_db_enabled = settings.DB_ENABLED
        settings.DB_ENABLED = False

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
        old_handler = loading.couchdbkit_handler
        for app, value in old_handler.app_schema.items():
            for name, cls in value.items():
                cls.set_db(mock_couch)

    def teardown(self):
        """Enable database access"""
        from django.conf import settings
        settings.DB_ENABLED = self.original_db_enabled
        self.db_patch.stop()


class HqdbContext(DatabaseContext):
    """Database context with couchdb setup/teardown

    In addition to the normal django database setup/teardown, also
    setup/teardown couchdb databases.

    This is mostly copied from
    ``couchdbkit.ext.django.testrunner.CouchDbKitTestSuiteRunner``
    """

    @staticmethod
    def get_test_db_name(dbname):
        return "%s_test" % dbname

    @classmethod
    def get_test_db(cls, db):
        # not copying DB would modify the db dict and add multiple "_test"
        test_db = db.copy()
        test_db['URL'] = cls.get_test_db_name(test_db['URL'])
        return test_db

    def should_skip_test_setup(self):
        # FRAGILE look in sys.argv; can't get nose config from here
        return "--collect-only" in sys.argv

    def setup(self):
        from django.conf import settings
        if self.should_skip_test_setup():
            return

        from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
        self.blob_db = TemporaryFilesystemBlobDB()

        log.info("overridding the couchdbkit database settings to use a test database!")

        # first pass: just implement this as a monkey-patch to the loading module
        # overriding all the existing couchdb settings
        databases = getattr(settings, "COUCHDB_DATABASES", [])

        # Convert old style to new style
        if isinstance(databases, (list, tuple)):
            databases = dict(
                (app_name, {'URL': uri}) for app_name, uri in databases
            )

        self.dbs = dict(
            (app, self.get_test_db(db)) for app, db in databases.items()
        )

        old_handler = loading.couchdbkit_handler
        couchdbkit_handler = loading.CouchdbkitHandler(self.dbs)
        loading.couchdbkit_handler = couchdbkit_handler
        loading.register_schema = couchdbkit_handler.register_schema
        loading.get_schema = couchdbkit_handler.get_schema
        loading.get_db = couchdbkit_handler.get_db

        # register our dbs with the extension document classes
        for app, value in old_handler.app_schema.items():
            for name, cls in value.items():
                cls.set_db(loading.get_db(app))

        sys.__stdout__.write("\n")  # newline for creating database message
        super(HqdbContext, self).setup()

    def teardown(self):
        if self.should_skip_test_setup():
            return

        self.blob_db.close()

        # delete couch databases
        deleted_databases = []
        skipcount = 0
        for app in self.dbs:
            app_label = app.split('.')[-1]
            db = loading.get_db(app_label)
            if db.dbname in deleted_databases:
                skipcount += 1
                continue
            try:
                db.server.delete_db(db.dbname)
                deleted_databases.append(db.dbname)
                log.info("deleted database %s for %s", db.dbname, app_label)
            except ResourceNotFound:
                log.info("database %s not found for %s! it was probably already deleted.", db.dbname, app_label)
        if skipcount:
            log.info("skipped deleting %s app databases that were already deleted", skipcount)

        # HACK clean up leaked database connections
        from corehq.sql_db.connections import connection_manager
        connection_manager.dispose_all()

        super(HqdbContext, self).teardown()
