from abc import ABC, abstractmethod
from importlib import import_module

import attr


@attr.s(frozen=True)
class ExtensionPoint:
    name = attr.ib()
    providing_args = attr.ib()
    docs = attr.ib(default="")


class Plugins(ABC):
    def __init__(self):
        self.registry = {}
        self.extension_point_registry = {}

    def register_plugin(self, plugin):
        if isinstance(plugin, str):
            plugin_module = import_module(plugin)
            if not hasattr(plugin_module, 'CommCarePlugin'):
                # XXX: log warning
                return
            plugin = plugin_module.CommCarePlugin()

        if plugin.key in self.registry:
            raise Exception(f"Plugin with key '{plugin.key}' already registered")

        self.registry[plugin.key] = plugin
        self.connect_extension_points(plugin)

    def register_extension_point(self, point: ExtensionPoint):
        if point.name in self.extension_point_registry:
            raise Exception(f"Exception point '{point.name}' already registered")
        self.extension_point_registry[point.name] = point

    @abstractmethod
    def connect_extension_points(self, plugin):
        """For the given plugin connect any extension points"""
        pass

    @abstractmethod
    def get_extension_point_contributions(self, extension_point, **kwargs):
        """This is the main interface for callers to receive responses from plugins"""
        pass
