"""Reuse databases between test runs to save setup/teardown time.

In addition to the normal django database setup/teardown, also
setup/teardown Couch and Elasticsearch databases. Database setup/
teardown may be skipped, depending on the presence and value of an
environment variable (`REUSE_DB`) or option (`--reusedb`). Typical
usage is `REUSE_DB=1` which means skip database setup and migrations
if possible and do not teardown databases after running tests. If
connection fails for any test database in `settings.DATABASES` all
databases will be re-created and migrated.

The `REUSE_DB` environment variable may be overridden with
`--reusedb` option passed on the command line.
"""
import os
from unittest.mock import patch

import pytest
from pytest_django.plugin import blocking_manager_key

from django.test import utils as djutils

from dimagi.utils.parsing import string_to_boolean

from corehq.util.test_utils import timelimit

REUSE_DB_HELP = """
To be used in conjunction with the environment variable REUSE_DB=1.
reset: Drop existing test dbs, then create and migrate new ones, but do not
    teardown after running tests. This is convenient when the existing databases
    are outdated and need to be rebuilt.
flush: Flush all objects from the old test databases before running tests.
    Much faster than `reset`. Also runs `bootstrap` (see below).
bootstrap: Restore database state such as software plan versions and currencies
    initialized by database migrations. Sometimes when running tests with
    REUSE_DB=1 this state is lost, causing tests that depend on it to fail.
migrate: Migrate the test databases before running tests.
teardown: Skip database setup; do normal teardown after running tests.
"""


@pytest.hookimpl
def pytest_addoption(parser):
    parser.addoption(
        "--reusedb",
        default=string_to_boolean(os.environ.get("REUSE_DB") or "0"),
        help=REUSE_DB_HELP
    )
    parser.addoption(
        "--db",
        default="both",
        choices=["skip", "only"],
        help="Skip or only run database tests."
    )


@pytest.hookimpl
def pytest_configure(config):
    config.reuse_db = reusedb = config.getoption("--reusedb")
    config.skip_setup_for_reuse_db = reusedb and reusedb != "reset"
    config.skip_teardown_for_reuse_db = reusedb and reusedb != "teardown"
    db_opt = config.getoption("--db")
    assert db_opt in ["both", "only", "skip"], db_opt
    config.should_run_database_tests = db_opt

    _db_context.patch_django()


@pytest.hookimpl(wrapper=True)
def pytest_collection_modifyitems(config, items):
    """Sort and filter tests"""
    import pytest_django.plugin as mod
    django_key = None
    is_db_test = None

    class items_for_django:
        def sort(key):
            nonlocal django_key, is_db_test
            django_key = key
            is_db_test = filter_and_sort(items, key, config)

    def skip_django_modifyitems():
        called.append(1)
        return False

    mod.pytest_collection_modifyitems(items_for_django)
    called = []
    # use patch to skip django-pytest pytest_collection_modifyitems
    with patch.object(mod, "django_settings_is_configured", skip_django_modifyitems):
        yield
    assert called, "django_settings_is_configured patch was ineffective. " \
        "HQ-speicific test filtering and sorting may not have happened."
    assert is_still_sorted(items, django_key), "Test order changed. Database " \
        "tests are mixed with non-database tests."
    _db_context.setup_before_first_db_test(items, is_db_test, config)


def filter_and_sort(items, key, config):
    def is_db_test(item):
        return bool(new_key(item))

    new_key = reorder(key)
    if config.should_run_database_tests == "only":
        should_run = is_db_test
    elif config.should_run_database_tests == "skip":
        def should_run(item):
            return not is_db_test(item)
    else:
        def should_run(item):
            return True

    tests = sorted((t for t in items if should_run(t)), key=new_key)
    items[:] = tests
    return is_db_test


def reorder(key):
    """Translate django-pytest's test sorting key

    - 2 -> 0: non-db tests first (pytest-django normally runs them last)
    - 0 -> 1: TestCase
    - 1 -> 2: TransactionTestCase last
    """
    new_order = {2: 0, 0: 1, 1: 2}
    return lambda item: new_order[key(item)]


def is_still_sorted(items, key):
    if not items:
        return True
    new_key = reorder(key)
    it = iter(items)
    next(it)
    return all(new_key(a) <= new_key(b) for a, b in zip(items, it))


class DeferredDatabaseContext:

    def __init__(self):
        self.did_setup = False
        self.setup_cfg = None

    def patch_django(self):
        self.django_setup_databases = djutils.setup_databases
        self.django_teardown_databases = djutils.teardown_databases
        # HACK monkey patch
        djutils.setup_databases = self.session_setup
        djutils.teardown_databases = self.session_teardown

    def session_setup(self, *args, **kw):
        """Preserve arguments, but do not setup databases initially"""
        db_cfg = []
        self.setup_cfg = (db_cfg, args, kw)
        return db_cfg

    def setup_before_first_db_test(self, tests, is_db_test, config):
        """Inject database setup just before the first test that needs it

        Allows expensive setup to be avoided when there are no database
        tests included in the test run.
        """
        def setup_databases_before(test):
            def setup():
                db_blocker = config.stash[blocking_manager_key]
                with db_blocker.unblock():
                    self.setup_databases(config)
                return test_setup()

            # HACK monkey patch
            test_setup = test.setup
            test.setup = setup

        for test in tests:
            if is_db_test(test):
                setup_databases_before(test)
                break

    @timelimit(480)
    def setup_databases(self, config):
        """Setup databases for tests"""
        assert not self.did_setup, "already set up"
        self.did_setup = True
        db_cfg, args, kw = self.setup_cfg
        db_cfg.extend(self.django_setup_databases(*args, **kw))

    def session_teardown(self, *args, **kw):
        if self.did_setup:
            result = self.django_teardown_databases(*args, **kw)
            assert result is None, result
        assert self.setup_cfg is not None, "session_setup() not called"


_db_context = DeferredDatabaseContext()
