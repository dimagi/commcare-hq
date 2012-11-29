# See http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
import functools

class memoized(object):
    """Decorator. Caches a function's return value each time it is called.
    If called later with the same arguments, the cached value is returned
    (not reevaluated).
    """
    def __init__(self, func):
        self.func = func
        self.cache = {}

    def __call__(self, *args, **kwargs):
        return self.call(None, self.cache, *args, **kwargs)

    def call(self, obj, cache, *args, **kwargs):
        if obj:
            args = (obj,) + args
        key = self.get_args_tuple(*args, **kwargs)
        try:
            return cache[key]
        except KeyError:
            value = self.func( *args, **kwargs)
            cache[key] = value
            return value

    def __repr__(self):
        """Return the function's docstring."""
        return self.func.__doc__

    def __get__(self, obj, objtype):
        """Support instance methods."""
        cache_attr = '_%s_cache' % self.func.__name__
        try:
            cache = getattr(obj, cache_attr)
        except AttributeError:
            cache = {}
            setattr(obj, cache_attr, cache)
        return functools.partial(self.call, obj, cache)

    def get_args_tuple(self, *args, **kwargs):
        """
        Take a function and the arguments you'd call it with
        and return a tuple
        """
        import inspect
        arg_names, args_name, kwargs_name, ___ = inspect.getargspec(self.func)
        values = inspect.getcallargs(self.func, *args, **kwargs)
        in_order = [values[arg_name] for arg_name in arg_names]
        if args_name:
            in_order.append(values[args_name])
        if kwargs_name:
            in_order.append(tuple(sorted(values[kwargs_name].items())))
        return tuple(in_order)
