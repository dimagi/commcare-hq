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
from django.test import utils as django_utils

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
    parser.addoption("--reusedb", default=os.environ.get("REUSE_DB"), help=REUSE_DB_HELP)
    parser.addoption("--db",
                     default="both",
                     choices=["skip", "only"],
                     help="Skip or only run database tests.")


@pytest.hookimpl
def pytest_configure(config):
    config.reusedb = reusedb = config.getoption("--reusedb")
    config.skip_setup_for_reuse_db = reusedb and reusedb != "reset"
    config.skip_teardown_for_reuse_db = reusedb and reusedb != "teardown"
    db_opt = config.getoption("--db")
    assert db_opt in ["both", "only", "skip"], db_opt
    config.should_run_database_tests = db_opt

    db_context.patch_django()


@pytest.hookimpl(wrapper=True)
def pytest_collection_modifyitems(config, items):
    """Sort and filter tests"""
    import pytest_django.plugin as mod
    django_key = None

    class items_for_django:
        def sort(key):
            nonlocal django_key
            django_key = key
            filter_and_sort(items, key, config)

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
    assert is_still_sorted(items, django_key)


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
    db_context.inject_database_setup(tests, is_db_test)
    items[:] = tests


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
        self.django_setup_databases = django_utils.setup_databases
        self.django_teardown_databases = django_utils.teardown_databases
        django_utils.setup_databases = self.session_setup
        django_utils.teardown_databases = self.session_teardown

    def inject_database_setup(self, tests, is_db_test):
        """Inject database setup just before the first that needs it"""
        for test in tests:
            if is_db_test(test):
                def setup_databases():
                    breakpoint()
                    self.setup_databases()
                    return setup()

                setup = test.setup
                test.setup = setup_databases
                break

    def session_setup(self, *args, **kw):
        """Preserve arguments, but do setup databases initially"""
        db_cfg = []
        self.setup_cfg = (db_cfg, args, kw)
        return db_cfg

    def setup_databases(self):
        assert not self.did_setup, "already set up"
        self.did_setup = True
        db_cfg, args, kw = self.setup_cfg
        db_cfg.extend(self.django_setup_databases(*args, **kw))

    def session_teardown(self, *args, **kw):
        if self.did_setup:
            result = self.django_teardown_databases(*args, **kw)
            assert result is None, result
        assert self.setup_cfg is not None, "session_setup() not called"


db_context = DeferredDatabaseContext()
