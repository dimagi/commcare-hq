import sys

from testil import assert_raises as _assert_raises

from .tools import nottest as nottest_tool


def create_nose_virtual_package():
    sys.modules['nose.tools'] = VirtualNose.tools
    sys.modules['nose.plugins.attrib'] = VirtualNose.plugins.attrib


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

    class plugins:
        class attrib:
            def attr(*args, **kwargs):
                # TODO adapt to pytest
                """Decorator that adds attributes to classes or functions
                for use with the Attribute (-a) plugin.
                """
                def wrap_ob(ob):
                    for name in args:
                        setattr(ob, name, True)
                    for name, value in kwargs.items():
                        setattr(ob, name, value)
                    return ob
                return wrap_ob
