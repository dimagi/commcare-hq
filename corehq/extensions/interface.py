import importlib
import inspect

from dimagi.utils.logging import notify_exception


class ExtensionError(Exception):
    pass


class Extension:
    def __init__(self, point, callable_ref, domains):
        self.point = point
        self.callable = callable_ref
        self.domains = set(domains) if domains else None

    def validate(self, expected_args):
        spec = inspect.getfullargspec(self.callable)
        unconsumed_args = set(expected_args) - set(spec.args)
        if unconsumed_args and not spec.varkw:
            raise ExtensionError(f"Not all extension point args are consumed: {unconsumed_args}")

    def should_call_for_domain(self, domain):
        return self.domains is None or domain in self.domains

    def __call__(self, *args, **kwargs):
        return self.callable(*args, **kwargs)

    def __repr__(self):
        return f"{self.callable}"


class ExtensionPoint:
    def __init__(self, manager, name, definition_function):
        self.manager = manager
        self.name = name
        self.definition_function = definition_function
        self.providing_args = inspect.getfullargspec(definition_function).args
        self.extensions = []
        self.__doc__ = inspect.getdoc(definition_function)

    def extend(self, impl=None, *, domains=None):

        def _extend(impl):
            if self.manager.locked:
                raise ExtensionError(
                    "Late extension definition. Extensions must be defined before setup is complete"
                )
            if not callable(impl):
                raise ExtensionError(f"Extension point implementation must be callable: {impl!r}")
            extension = Extension(self.name, impl, domains)
            extension.validate(self.providing_args)
            self.extensions.append(extension)
            return impl

        if domains is not None and not isinstance(domains, list):
            raise ExtensionError("domains must be a list")
        if domains is not None and "domain" not in self.providing_args:
            raise ExtensionError("domain filtering not supported for this extension point")
        return _extend if impl is None else _extend(impl)

    def __call__(self, *args, **kwargs):
        results = []
        callargs = inspect.getcallargs(self.definition_function, *args, **kwargs)
        domain = callargs.get('domain')
        for extension in self.extensions:
            if domain and not extension.should_call_for_domain(domain):
                continue
            try:
                result = extension(*args, **kwargs)
                if result is not None:
                    results.append(result)
            except Exception:  # noqa
                notify_exception(
                    None,
                    message="Error calling extension",
                    details={
                        "extention_point": self.name,
                        "extension": extension,
                        "kwargs": kwargs
                    },
                )
        return results


class CommCareExtensions:
    def __init__(self):
        self.registry = {}
        self.locked = False

    def extension_point(self, func):
        """Decorator for creating an extension point."""
        if self.locked:
            raise ExtensionError(
                "Late extension point definition. Extension points must "
                "be defined before setup is complete"
            )
        name = func.__name__
        point = ExtensionPoint(self, name, func)
        self.registry[name] = point
        return point

    def load_extensions(self, implementations):
        for module_name in implementations:
            self.resolve_module(module_name)
        self.locked = True

    def add_extension_points(self, module_or_name):
        self.resolve_module(module_or_name)

    def resolve_module(self, module_or_name):
        if isinstance(module_or_name, str):
            importlib.import_module(module_or_name)
