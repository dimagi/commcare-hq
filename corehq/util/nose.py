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
#from testrunner import TwoStageTestRunner

from couchdbkit.ext.django import loading
from mock import patch, Mock
from nose.plugins import Plugin
from django_nose.plugin import DatabaseContext

log = logging.getLogger(__name__)


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


class CouchdbContext(DatabaseContext):
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

    def setup(self):
        from django.conf import settings
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

        super(CouchdbContext, self).setup()

    def teardown(self):
        super(CouchdbContext, self).teardown()

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
