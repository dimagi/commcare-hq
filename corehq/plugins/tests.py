import testil

from corehq import plugins
from corehq.plugins.interface import ExtensionPoint


class DemoPlugin:
    def __init__(self, key, mock_calls):
        self.key = key
        self.mock_calls = {
            args: response for args, response in mock_calls.items()
        }

    def ext_point_a(self, arg1, arg2):
        return self.mock_calls[(arg1, arg2)]


def test_plugin():
    point = ExtensionPoint("ext_point_a", providing_args=("arg1", "arg2"))
    plugins.register_extension_point(point)

    demo_plugin_1 = DemoPlugin("p1", {
        (1, 2): "response1_p1",
        (3, 4): "response2_p1"
    })
    demo_plugin_2 = DemoPlugin("p2", {
        (1, 2): "response1_p2",
    })
    plugins.register_plugin(demo_plugin_1)
    plugins.register_plugin(demo_plugin_2)

    responses = plugins.get_contributions("ext_point_a", arg1=1, arg2=2)
    testil.eq(["response1_p1", "response1_p2"], responses)

    responses = plugins.get_contributions("ext_point_a", arg1=3, arg2=4)
    testil.eq(["response2_p1"], responses)
