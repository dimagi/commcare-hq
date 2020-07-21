import re

import testil

from corehq.extensions.interface import ExtensionPoint, CommCareExtensions, ExtensionError


class DemoExtension:
    def __init__(self, mock_calls):
        self.mock_calls = {
            args: response for args, response in mock_calls.items()
        }

    def ext_point_a(self, arg1, domain):
        return self.mock_calls[(arg1, domain)]


demo_extension_1 = DemoExtension({
    (1, "d2"): "p1",
})


def demo_extension_2(arg1, domain):
    if arg1 == 1:
        return "p2"
    else:
        raise Exception


def demo_extension_3(**kwargs):
    """test that kwargs style functions are acceptable"""
    return "p3"


extensions = CommCareExtensions()
point = ExtensionPoint("ext_point_a", providing_args=("arg1", "domain"))
extensions.register_extension_point(point)

extensions.load_extensions({
    "ext_point_a": [
        {
            "callable": demo_extension_1.ext_point_a,
            "domains": ["d2"],
        },
        {
            "callable": demo_extension_2,
        },
        {
            "callable": "corehq.extensions.tests.demo_extension_3",
            "domains": ["d1"],
        },
    ]
})


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
        extensions.register_extension("missing", demo_extension_2)


def test_validation_missing_callable():
    with testil.assert_raises(ExtensionError, msg="Extension not found: 'corehq.missing'"):
        extensions.register_extension("ext_point_a", "corehq.missing")


def test_validation_not_callable():
    with testil.assert_raises(ExtensionError, msg=re.compile("not callable")):
        extensions.register_extension("ext_point_a", demo_extension_1)


def test_validation_callable_args():
    def bad_spec(a, domain):
        pass

    with testil.assert_raises(ExtensionError, msg=re.compile("consumed.*arg1")):
        extensions.register_extension("ext_point_a", bad_spec)
