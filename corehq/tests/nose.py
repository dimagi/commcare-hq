"""
Utilities and plugins for running tests with nose

Django-nose database context to run tests in two phases:

 - Stage 1 runs all test that don't require DB access (test that don't inherit
   from TransactionTestCase)
 - Stage 2 runs all DB tests (test that do inherit from TransactionTestCase)

Adapted from testrunner.TwoStageTestRunner
Based on http://www.caktusgroup.com/blog/2013/10/02/skipping-test-db-creation/
"""
import logging
import os
import sys
import threading
from fnmatch import fnmatch

from django.conf import settings
from django.core import cache
from django.core.management import call_command
from django.db.backends.base.creation import TEST_DATABASE_PREFIX
from django.db.utils import OperationalError
from django.test.utils import get_unique_databases_and_mirrors

from couchdbkit import ResourceNotFound
from couchdbkit.ext.django import loading
from django_nose.plugin import DatabaseContext
from unittest.mock import Mock, patch
from nose.plugins import Plugin
from nose.tools import nottest
from requests.exceptions import HTTPError

from dimagi.utils.parsing import string_to_boolean

from corehq.apps.es.client import manager as elastic_manager
from corehq.tests.noseplugins.cmdline_params import CmdLineParametersPlugin
from corehq.util.couchdb_management import couch_config
from corehq.util.test_utils import timelimit, unit_testing_only

log = logging.getLogger(__name__)


class HqTestFinderPlugin(Plugin):
    """Find tests in all modules within "tests" packages"""

    enabled = True

    INCLUDE_DIRS = [
        "corehq/ex-submodules/*",
        "submodules/dimagi-utils-src",
        "submodules/django-digest-src",
        "submodules/toggle",
        "extensions/*/*",
        "custom",
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


class ErrorOnDbAccessContext(object):
    """Ensure that touching a database raises an error."""

    def __init__(self, tests, runner):
        pass

    def setup(self):
        """Disable database access"""
        self.original_db_enabled = settings.DB_ENABLED
        settings.DB_ENABLED = False

        self.db_patch = patch('django.db.backends.utils.CursorWrapper')
        db_mock = self.db_patch.start()
        error = RuntimeError(
            "Attempt to access database in a 'no database' test suite. "
            "It could be that you don't have 'BASE_ADDRESS' set in your "
            "localsettings.py. If your test really needs database access "
            "it should subclass 'django.test.testcases.TestCase' or a "
            "similar test base class.")
        db_mock.side_effect = error

        class CouchSpec(object):
            dbname = None
            view = Mock(return_value=[])

        def mock_couch(app):
            dbname = dbs.get(app, main_db_url).rsplit("/", 1)[1]
            return Mock(name=dbname, dbname=dbname, spec_set=CouchSpec)

        # register our dbs with the extension document classes
        main_db_url = settings.COUCH_DATABASE
        dbs = dict(settings.COUCHDB_DATABASES)
        self.db_classes = db_classes = []
        for app, value in loading.couchdbkit_handler.app_schema.items():
            for cls in value.values():
                db_classes.append(cls)
                cls.set_db(mock_couch(app))

    def teardown(self):
        """Enable database access"""
        settings.DB_ENABLED = self.original_db_enabled
        for cls in self.db_classes:
            del cls._db
        self.db_patch.stop()


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

    When using REUSE_DB=1, you may also want to provide a value for the
    --reusedb option, either reset, flush, bootstrap, migrate, or teardown.
    ./manage.py test --help will give you a description of these.
    """

    def __init__(self, tests, runner):
        reuse_db = (CmdLineParametersPlugin.get('reusedb')
                    or string_to_boolean(os.environ.get("REUSE_DB") or "0"))
        self.reuse_db = reuse_db
        self.skip_setup_for_reuse_db = reuse_db and reuse_db != "reset"
        self.skip_teardown_for_reuse_db = reuse_db and reuse_db != "teardown"
        super(HqdbContext, self).__init__(tests, runner)

    def should_skip_test_setup(self):
        return CmdLineParametersPlugin.get('collect_only')

    @timelimit(480)
    def setup(self):
        if self.should_skip_test_setup():
            return

        from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
        self.blob_db = TemporaryFilesystemBlobDB()
        self.old_names = self._get_databases()

        if self.skip_setup_for_reuse_db and self._databases_ok():
            if self.reuse_db == "migrate":
                call_command('migrate_multi', interactive=False)
            if self.reuse_db == "flush":
                flush_databases()
            if self.reuse_db == "bootstrap":
                bootstrap_migrated_db_state()
            return  # skip remaining setup

        if self.reuse_db == "reset":
            self.reset_databases()

        print("", file=sys.__stdout__)  # newline for creating database message
        if self.reuse_db:
            print("REUSE_DB={} ".format(self.reuse_db), file=sys.__stdout__, end="")
        if self.skip_setup_for_reuse_db:
            # pass this on to the Django runner to avoid creating databases
            # that already exist
            self.runner.keepdb = True
        super(HqdbContext, self).setup()

    def reset_databases(self):
        self.delete_couch_databases()
        self.delete_elastic_indexes()
        self.clear_redis()
        # tear down all databases together to avoid dependency issues
        teardown = []
        for connection, db_name, is_first in self.old_names:
            try:
                connection.ensure_connection()
                teardown.append((connection, db_name, is_first))
            except OperationalError:
                pass  # ignore databases that don't exist
        self.runner.teardown_databases(reversed(teardown))

    def _databases_ok(self):
        for connection, db_name, _ in self.old_names:
            db = connection.settings_dict
            assert db["NAME"].startswith(TEST_DATABASE_PREFIX), db["NAME"]
            try:
                connection.ensure_connection()
            except OperationalError as e:
                print(str(e), file=sys.__stderr__)
                return False
        return True

    def _get_databases(self):
        from django.db import connections
        old_names = []
        test_databases, mirrored_aliases = get_unique_databases_and_mirrors()
        assert not mirrored_aliases, "DB mirrors not supported"
        for signature, (db_name, aliases) in test_databases.items():
            alias = list(aliases)[0]
            connection = connections[alias]
            old_names.append((connection, db_name, True))
        return old_names

    def delete_couch_databases(self):
        for db in get_all_test_dbs():
            try:
                db.server.delete_db(db.dbname)
                log.info("deleted database %s", db.dbname)
            except ResourceNotFound:
                log.info("database %s not found! it was probably already deleted.",
                         db.dbname)

    def delete_elastic_indexes(self):
        # corehq.apps.es.client.create_document_adapter uses
        # TEST_DATABASE_PREFIX when constructing test index names
        for index_name in elastic_manager.get_indices():
            if index_name.startswith(TEST_DATABASE_PREFIX):
                elastic_manager.index_delete(index_name)

    def clear_redis(self):
        config = settings.CACHES.get("redis", {})
        loc = config.get("TEST_LOCATION")
        if loc:
            redis = cache.caches['redis']
            assert redis.client._server == [loc], (redis.client._server, config)
            redis.clear()

    def teardown(self):
        if self.should_skip_test_setup():
            return

        self.blob_db.close()

        self.delete_elastic_indexes()

        if self.skip_teardown_for_reuse_db:
            return

        self.delete_couch_databases()
        self.clear_redis()

        # HACK clean up leaked database connections
        from corehq.sql_db.connections import connection_manager
        connection_manager.dispose_all()

        # in case this was set before we want to remove it now
        self.runner.keepdb = False

        # tear down in reverse order
        self.old_names = reversed(self.old_names)
        super(HqdbContext, self).teardown()


def print_imports_until_thread_change():
    """Print imports until the current thread changes

    This is useful for troubleshooting premature test runner exit
    (often caused by an import when running tests --with-doctest).
    """
    main = threading.current_thread()
    print("setting up import hook on %s" % main, file=sys.__stdout__)

    class InfoImporter(object):

        def find_module(self, name, path=None):
            thread = threading.current_thread()
            # add code here to check for other things happening on import
            #if name == 'gevent':
            #    sys.exit()
            print("%s %s" % (thread, name), file=sys.__stdout__)
            if thread is not main:
                sys.exit()
            return None

    # Register the import hook. See https://www.python.org/dev/peps/pep-0302/
    sys.meta_path.append(InfoImporter())


@nottest
@unit_testing_only
def get_all_test_dbs():
    all_dbs = list(couch_config.all_dbs_by_db_name.values())
    for db in all_dbs:
        if '/test_' not in db.uri:
            raise ValueError("not a test db url: db=%s url=%r" % (db.dbname, db.uri))
    return all_dbs


@unit_testing_only
def flush_databases():
    """
    Best effort at emptying all documents from all databases.
    Useful when you break a test and it doesn't clean up properly. This took
    about 5 seconds to run when trying it out.
    """
    print("Flushing test databases, check yourself before you wreck yourself!", file=sys.__stdout__)
    for db in get_all_test_dbs():
        try:
            db.flush()
        except (ResourceNotFound, HTTPError):
            pass
    call_command('flush', interactive=False)
    bootstrap_migrated_db_state()


@unit_testing_only
def bootstrap_migrated_db_state():
    from corehq.apps.accounting.tests.generator import bootstrap_accounting
    from corehq.apps.smsbillables.tests.utils import bootstrap_smsbillables
    bootstrap_accounting()
    bootstrap_smsbillables()


if os.environ.get("HQ_TESTS_PRINT_IMPORTS"):
    print_imports_until_thread_change()
