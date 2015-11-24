from contextlib import contextmanager
from copy import copy
import os
import unittest
from django.apps import apps
from django.test.simple import build_test
import yaml
from django.conf import settings


class DependenciesNotFound(Exception):
    pass


class OptimizedTestRunnerMixin(object):
    """
    You can have any TestRunner mixin this class to add db optimizations to it.
    What this does is allow you to explicitly declare test app dependencies and then
    using this test runner will only bootstrap those apps. If an app needs the database
    but has very few dependencies this can drastically improve speedup times.

    There are two ways to optimize tests, by app and by test class.

    By app:

    To optimize tests by app, you should add the app as an entry to `app_test_db_dependencies.yml`.
    Then you declare all other dependencies the app has by following the format of other apps.
    You _must_ use the fully qualified app from settings.py.
    The app is always assumed to be dependent on itself.

    App dependencies will be picked up and used by any of the following formats:

     - ./manage.py test appname
     - ./manage.py test appname.TestCase
     - ./manage.py test appname.TestCase.test_method

    By test:

    Some tests may require far fewer dependencies than the entire app. In this case you can further
    optimize by adding a `dependent_apps` property to the test itself. For example:

    class MyTestCase(TestCase):
        dependent_apps = ['myapp.dependentapp1', 'myapp.dependentapp2']

    This will override the app-level setting. Like apps, tests are always assumed to be dependent
    on the apps they live in.

    Updating:

    The easiest way to determine an app/test's dependencies is to mark them empty and then run the tests.
    The tests will fail on various django/couch access. You can then iteratively add those apps to the
    list of dependencies until tests pass again.
    """

    def run_tests(self, test_labels, extra_tests=None, **kwargs):
        test_labels = test_labels or self.get_test_labels()
        with optimize_apps_for_test_labels(test_labels):
            return super(OptimizedTestRunnerMixin, self).run_tests(test_labels, extra_tests, **kwargs)


class AppAndTestMap(object):

    def __init__(self):
        self._dependencies = get_app_test_db_dependencies()
        # these are permanently needed apps
        self.required_apps = set([
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions'
        ])
        self.apps = set([])
        self.tests = []  # contains tuples of app_labels and test classes

    def add_test(self, app_label, test):
        self.tests.append((app_label, test))

    def add_app(self, app_label):
        self.apps.add(app_label)

    def get_needed_installed_apps(self):
        try:
            needed_apps = copy(self.required_apps)
            for app in self.apps:
                needed_apps.update(self.get_app_dependencies(app))

            for app, test in self.tests:
                needed_apps.update(self.get_test_dependencies(app, test))

            return needed_apps
        except DependenciesNotFound:
            # any time we can't detect dependencies fall back to including all apps
            return settings.INSTALLED_APPS

    def get_app_dependencies(self, app):
        if app not in self._dependencies:
            raise DependenciesNotFound()
        return self._dependencies[app]

    def get_test_dependencies(self, app, test):
        dependencies = set([apps.get_app_config(app).name])

        def _extract_tests(test_suite_or_test):
            if isinstance(test_suite_or_test, unittest.TestCase):
                return [test_suite_or_test]
            elif isinstance(test_suite_or_test, unittest.TestSuite):
                return test._tests
            else:
                raise DependenciesNotFound()

        for test in _extract_tests(test):
            if hasattr(test, 'dependent_apps'):
                dependencies.update(test.dependent_apps)
            else:
                # if any of the tests don't have explicit dependencies defined
                # immediately short-circuit to using all app dependencies for the app
                return self.get_app_dependencies(app)
        return dependencies


@contextmanager
def optimize_apps_for_test_labels(test_labels):
    test_map = AppAndTestMap()
    for label in test_labels:
        if '.' in label:
            test_map.add_test(label.split('.')[0], build_test(label))
        else:
            test_map.add_app(label)

    _real_installed_apps = settings.INSTALLED_APPS
    needed_apps = test_map.get_needed_installed_apps()
    print 'overriding settings.INSTALLED_APPS to {}'.format(
        ','.join(test_map.get_needed_installed_apps())
    )
    settings.INSTALLED_APPS = tuple(needed_apps)
    apps.set_installed_apps(settings.INSTALLED_APPS)
    try:
        yield
    finally:
        settings.INSTALLED_APPS = _real_installed_apps
        apps.unset_installed_apps()


def get_app_test_db_dependencies():
    file_path = os.path.join(os.path.dirname(__file__), 'app_test_db_dependencies.yml')
    all_dependencies = {}
    with open(file_path) as f:
        app_dependencies = yaml.load(f)
        for app_path, dependencies in app_dependencies.items():
            # all_dependencies just contains the short labels, and should include a pointer to the
            # fully qualified app itself
            all_dependencies[app_path.split('.')[-1]] = [app_path] + dependencies

    return all_dependencies
