import inspect
from collections import defaultdict

import attr

from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function


@attr.s(frozen=True)
class ExtensionPoint:
    name = attr.ib()
    providing_args = attr.ib()
    docs = attr.ib(default="")


class PluginContribution:
    def __init__(self, callable_ref, domains=None):
        self.callable_ref = callable_ref
        self.domains = domains
        self._callable = None

    def validate(self, extension_point):
        _callable = self.callable_ref
        if isinstance(_callable, str):
            _callable = to_function(self.callable_ref)
        if not _callable:
            raise Exception(f"Plugin not found: '{self.callable_ref}'")
        if not callable(_callable):
            raise Exception(f"Plugin not callable: '{self.callable_ref}'")
        self._callable = _callable
        spec = inspect.getfullargspec(_callable)
        unconsumed_args = set(extension_point.providing_args) - set(spec.args)
        if unconsumed_args and not spec.varkw:
            raise Exception(f"Not all extension point args are consumed: {unconsumed_args}")

    def should_call(self, **kwargs):
        if self.domains is None or 'domain' not in kwargs:
            return True

        return kwargs['domain'] in self.domains

    def __call__(self, **kwargs):
        if self.should_call(**kwargs):
            return self._callable(**kwargs)

    def __repr__(self):
        return f"{self.callable_ref}"


class Plugins:
    def __init__(self):
        self.registry = defaultdict(list)
        self.extension_point_registry = {}

    def load_plugins(self, plugins):
        for point, plugin_defs in plugins.items():
            for plugin_def in plugin_defs:
                self.register_plugin(point, plugin_def["callable"], plugin_def.get("domains", None))

    def register_plugin(self, point, callable_ref, domains=None):
        if point not in self.extension_point_registry:
            raise Exception(f"unknown extension point '{point}'")

        plugin = PluginContribution(callable_ref, domains)
        plugin.validate(self.extension_point_registry[point])
        self.registry[point].append(plugin)

    def register_extension_point(self, point: ExtensionPoint):
        if point.name in self.extension_point_registry:
            raise Exception(f"Exception point '{point.name}' already registered")
        self.extension_point_registry[point.name] = point

    def get_extension_point_contributions(self, extension_point, **kwargs):
        plugins = self.registry[extension_point]
        results = []
        for plugin in plugins:
            try:
                result = plugin(**kwargs)
                if result is not None:
                    results.append(result)
            except Exception:  # noqa
                notify_exception(
                    None,
                    message="Error calling plugin",
                    details={
                        "extention_point": extension_point,
                        "plugin": plugin,
                        "kwargs": kwargs
                    },
                )
        return results
