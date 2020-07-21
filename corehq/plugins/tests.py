import re

import testil

from corehq.plugins.interface import ExtensionPoint, Plugins, ExtensionError


class DemoPlugin:
    def __init__(self, mock_calls):
        self.mock_calls = {
            args: response for args, response in mock_calls.items()
        }

    def ext_point_a(self, arg1, domain):
        return self.mock_calls[(arg1, domain)]


demo_plugin_1 = DemoPlugin({
    (1, "d2"): "p1",
})


def demo_plugin_2(arg1, domain):
    if arg1 == 1:
        return "p2"
    else:
        raise Exception


def demo_plugin_3(**kwargs):
    """test that kwargs style functions are acceptable"""
    return "p3"


plugins = Plugins()
point = ExtensionPoint("ext_point_a", providing_args=("arg1", "domain"))
plugins.register_extension_point(point)

plugins.load_plugins({
    "ext_point_a": [
        {
            "callable": demo_plugin_1.ext_point_a,
            "domains": ["d2"],
        },
        {
            "callable": demo_plugin_2,
        },
        {
            "callable": "corehq.plugins.tests.demo_plugin_3",
            "domains": ["d1"],
        },
    ]
})


def test_plugins():
    def check(kwargs, expected):
        results = plugins.get_extension_point_contributions("ext_point_a", **kwargs)
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
        plugins.register_plugin("missing", demo_plugin_2)


def test_validation_missing_callable():
    with testil.assert_raises(ExtensionError, msg="Plugin not found: 'corehq.missing'"):
        plugins.register_plugin("ext_point_a", "corehq.missing")


def test_validation_not_callable():
    with testil.assert_raises(ExtensionError, msg=re.compile("not callable")):
        plugins.register_plugin("ext_point_a", demo_plugin_1)


def test_validation_callable_args():
    def bad_spec(a, domain):
        pass

    with testil.assert_raises(ExtensionError, msg=re.compile("consumed.*arg1")):
        plugins.register_plugin("ext_point_a", bad_spec)

