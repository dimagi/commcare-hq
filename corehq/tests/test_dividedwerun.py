from unittest import TestCase

import pytest
from django.test import SimpleTestCase, TestCase as DatabaseTest
from unmagic import get_request

from .pytest_plugins.dividedwerun import name_of


def test_name_of_function_test():
    def do():
        pass
    func = make_function(do)

    assert name_of(func) == "corehq/tests/test_dividedwerun.py::do"


def test_name_of_with_setup_module():
    global setup_module

    def do():
        pass

    def da():
        pass

    do_func = make_function(do)
    da_func = make_function(da)

    assert name_of(do_func) != name_of(da_func)

    def setup_module():
        pass

    assert name_of(do_func) == name_of(da_func)
    del setup_module


class Test:

    def test(self):
        func = make_function(self.test)
        assert name_of(func) == "corehq/tests/test_dividedwerun.py::Test::test"


class TestSubclass(TestCase):

    def test(self):
        func = make_function(self.test)
        assert name_of(func) == "corehq/tests/test_dividedwerun.py::TestSubclass::test"


class TestSimpleSubclass(SimpleTestCase):

    def test(self):
        func = make_function(self.test)
        assert name_of(func) == "corehq/tests/test_dividedwerun.py::TestSimpleSubclass::test"


class TestCaseClassSetup(TestCase):

    @classmethod
    def setUpClass(cls):
        """Potentially expensive"""
        super().setUpClass()

    def test(self):
        func = make_function(self.test)
        other = make_function(self.other)
        assert name_of(func) == name_of(other)

    def other(self):
        pass


class TestSimpleClassSetup(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        """Potentially expensive"""
        super().setUpClass()

    def test(self):
        func = make_function(self.test)
        other = make_function(self.other)
        assert name_of(func) == name_of(other)

    def other(self):
        pass


class TestDbClassSetup(DatabaseTest):

    @classmethod
    def setUpClass(cls):
        """Potentially expensive"""
        # do not call super to skip db setup

    @classmethod
    def tearDownClass(cls):
        """Potentially expensive"""
        # do not call super to skip db teardown

    def test(self):
        func = make_function(self.test)
        other = make_function(self.other)
        assert name_of(func) == name_of(other)

    def other(self):
        pass


def make_function(func):
    return pytest.Function.from_parent(
        get_request().node.parent,
        name=func.__name__,
        callobj=func,
    )
