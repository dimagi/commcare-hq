import sys

from testil import assert_raises as _assert_raises

from .tools import nottest as nottest_tool


def create_nose_virtual_package():
    sys.modules['nose.tools'] = VirtualNose.tools


class VirtualNose:
    """Legacy namespace for tests written before pytest"""
    class tools:
        nottest = nottest_tool
        assert_raises = _assert_raises

        def assert_equal(actual, expected):
            assert actual == expected

        def assert_false(value):
            assert not value

        def assert_true(value):
            assert value

        def assert_in(needle, haystack):
            assert needle in haystack

        def assert_list_equal(actual, expected):
            assert actual == expected

        def assert_is_none(value):
            assert value is None
