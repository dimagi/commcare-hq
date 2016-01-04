import datetime
from collections import defaultdict
from functools import wraps
from unittest.util import strclass
from couchdbkit import Database, ResourceNotFound

from couchdbkit.ext.django import loading
from couchdbkit.ext.django.testrunner import CouchDbKitTestSuiteRunner
from django.apps import AppConfig
from django.conf import settings
from django.test import TransactionTestCase
from django.utils import unittest
from mock import patch, Mock
from corehq.tests.optimizer import OptimizedTestRunnerMixin

import settingshelper


def set_db_enabled(is_enabled):
    def decorator(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            original_value = settings.DB_ENABLED
            settings.DB_ENABLED = is_enabled
            try:
                return fn(*args, **kwargs)
            finally:
                settings.DB_ENABLED = original_value

        return _inner

    return decorator


class HqTestSuiteRunner(CouchDbKitTestSuiteRunner):
    """
    A test suite runner for Hq.  On top of the couchdb testrunner, also
    apply all our monkeypatches to the settings.

    To use this, change the settings.py file to read:

    TEST_RUNNER = 'Hq.testrunner.HqTestSuiteRunner'
    """

    dbs = []

    def setup_test_environment(self, **kwargs):
        self._assert_only_test_databases_accessed()
        # monkey patch TEST_APPS into INSTALLED_APPS
        # so that tests are run for them
        # without having to explicitly have them in INSTALLED_APPS
        # weird list/tuple type issues, so force everything to tuples
        settings.INSTALLED_APPS = (tuple(settings.INSTALLED_APPS) +
                                   tuple(settings.TEST_APPS))
        settings.CELERY_ALWAYS_EAGER = True
        # keep a copy of the original PILLOWTOPS setting around in case other tests want it.
        settings._PILLOWTOPS = settings.PILLOWTOPS
        settings.PILLOWTOPS = {}
        super(HqTestSuiteRunner, self).setup_test_environment(**kwargs)

    def setup_databases(self, **kwargs):
        from corehq.blobs.tests.util import TemporaryFilesystemBlobDB
        self.blob_db = TemporaryFilesystemBlobDB()
        self.newdbname = self.get_test_db_name(settings.COUCH_DATABASE_NAME)
        print "overridding the couch settings!"
        new_db_settings = settingshelper.get_dynamic_db_settings(
            settings.COUCH_SERVER_ROOT,
            settings.COUCH_USERNAME,
            settings.COUCH_PASSWORD,
            self.newdbname,
        )
        settings.COUCH_DATABASE_NAME = self.newdbname
        for (setting, value) in new_db_settings.items():
            setattr(settings, setting, value)
            print "set %s settting to %s" % (setting, value)

        settings.COUCH_SETTINGS_HELPER = settings.COUCH_SETTINGS_HELPER._replace(
            is_test=True)
        settings.EXTRA_COUCHDB_DATABASES = settings.COUCH_SETTINGS_HELPER.get_extra_couchdbs()

        return super(HqTestSuiteRunner, self).setup_databases(**kwargs)

    def teardown_databases(self, old_config, **kwargs):
        self.blob_db.close()
        for db_uri in settings.EXTRA_COUCHDB_DATABASES.values():
            db = Database(db_uri)
            self._assert_is_a_test_db(db_uri)
            self._delete_db_if_exists(db)
        super(HqTestSuiteRunner, self).teardown_databases(old_config, **kwargs)

    def _assert_only_test_databases_accessed(self):
        original_init = Database.__init__
        self_ = self

        def asserting_init(self, uri, create=False, server=None, **params):
            original_init(self, uri, create=create, server=server, **params)
            try:
                self_._assert_is_a_test_db(self.dbname)
            except AssertionError:
                db = self

                def request(self, *args, **kwargs):
                    self_._assert_is_a_test_db(db.dbname)

                self.res.request = request

        Database.__init__ = asserting_init

    @staticmethod
    def _assert_is_a_test_db(db_uri):
        assert db_uri.endswith('_test'), db_uri
        assert '_test_test' not in db_uri, db_uri

    @staticmethod
    def _delete_db_if_exists(db):
        try:
            db.server.delete_db(db.dbname)
        except ResourceNotFound:
            pass

    def get_all_test_labels(self):
        return [self._strip(app) for app in settings.INSTALLED_APPS
                if app not in settings.APPS_TO_EXCLUDE_FROM_TESTS
                and not app.startswith('django.')]

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        test_labels = test_labels or self.get_all_test_labels()
        return super(HqTestSuiteRunner, self).run_tests(
            test_labels, extra_tests, **kwargs
        )

    def _strip(self, entry):
        app_config = AppConfig.create(entry)
        return app_config.label


class TimingTestSuite(unittest.TestSuite):
    def __init__(self, tests=()):
        super(TimingTestSuite, self).__init__(tests)
        self.test_times = []
        self._patched_test_classes = set()

    def patch_test_class(self, klass):
        if klass in self._patched_test_classes:
            return

        suite = self
        original_call = klass.__call__

        def new_call(self, *args, **kwargs):
            start = datetime.datetime.utcnow()
            result = original_call(self, *args, **kwargs)
            end = datetime.datetime.utcnow()
            suite.test_times.append((self, end - start))
            return result

        klass.__call__ = new_call

        original_setUpClass = getattr(klass, 'setUpClass', None)
        if original_setUpClass:
            @wraps(original_setUpClass)
            def new_setUpClass(cls, *args, **kwargs):
                start = datetime.datetime.utcnow()
                result = original_setUpClass(*args, **kwargs)
                end = datetime.datetime.utcnow()
                suite.test_times.append((cls.setUpClass, end - start))
                return result
            klass.setUpClass = classmethod(new_setUpClass)

        self._patched_test_classes.add(klass)

    def addTest(self, test):
        self.patch_test_class(test.__class__)
        super(TimingTestSuite, self).addTest(test)

    @staticmethod
    def get_test_class(method):
        """
        return the TestCase class associated with method

        method can either be a test_* method, or setUpClass

        """
        try:
            # setUpClass
            return method.im_self
        except AttributeError:
            # test_* method
            return method.__class__


class TwoStageTestRunner(HqTestSuiteRunner):
    """
    Test runner which splits testing into two stages:
     - Stage 1 runs all test that don't require DB access (test that don't inherit from TransactionTestCase)
     - Stage 2 runs all DB tests (test that do inherit from TransactionTestCase)

    Based off http://www.caktusgroup.com/blog/2013/10/02/skipping-test-db-creation/
    """
    def get_test_labels(self):
        return self.get_all_test_labels()

    def split_suite(self, suite):
        """
        Check if any of the tests to run subclasses TransactionTestCase.
        """
        simple_tests = unittest.TestSuite()
        db_tests = TimingTestSuite()
        for test in suite:
            if isinstance(test, TransactionTestCase):
                db_tests.addTest(test)
            else:
                simple_tests.addTest(test)
        return simple_tests, db_tests

    def setup_mock_database(self):
        """
        Ensure that touching the DB raises and error.
        """
        self._db_patch = patch('django.db.backends.util.CursorWrapper')
        db_mock = self._db_patch.start()
        error = RuntimeError(
            "Attempt to access database in a 'no database' test suite run. "
            "It could be that you don't have 'BASE_ADDRESS' set in your localsettings.py. "
            "If your test really needs database access it must subclass 'TestCase' and not 'SimpleTestCase'.")
        db_mock.side_effect = error

        mock_couch = Mock(side_effect=error, spec=[])

        # register our dbs with the extension document classes
        old_handler = loading.couchdbkit_handler
        for app, value in old_handler.app_schema.items():
            for name, cls in value.items():
                cls.set_db(mock_couch)

    def teardown_mock_database(self):
        """
        Remove cursor patch.
        """
        self._db_patch.stop()

    @set_db_enabled(False)
    def run_non_db_tests(self, suite):
        print("Running {0} tests without database".format(suite.countTestCases()))
        self.setup_mock_database()
        result = self.run_suite(suite)
        self.teardown_mock_database()
        return self.suite_result(suite, result)

    @set_db_enabled(True)
    def run_db_tests(self, suite):
        print("Running {0} tests with database".format(suite.countTestCases()))
        old_config = self.setup_databases()
        result = self.run_suite(suite)

        from corehq.sql_db.connections import Session, connection_manager
        Session.remove()
        connection_manager.dispose_all()


        self.teardown_databases(old_config)
        return self.suite_result(suite, result)

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        """
        Run the unit tests in two groups, those that don't need db access
        first and those that require db access afterwards.
        """
        test_labels = test_labels or self.get_test_labels()
        self.setup_test_environment()
        full_suite = self.build_suite(test_labels, extra_tests)
        simple_suite, db_suite = self.split_suite(full_suite)
        failures = 0
        if simple_suite.countTestCases():
            failures += self.run_non_db_tests(simple_suite)

        if failures and self.failfast:
            return failures

        if db_suite.countTestCases():
            failures += self.run_db_tests(db_suite)
            self.print_test_times(db_suite)
        self.teardown_test_environment()
        return failures

    def print_test_times(self, suite, percent=.5):
        self.print_test_times_by_test(suite, percent)
        self.print_test_times_by_class(suite, percent)

    def _get_total_time(self, time_tuples):
        return reduce(
            lambda x, y: x + y,
            (test_time for _, test_time in time_tuples),
            datetime.timedelta(seconds=0)
        )

    def _print_test_times(self, sorted_times, percent):
        total_time = self._get_total_time(sorted_times)
        rounded_total_time = total_time - datetime.timedelta(
            microseconds=total_time.microseconds
        )
        cumulative_time = datetime.timedelta(seconds=0)

        print (
            '{:.0f}% of the test time (total: {}) '
            'was spent in the following tests:'.format(
                percent * 100,
                rounded_total_time,
            )
        )
        for test, test_time in sorted_times:
            cumulative_time += test_time
            print ' ', test, test_time
            if cumulative_time > total_time / 2:
                break

    def print_test_times_by_test(self, suite, percent=.5):
        self._print_test_times(
            sorted(suite.test_times, key=lambda x: x[1], reverse=True),
            percent,
        )

    def print_test_times_by_class(self, suite, percent=.5):
        times_by_class = defaultdict(datetime.timedelta)
        for test, test_time in suite.test_times:
            times_by_class[strclass(TimingTestSuite.get_test_class(test))] += test_time
        self._print_test_times(
            sorted(times_by_class.items(), key=lambda x: x[1], reverse=True),
            percent,
        )


class DevTestRunner(OptimizedTestRunnerMixin, TwoStageTestRunner):
    """
    See OptimizedTestRunner.
    """
    pass

class NonDbOnlyTestRunner(TwoStageTestRunner):
    """
    Override run_db_test to do nothing.
    """
    def run_db_tests(self, suite):
        print("Skipping {0} database tests".format(suite.countTestCases()))
        return 0


class DbOnlyTestRunner(TwoStageTestRunner):
    """
    Override run_non_db_tests to do nothing.
    """
    def run_non_db_tests(self, suite):
        print("Skipping {0} non-database tests".format(suite.countTestCases()))
        return 0


class _OnlySpecificApps(HqTestSuiteRunner):
    app_labels = set()
    # If include is False, then run for all EXCEPT app_labels
    include = True

    def get_test_labels(self):
        test_labels = self.get_all_test_labels()
        test_labels = [app_label for app_label in test_labels
                       if self.include == (app_label in self.app_labels)]
        print "Running tests for the following apps:"
        for test_label in sorted(test_labels):
            print "  {}".format(test_label)

        return test_labels


class GroupTestRunnerCatchall(_OnlySpecificApps, TwoStageTestRunner):
    include = False

    @property
    def app_labels(self):
        return {app_label
                for app_labels in settings.TRAVIS_TEST_GROUPS
                for app_label in app_labels}

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        self.setup_test_environment()
        failures = 0

        # run all non-db tests from ALL apps first irrespective of which app labels get passed in
        all_test_labels = self.get_all_test_labels()
        all_suite = self.build_suite(all_test_labels, extra_tests)
        simple_suite, _ = self.split_suite(all_suite)
        if simple_suite.countTestCases():
            failures += self.run_non_db_tests(simple_suite)

        if failures and self.failfast:
            return failures

        # then run db tests from specified apps
        db_labels = test_labels or self.get_test_labels()
        full_suite = self.build_suite(db_labels, extra_tests)
        _, db_suite = self.split_suite(full_suite)

        if db_suite.countTestCases():
            failures += self.run_db_tests(db_suite)
            self.print_test_times(db_suite)
        self.teardown_test_environment()
        return failures


def _bootstrap_group_test_runners():
    """
    Dynamically insert classes named GroupTestRunner[0-N] and GroupTestRunnerCatchall
    generated from the TRAVIS_TEST_GROUPS settings variable
    into this module, so they can be used like
        python manage.py test --testrunner=testrunner.GroupTestRunner0
        python manage.py test --testrunner=testrunner.GroupTestRunner1
        ...
        python manage.py test --testrunner=testrunner.GroupTestRunnerCatchall

    When you change the number of groups in TRAVIS_TEST_GROUPS, you must also
    manually edit travis.yml have the following env variables:

        env:
            [...] TEST_RUNNER=testrunner.GroupTestRunnerCatchall
            [...] TEST_RUNNER=testrunner.GroupTestRunner0
            [...] TEST_RUNNER=testrunner.GroupTestRunner1
            ...
    """
    for i, app_labels in enumerate(settings.TRAVIS_TEST_GROUPS):
        class_name = 'GroupTestRunner{}'.format(i)
        globals()[class_name] = type(
            class_name,
            (_OnlySpecificApps, DbOnlyTestRunner),
            {
                'app_labels': settings.TRAVIS_TEST_GROUPS[i]
            }
        )

_bootstrap_group_test_runners()
