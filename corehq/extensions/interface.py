import importlib
import inspect
from collections import defaultdict

import attr

from dimagi.utils.logging import notify_exception
from dimagi.utils.modules import to_function


class ExtensionError(Exception):
    pass


@attr.s(frozen=True)
class ExtensionPoint:
    name = attr.ib()
    providing_args = attr.ib()


def extension_point(func):
    """Decorator for creating an extension point"""
    def extend(domains=None):

        def _extend(impl):
            setattr(impl, "extension_point_impl", {
                "spec": func.__name__,
                "domains": domains
            })
            return impl

        return _extend

    func.extension_point_spec = {"name": func.__name__}
    func.extend = extend
    return func


class ExtensionContribution:
    def __init__(self, callable_ref, domains=None):
        self.callable_ref = callable_ref
        self.domains = domains
        self._callable = None

    def validate(self, extension_point):
        _callable = self.callable_ref
        if isinstance(_callable, str):
            _callable = to_function(self.callable_ref)
        if not _callable:
            raise ExtensionError(f"Extension not found: '{self.callable_ref}'")
        if not callable(_callable):
            raise ExtensionError(f"Extension not callable: '{self.callable_ref}'")
        self._callable = _callable
        spec = inspect.getfullargspec(_callable)
        unconsumed_args = set(extension_point.providing_args) - set(spec.args)
        if unconsumed_args and not spec.varkw:
            raise ExtensionError(f"Not all extension point args are consumed: {unconsumed_args}")

    def should_call(self, **kwargs):
        if self.domains is None or 'domain' not in kwargs:
            return True

        return kwargs['domain'] in self.domains

    def __call__(self, **kwargs):
        if self.should_call(**kwargs):
            return self._callable(**kwargs)

    def __repr__(self):
        return f"{self.callable_ref}"


class CommCareExtensions:
    def __init__(self):
        self.registry = defaultdict(list)
        self.extension_point_registry = {}

    def load_extensions(self, implementations):
        for module_name in implementations:
            self.register_extensions(module_name)

    def add_extension_points(self, module_or_name):
        names = []
        module = self.resolve_module(module_or_name)
        for name in dir(module):
            method = getattr(module, name)
            spec_opts = getattr(method, "extension_point_spec", None)
            if spec_opts is not None:
                name = spec_opts["name"]
                if name in self.extension_point_registry:
                    raise ExtensionError(f"Exception point '{name}' already registered")
                spec = inspect.getfullargspec(method)
                self.extension_point_registry[name] = ExtensionPoint(name, spec.args)
                names.append(name)

        if not names:
            raise ValueError(f"did not find any extension points in {module!r}")

    def register_extensions(self, module_or_name):
        names = []
        module = self.resolve_module(module_or_name)
        for name in dir(module):
            method = getattr(module, name)
            spec_opts = getattr(method, "extension_point_impl", None)
            if spec_opts is not None:
                spec = spec_opts["spec"]
                domains = spec_opts["domains"]
                self.register_extension(spec, method, domains)
                names.append(name)

        if not names:
            raise ValueError(f"did not find any extensions in {module!r}")

    def resolve_module(self, module_or_name):
        if isinstance(module_or_name, str):
            return importlib.import_module(module_or_name)
        else:
            return module_or_name

    def register_extension(self, point, callable_ref, domains=None):
        if point not in self.extension_point_registry:
            raise ExtensionError(f"unknown extension point '{point}'")

        extension = ExtensionContribution(callable_ref, domains)
        extension.validate(self.extension_point_registry[point])
        self.registry[point].append(extension)

    def get_extension_point_contributions(self, extension_point, **kwargs):
        extensions = self.registry[extension_point]
        results = []
        for extension in extensions:
            try:
                result = extension(**kwargs)
                if result is not None:
                    results.append(result)
            except Exception:  # noqa
                notify_exception(
                    None,
                    message="Error calling extension",
                    details={
                        "extention_point": extension_point,
                        "extension": extension,
                        "kwargs": kwargs
                    },
                )
        return results
