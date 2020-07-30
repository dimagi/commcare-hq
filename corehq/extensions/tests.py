import re

import testil

from corehq.extensions.interface import CommCareExtensions, ExtensionError, ResultFormat
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


def test_commcare_extensions():
    def check(args, kwargs, expected):
        results = ext_point_a(*args, **kwargs)
        testil.eq(results, expected)

    cases = [
        ([], {"arg1": 1, "domain": "d1"}, ["p2", "p3"]),
        ([], {"arg1": 2, "domain": "d1"}, ["p3"]),
        ([1, "d2"], {}, ["p1", "p2"]),
        ([], {"arg1": 2, "domain": "d2"}, []),
    ]
    for args, kwargs, expected in cases:
        yield check, args, kwargs, expected


def test_validation_not_callable():
    with testil.assert_raises(ExtensionError, msg=re.compile("callable")):
        ext_point_a.extend("not callable")


def test_validation_callable_args():
    def bad_spec(a, domain):
        pass

    with testil.assert_raises(ExtensionError, msg=re.compile("consumed.*arg1")):
        ext_point_a.extend(bad_spec)


@generate_cases([
    ([["d1"]], {}, re.compile(r"callable: \['d1'\]")),
    ([], {"domains": "d1"}, re.compile("domains must be a list")),
    ([], {"domains": ["d1"]}, re.compile("domain filtering not supported")),
])
def test_decorator(self, args, kwargs, exception_message):
    ext = CommCareExtensions()
    ext_point = ext.extension_point(lambda: None)
    with testil.assert_raises(ExtensionError, msg=exception_message):
        @ext_point.extend(*args, **kwargs)
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


def test_flatten_results():
    ext = CommCareExtensions()

    @ext.extension_point(result_format=ResultFormat.FLATTEN)
    def ext_point_d():
        """test"""

    @ext_point_d.extend
    def extend_1():
        return [1, 2]

    @ext_point_d.extend
    def extend_2():
        return [3, 4]

    testil.eq(ext_point_d(), [1, 2, 3, 4])


def test_single_value():
    ext = CommCareExtensions()

    @ext.extension_point(result_format=ResultFormat.FIRST)
    def ext_point_d():
        """test"""

    @ext_point_d.extend
    def extend_1():
        return None

    @ext_point_d.extend
    def extend_2():
        return 1

    testil.eq(ext_point_d(), 1)


def test_single_value_none():
    ext = CommCareExtensions()

    @ext.extension_point(result_format=ResultFormat.FIRST)
    def ext_point():
        pass

    testil.eq(ext_point(), None)
