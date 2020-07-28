import importlib
import inspect
from collections import defaultdict

import attr

from dimagi.utils.logging import notify_exception


class ExtensionError(Exception):
    pass


@attr.s(frozen=True)
class ExtensionPoint:
    name = attr.ib()
    providing_args = attr.ib()


class Extension:
    def __init__(self, point, callable_ref, domains):
        self.point = point
        self.callable = callable_ref
        self.domains = domains
        self._callable = None

    def validate(self, extension_point):
        spec = inspect.getfullargspec(self.callable)
        unconsumed_args = set(extension_point.providing_args) - set(spec.args)
        if unconsumed_args and not spec.varkw:
            raise ExtensionError(f"Not all extension point args are consumed: {unconsumed_args}")

    def should_call(self, **kwargs):
        if self.domains is None or 'domain' not in kwargs:
            return True

        return kwargs['domain'] in self.domains

    def __call__(self, **kwargs):
        if self.should_call(**kwargs):
            return self.callable(**kwargs)

    def __repr__(self):
        return f"{self.callable_ref}"


class ExtensionCaller:
    def __init__(self, extension_point):
        self.extension_point = extension_point
        self.extensions = []

    def add_extension(self, extension):
        self.extensions.append(extension)

    def __call__(self, *args, **kwargs):
        results = []
        for extension in self.extensions:
            try:
                result = extension(**kwargs)
                if result is not None:
                    results.append(result)
            except Exception:  # noqa
                notify_exception(
                    None,
                    message="Error calling extension",
                    details={
                        "extention_point": self.extension_point.name,
                        "extension": extension,
                        "kwargs": kwargs
                    },
                )
        return results


class _Registry(object):
    """Extension implementation holder object for performing 1:N calls where N is the number
    of registered extensions.
    """


class CommCareExtensions:
    def __init__(self):
        self.registry = _Registry()
        self.extension_point_registry = {}
        self.locked = False

    def extension_point(self, func):
        """Decorator for creating an extension point.

        Usage:

            @extension_point
            def get_menu_items(menu_name, domain) -> List[str]:
                '''This function serves to define the extension point
                and should only have a docstring and no implementation
                '''

            # Use the extension point function as a decorator to tag
            # implementation functions or methods.

            @get_menu_items.extend
            def extra_menu_items(menu_name, domain):
                # actual implementation which will get called
                return ["Option A"] if menu_name == "options" else []

            # Extensions may also be limited to specific domains (only
            # for extension points that pass a domain argument).
            # Domains must be passed as a keyword argument and must be
            # a list.

            @get_menu_items.extend(domains=["more_options"])
            def menu_items_for_more_options_domain(menu_name, domain):
                assert domain == "more_options"
                return ["Option B"]
        """
        def extend(impl=None, *, domains=None):

            def _extend(impl):
                if self.locked:
                    raise ExtensionError(
                        "Late extension definition. Extensions must be defined before setup is complete"
                    )
                assert callable(impl), (
                    f"Incorrect usage of extension decorator. See docs below:"
                    f"\n\n{self.extension_point.__doc__}"
                )
                self.register_extension(Extension(func.__name__, impl, domains))
                return impl

            if domains is not None:
                assert isinstance(domains, list), "domains must be a list"
            return _extend if impl is None else _extend(impl)

        if self.locked:
            raise ExtensionError(
                "Late extension point definition. Extension points must "
                "be defined before setup is complete"
            )
        name = func.__name__
        args = inspect.getfullargspec(func).args
        self.extension_point_registry[name] = ExtensionPoint(name, args)
        func.extend = extend
        return func

    def load_extensions(self, implementations):
        for module_name in implementations:
            self.resolve_module(module_name)
        self.locked = True

    def add_extension_points(self, module_or_name):
        self.resolve_module(module_or_name)

    def resolve_module(self, module_or_name):
        if isinstance(module_or_name, str):
            importlib.import_module(module_or_name)

    def register_extension(self, extension):
        if extension.point not in self.extension_point_registry:
            raise ExtensionError(f"unknown extension point '{extension.point}'")

        extension_point = self.extension_point_registry[extension.point]
        extension.validate(extension_point)
        caller = getattr(self.registry, extension.point, None)
        if caller is None:
            caller = ExtensionCaller(extension_point)
            setattr(self.registry, extension_point.name, caller)
        caller.add_extension(extension)
