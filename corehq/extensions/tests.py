import re

import testil

from corehq.extensions.interface import CommCareExtensions, Extension, ExtensionError
from corehq.util.test_utils import generate_cases

extensions = CommCareExtensions()
extension_point = extensions.extension_point


@extension_point
def ext_point_a(arg1, domain):
    pass


class DemoExtension:
    def __init__(self, mock_calls):
        self.mock_calls = {
            args: response for args, response in mock_calls.items()
        }

    def ext_point_a(self, arg1, domain):
        return self.mock_calls[(arg1, domain)]


demo_extension = DemoExtension({
    (1, "d2"): "p1",
})
ext_point_a.extend(domains=["d2"])(demo_extension.ext_point_a)


@ext_point_a.extend()
def demo_extension_2(arg1, domain):
    if arg1 == 1:
        return "p2"
    else:
        raise Exception


@ext_point_a.extend(domains=["d1"])
def demo_extension_3(**kwargs):
    """test that kwargs style functions are acceptable"""
    return "p3"


def setup():
    extensions.add_extension_points(None)
    extensions.load_extensions(["corehq.extensions.tests"])


def test_commcare_extensions():
    def check(kwargs, expected):
        results = extensions.get_extension_point_contributions("ext_point_a", **kwargs)
        testil.eq(results, expected)

    cases = [
        ({"arg1": 1, "domain": "d1"}, ["p2", "p3"]),
        ({"arg1": 2, "domain": "d1"}, ["p3"]),
        ({"arg1": 1, "domain": "d2"}, ["p1", "p2"]),
        ({"arg1": 2, "domain": "d2"}, []),
    ]
    for kwargs, expected in cases:
        yield check, kwargs, expected


def test_validation_missing_point():
    with testil.assert_raises(ExtensionError, msg="unknown extension point 'missing'"):
        extensions.register_extension(Extension("missing", demo_extension_2, None))


def test_validation_not_callable():
    with testil.assert_raises(TypeError):
        extensions.register_extension(Extension("ext_point_a", "corehq.missing", None))


def test_validation_callable_args():
    def bad_spec(a, domain):
        pass

    with testil.assert_raises(ExtensionError, msg=re.compile("consumed.*arg1")):
        extensions.register_extension(Extension("ext_point_a", bad_spec, None))


@generate_cases([
    ([["d1"]], {}, re.compile("Incorrect usage")),
    ([], {"domains": "d1"}, re.compile("domains must be a list")),
])
def test_decorator(self, args, kwargs, exception_message):
    ext = CommCareExtensions()
    ext.extension_point(ext_point_a)
    with testil.assert_raises(AssertionError, msg=exception_message):
        @ext_point_a.extend(*args, **kwargs)
        def impl():
            pass


def test_late_extension_definition():
    ext = CommCareExtensions()

    @ext.extension_point
    def ext_point_b():
        """testing..."""

    ext.load_extensions([])
    with testil.assert_raises(ExtensionError, msg=re.compile("Late extension definition")):
        @ext_point_b.extend
        def impl():
            pass


def test_late_extension_point_definition():
    ext = CommCareExtensions()
    ext.load_extensions([])

    with testil.assert_raises(ExtensionError, msg=re.compile("Late extension point definition")):
        @ext.extension_point
        def ext_point_c():
            """testing..."""
