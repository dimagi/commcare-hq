import pytest


@pytest.hookimpl
def pytest_sessionstart():
    from corehq.apps.domain.tests.test_utils import patch_domain_deletion
    from corehq.form_processor.tests.utils import patch_testcase_databases
    from corehq.util.es.testing import patch_es_user_signals
    from corehq.util.test_utils import patch_foreign_value_caches

    patch_unittest_TestCase_doClassCleanup()
    patch_django_test_case()
    patch_assertItemsEqual()
    patch_testcase_databases()
    extend_freezegun_ignore_list()
    patch_es_user_signals()
    patch_foreign_value_caches()
    patch_domain_deletion()


def patch_unittest_TestCase_doClassCleanup():
    """Raise/print errors caught during class cleanup

    pytest ignores `TestCase.tearDown_exceptions`, which causes them to
    pass silently. Can be removed once on a version of pytest that
    includes https://github.com/pytest-dev/pytest/pull/12250
    """

    @classmethod
    def doClassCleanupAndRaiseLastError(cls):
        doClassCleanups()
        errors = cls.tearDown_exceptions
        if errors:
            if len(errors) > 1:
                num = len(errors)
                for n, (exc_type, exc, tb) in enumerate(errors[:-1], start=1):
                    print(f"\nclass cleanup error ({n} of {num}):", file=sys.stderr)
                    print_exception(exc_type, exc, tb)
            raise errors[-1][1]

    import sys
    from traceback import print_exception
    from unittest.case import TestCase
    doClassCleanups = TestCase.doClassCleanups
    TestCase.doClassCleanups = doClassCleanupAndRaiseLastError


def patch_django_test_case():
    """Do class cleanups before TestCase transaction rollback"""
    from django.test import TestCase

    @classmethod
    def tearDownClass(cls):
        try:
            cls.doClassCleanups()
        finally:
            real_tearDownClass(cls)

    real_tearDownClass = TestCase.tearDownClass.__func__
    TestCase.tearDownClass = tearDownClass


def patch_assertItemsEqual():
    import unittest
    unittest.TestCase.assertItemsEqual = unittest.TestCase.assertCountEqual


GLOBAL_FREEZEGUN_IGNORE_LIST = ["kafka."]


def extend_freezegun_ignore_list():
    """Extend the freezegun ignore list"""
    import freezegun

    freezegun.configure(extend_ignore_list=GLOBAL_FREEZEGUN_IGNORE_LIST)
